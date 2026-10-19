"""Bounded subprocess execution with cooperative job cancellation."""
from __future__ import annotations
import subprocess
import tempfile
import time
from pathlib import Path

class RenderCancelled(RuntimeError):
    pass

def check_cancel(cancel_file: Path | None) -> None:
    if cancel_file and Path(cancel_file).exists():
        raise RenderCancelled('Render cancelled by operator. Completed cached speech is retained.')

def run(args: list, cancel_file: Path | None = None, timeout: float = 1800, *, cwd=None, env=None) -> str:
    check_cancel(cancel_file)
    # File-backed output prevents long FFmpeg logs from filling pipe buffers or RAM.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(a) for a in args], stdout=output, stderr=errors, cwd=cwd, env=env,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        start = time.monotonic()
        try:
            while process.poll() is None:
                check_cancel(cancel_file)
                if time.monotonic() - start > timeout:
                    raise TimeoutError(f'Process exceeded {timeout:g} seconds: {Path(str(args[0])).name}')
                time.sleep(0.1)
        except BaseException:
            process.kill()
            process.wait()
            raise
        output.seek(0)
        errors.seek(0, 2)
        size = errors.tell()
        errors.seek(max(0, size - 5000))
        error = errors.read().decode('utf-8', errors='replace')
        if process.returncode:
            raise RuntimeError(error or f'Process exited with code {process.returncode}')
        return output.read().decode('utf-8', errors='replace')
