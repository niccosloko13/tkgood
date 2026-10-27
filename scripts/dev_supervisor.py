"""Own exactly one Product Hunter backend. No process/port-based killing."""
from process_runtime import hidden_kwargs, logged
import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class DevError(RuntimeError):
    pass


def identity(pid):
    """Creation identity + executable protects against PID reuse; never uses a PID alone."""
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            size = wintypes.DWORD(32768)
            path = ctypes.create_unicode_buffer(size.value)
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            # An exited process can retain a handle; reject its nonzero exit time.
            if times[1].dwHighDateTime or times[1].dwLowDateTime:
                return None
            if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                return None
            return {'created': (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    'executable': os.path.normcase(path.value)}
        finally:
            kernel.CloseHandle(handle)
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        if stat[0] == 'Z':
            return None
        return {'created': stat[19], 'executable': os.readlink(f'/proc/{pid}/exe')}
    except (OSError, IndexError):
        return None


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value), encoding='utf-8')
    os.replace(temp, path)
    if os.name != 'nt':
        path.chmod(0o600)


def build_extension(root=ROOT):
    extension = root/'extension'
    digest = hashlib.sha256()
    for path in sorted(extension.iterdir()):
        if path.is_file() and path.name not in ('dev_config.js','build.js'):
            digest.update(path.name.encode()+b'\0'+path.read_bytes())
    contract_path=root/'config/companion_api.json'
    if contract_path.exists():digest.update(b'companion_api\0'+contract_path.read_bytes())
    api=json.loads(contract_path.read_text(encoding='utf-8'))['api_version'] if contract_path.exists() else '1'
    build = digest.hexdigest()[:16]
    (extension/'build.js').write_text('globalThis.PH_BUILD_ID = '+json.dumps(build)+';\nglobalThis.PH_API_VERSION = '+json.dumps(api)+';\n',encoding='utf-8')
    return build


class Supervisor:
    def __init__(self, root=ROOT, runtime=None, port=8000, runner=None):
        self.root = Path(root).resolve()
        self.runtime = Path(runtime or self.root/'.runtime')
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.port = port
        self.base = f'http://127.0.0.1:{port}'
        self.runner = Path(runner or self.root/'run.py')
        self.record_path = self.runtime/'backend.pid'
        self.config_path = self.runtime/'dev.json'

    @contextlib.contextmanager
    def lock(self):
        with (self.runtime/'control.lock').open('a+b') as handle:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:
                raise DevError('Another devctl operation is running') from exc
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    fcntl.flock(handle,fcntl.LOCK_UN)

    def provision(self):
        if self.config_path.exists():
            config = json.loads(self.config_path.read_text(encoding='utf-8'))
        else:
            # Pin the already installed Companion's routing ID; never auto-trust
            # the first extension that happens to call an administration endpoint.
            import sqlite3
            with sqlite3.connect(self.root/'data/product_hunter.db') as con:
                row = con.execute("SELECT value_json FROM system_state WHERE key='tiktok_bridge'").fetchone()
            extension_id = json.loads(row[0]).get('extension_id') if row else None
            import re
            if not extension_id or not re.fullmatch('[a-p]{32}',extension_id):
                raise DevError('No installed Companion identity in this workspace database')
            config = {'extension_id':extension_id,'token':secrets.token_urlsafe(48)}
            atomic_json(self.config_path,config)
        (self.root/'extension/dev_config.js').write_text(
            'globalThis.PH_DEV = '+json.dumps(config)+';\n',encoding='utf-8')
        return config

    def request(self, path, payload=None, timeout=3):
        config = json.loads(self.config_path.read_text(encoding='utf-8')) if self.config_path.exists() else {}
        req = Request(self.base+path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json','X-PH-Dev-Token':config.get('token','')})
        with urlopen(req,timeout=timeout) as response:
            return json.load(response)

    def healthy(self):
        try:
            data = self.request('/api/status',timeout=1)
            return data if data.get('app') == 'online' and data.get('mode') == 'normal_chrome_bridge' else None
        except (OSError,ValueError):
            return None

    def record(self):
        try:
            value = json.loads(self.record_path.read_text(encoding='utf-8'))
            if value['root'] != str(self.root) or value['identity'] != identity(value['pid']):
                return None
            return value
        except (OSError,ValueError,KeyError,TypeError):
            return None

    def wait_health(self, run_id, timeout=25):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.healthy():
                try:
                    if self.request('/api/dev/status')['run_id'] == run_id:
                        return
                except (OSError,KeyError,ValueError):
                    pass
            time.sleep(.25)
        raise DevError(f'Health timeout after {timeout}s; inspect {self.runtime / "logs/backend.log"}')

    def start(self, timeout=25):
        record=self.record()
        if record:
            self.wait_health(record['run_id'],timeout)
            return record
        # Do not start even if the listener is a different/unhealthy service.
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',self.port)) == 0:
                raise DevError(f'Port {self.port} is occupied by an unmanaged process; nothing terminated')
        run_id=secrets.token_hex(16)
        env={**os.environ,'PH_DEV_CONTROL':'1','PH_RUN_ID':run_id,'PH_PORT':str(self.port),'PYTHONUNBUFFERED':'1'}
        (self.runtime/'logs').mkdir(parents=True,exist_ok=True)
        with (self.runtime/'logs/backend.log').open('ab') as log:
            log.write(f'\n--- Supervisor starting {run_id} ---\n'.encode()); log.flush()
            process=subprocess.Popen([sys.executable,str(self.runner)],cwd=self.root,env=env,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                **hidden_kwargs())
        stamp=identity(process.pid)
        if stamp is None:
            raise DevError('Backend exited before ownership could be recorded; inspect backend.log')
        record={'pid':process.pid,'identity':stamp,'root':str(self.root),'run_id':run_id}
        atomic_json(self.record_path,record)
        self.wait_health(run_id,timeout)
        return record

    def drain(self, timeout=60):
        self.request('/api/dev/drain',{})
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            active=self.request('/api/dev/status')['active']
            if not any(active.values()):
                return
            time.sleep(.5)
        raise DevError(f'Active operations did not finish within {timeout}s: {active}; restart refused')

    def stop(self, timeout=20):
        record=self.record()
        if not record:
            if self.healthy():
                raise DevError('Backend is unmanaged or PID identity changed; shutdown refused')
            return
        live=self.request('/api/dev/status')
        if live['run_id'] != record['run_id']:
            raise DevError('Backend run identity differs from owned process; shutdown refused')
        self.request('/api/dev/shutdown',{})
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if identity(record['pid']) is None:
                return
            time.sleep(.2)
        raise DevError('Owned backend did not exit gracefully; no other process was killed')

    def restart(self):
        if self.record():
            self.drain()
            self.stop()
        elif self.healthy():
            raise DevError('Existing backend was not started by this supervisor; restart refused')
        return self.start()


if __name__ == '__main__':
    with logged('supervisor.log'):
        supervisor=Supervisor()
        with supervisor.lock():
            supervisor.provision()
            build_extension()
            print(json.dumps(supervisor.start()))
