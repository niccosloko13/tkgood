"""Initial migration via the installed Companion's own non-web-accessible page.

No UI automation, process termination, debugger ports or Chrome settings pages.
"""
import ctypes
import json
import os
from pathlib import Path
import subprocess

from dev_supervisor import DevError, ROOT
from process_runtime import hidden_kwargs


def windows_args(command):
    from ctypes import wintypes
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
    kernel=ctypes.WinDLL('kernel32')
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    count=ctypes.c_int()
    argv=shell.CommandLineToArgvW(command,ctypes.byref(count))
    if not argv: raise DevError('Could not verify Chrome command line')
    try: return [argv[i] for i in range(count.value)]
    finally: kernel.LocalFree(argv)


def dedicated_roots(processes, profile, parse_args=windows_args):
    expected=os.path.normcase(str(Path(profile).resolve()))
    found=[]
    for process in processes:
        args=parse_args(process.get('CommandLine') or '')
        if any(arg.startswith('--type=') for arg in args): continue
        profiles=[arg.split('=',1)[1] for arg in args if arg.startswith('--user-data-dir=')]
        if len(profiles)==1 and os.path.normcase(str(Path(profiles[0]).resolve()))==expected:
            if Path(process.get('ExecutablePath') or '').name.lower()=='chrome.exe': found.append(process)
    return found


def bootstrap(root=ROOT):
    import sys
    sys.path.insert(0,str(root))
    if os.name!='nt': raise DevError('Legacy Companion bootstrap supports Windows only')
    profile=root/'browser-profiles/chrome-tiktok-main'
    query="Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Select-Object ProcessId,ExecutablePath,CommandLine,@{Name='CreatedTicks';Expression={$_.CreationDate.ToUniversalTime().Ticks.ToString()}} | ConvertTo-Json -Compress"
    (root/'.runtime/logs').mkdir(parents=True,exist_ok=True)
    with (root/'.runtime/logs/chrome-bootstrap.log').open('a',encoding='utf-8') as log:
        raw=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',query],text=True,timeout=10,stderr=log,**hidden_kwargs())
    rows=json.loads(raw or '[]'); rows=rows if isinstance(rows,list) else [rows]
    candidates=dedicated_roots(rows,profile)
    if len(candidates)>1:
        raise DevError(f'Ambiguous dedicated Chrome profile: {len(candidates)} browser roots; no action performed')
    if candidates:
        executable=candidates[0]['ExecutablePath']
    else:
        raise DevError('Dedicated Chrome profile is not running; refusing to open another Chrome. Restore the existing Companion profile first')
    config=json.loads((root/'.runtime/dev.json').read_text(encoding='utf-8'))
    with (root/'.runtime/logs/chrome-bootstrap.log').open('a',encoding='utf-8') as log:
        subprocess.Popen([executable,f'--user-data-dir={profile}','--no-first-run',
                      '--no-default-browser-check',f'chrome-extension://{config["extension_id"]}/dev_bootstrap.html'],
                     stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    with (root/'.runtime/logs/chrome-bootstrap.log').open('a',encoding='utf-8') as log:
        log.write(f'Legacy worker bootstrap: opened Companion local upgrade page in dedicated profile {profile}\n')

