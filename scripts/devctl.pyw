"""Windowless Windows entry point; results live in .runtime/logs/."""
import sys
from process_runtime import logged
from background_runner import launch

with logged('devctl.log'):
    try:
        print('Background task:',launch('devctl',sys.argv[1:] or ['status']))
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
