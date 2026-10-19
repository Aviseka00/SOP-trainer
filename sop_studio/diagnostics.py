from __future__ import annotations
import importlib.metadata
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from .process import run

def ffmpeg() -> str | None:
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        return path if Path(path).is_file() else None
    except (ImportError, RuntimeError):
        return None

def diagnose(root: Path) -> dict:
    packages = {}
    for package in ('streamlit', 'pillow', 'pymupdf', 'python-docx', 'edge-tts', 'pyttsx3', 'imageio-ffmpeg'):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = 'not installed'
    gpu = []
    if shutil.which('nvidia-smi'):
        try:
            report = run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'], timeout=10)
            gpu = [line.strip() for line in report.splitlines() if line.strip()]
        except Exception as exc:
            gpu = [f'GPU query failed: {exc}']
    ram_gb = None
    if os.name == 'nt':
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(k, ctypes.c_ulonglong) for k in ('total_phys', 'avail_phys', 'total_page', 'avail_page', 'total_virtual', 'avail_virtual', 'extended')]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            ram_gb = round(status.total_phys / 1024**3, 1)
        except Exception:
            pass
    disk = shutil.disk_usage(root)
    return {'python': sys.version, 'platform': platform.platform(), 'cpu': platform.processor(),
            'cpu_count': os.cpu_count(), 'ram_gb': ram_gb, 'gpu': gpu,
            'free_disk_gb': round(disk.free / 1024**3, 2), 'ffmpeg': ffmpeg(),
            'packages': packages, 'render_device': 'CPU / libx264',
            'avatar_status': 'Not installed or benchmarked. Recorded presenter fallback available.',
            'benchmark': 'No avatar model benchmark performed on this machine.'}

if __name__ == '__main__':
    print(json.dumps(diagnose(Path.cwd()), indent=2))
