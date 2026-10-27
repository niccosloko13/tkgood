"""Launch console children without a Windows console; preserve their output."""
import contextlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def hidden_kwargs():
    if os.name != 'nt':
        return {'start_new_session': True}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0  # SW_HIDE
    return {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            'startupinfo': startup}


class Tee:
    def __init__(self, original, log):
        self.original, self.log = original, log
    def write(self, text):
        self.log.write(text)
        if self.original:
            self.original.write(text)
        self.flush()
        return len(text)
    def flush(self):
        self.log.flush()
        if self.original:
            self.original.flush()


@contextlib.contextmanager
def logged(name):
    directory = ROOT / '.runtime/logs'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / name).open('a', encoding='utf-8') as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            yield
