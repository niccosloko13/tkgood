"""Canonical local launcher: direct starts use the same owned control as devctl."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.request import urlopen


def existing_server(port):
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',port))!=0:return None
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/status',timeout=2) as response:data=json.load(response)
        if data.get('app')=='online' and data.get('mode')=='normal_chrome_bridge':return {'kind':'babi'}
    except (OSError,ValueError):pass
    owner='PID/processo indisponivel'
    if os.name=='nt':
        from scripts.process_runtime import hidden_kwargs
        command=f"Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object {{ Get-Process -Id $_.OwningProcess | Select-Object Id,ProcessName | ConvertTo-Json -Compress }}"
        try:
            raw=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=5,**hidden_kwargs())
            data=json.loads(raw.stdout);owner=f"PID {data['Id']} ({data['ProcessName']})"
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):pass
    return {'kind':'other','owner':owner}


def serve(port):
    import uvicorn
    from app.main import app
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,reload=False))
    app.state.dev_shutdown=lambda:setattr(server,'should_exit',True)
    server.run()


def main():
    port=int(os.environ.get('PH_PORT','8000'))
    if os.environ.get('PH_DEV_CONTROL')=='1' and os.environ.get('PH_RUN_ID'):
        serve(port);return 0
    sys.path.insert(0,str(Path(__file__).resolve().parent/'scripts'))
    from dev_supervisor import Supervisor,DevError,build_extension
    try:
        current=existing_server(port)
        if current:
            if current['kind']=='babi':
                print(f'Babi j\u00e1 est\u00e1 rodando em http://127.0.0.1:{port}');return 0
            print(f"Porta {port} ocupada por {current['owner']}; nenhum processo foi encerrado.");return 1
        supervisor=Supervisor(port=port)
        with supervisor.lock():
            supervisor.provision();build_extension();supervisor.start()
        print(f'Babi rodando em http://127.0.0.1:{port}');return 0
    except (OSError,ValueError,DevError) as exc:
        print(f'Babi: {exc}');return 1
    except KeyboardInterrupt:
        print('Inicializacao interrompida.');return 130


if __name__=='__main__':raise SystemExit(main())
