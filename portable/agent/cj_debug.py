"""Shared debug logger for Claw Jump agent modules.

Set CLAW_JUMP_DEBUG=1 to write millisecond-precision timestamps to
%TEMP%/claw-jump-debug.log (Windows) or /tmp/claw-jump-debug.log.
"""
import os
import time
import tempfile

_debug_file = None
_start_time = time.time()


def _init():
    global _debug_file
    if os.environ.get("CLAW_JUMP_DEBUG"):
        path = os.path.join(tempfile.gettempdir(), "claw-jump-debug.log")
        _debug_file = open(path, "a", encoding="utf-8")


def dbg(tag, fmt, *args):
    """Write a timestamped debug line. Safe to call from any thread."""
    if _debug_file is None:
        return
    ts = time.strftime("%Y-%m-%dT%H:%M:%S.", time.localtime()) + f"{time.time() % 1:.3f}"[2:]
    elapsed = (time.time() - _start_time) * 1000
    msg = fmt % args if args else fmt
    line = f"[{tag} {ts} +{elapsed:7.1f}ms] {msg}\n"
    try:
        _debug_file.write(line)
        _debug_file.flush()
    except Exception:
        pass


_init()
