"""Small synthetic media fixtures; no downloaded or private recordings required."""
from pathlib import Path
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run

def presenter_clip(root):
    folder = Path(root)/'.test_tmp'
    folder.mkdir(parents=True, exist_ok=True)
    video = folder/'synthetic_presenter_fixture.mp4'
    if not video.exists():
        run([ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10',
             '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '1',
             '-c:v', 'libx264', '-c:a', 'aac', video])
    return video
