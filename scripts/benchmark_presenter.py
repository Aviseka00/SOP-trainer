"""Actual narrated presenter test; never writes success without a decoded model output."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sop_studio.avatar import render_presenter, readiness
from sop_studio.speech import installed_voices, generate_cached
from sop_studio.composition import ROOT
from sop_studio.storage import atomic_json

if __name__ == '__main__':
    if not readiness()['files_present']:
        raise SystemExit('Presenter setup incomplete: ' + ', '.join(readiness()['missing']))
    text = 'Welcome to SOP training.'
    voices = installed_voices()
    if not voices:
        raise SystemExit('A Windows voice is required for the measured speech-driven test.')
    audio = generate_cached(text, ROOT, 'Windows offline', voices[0]['id'], 155)
    video, record = render_presenter(str(ROOT/'approved_media'/'presenters'/'fictional_educator.png'), str(audio), device='cpu')
    record.update(test_text=text, output=str(video), quality_review='Not certified; inspect mouth, eyes, teeth and alignment manually.')
    import imageio_ffmpeg
    frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(video))
    record.update(output_frames=frames, output_duration_seconds=seconds,
                  render_seconds_per_video_second=round(record['seconds_elapsed']/seconds,2))
    atomic_json(ROOT/'models'/'sadtalker'/'benchmark.json', record)
    print(json.dumps(record, indent=2))
