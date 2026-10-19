"""Optional real SadTalker adapter. Never substitutes a static image for animation."""
from __future__ import annotations
import json
import os
import shutil
import time
from pathlib import Path
from .schema import digest, file_hash
from .process import run, check_cancel
from .storage import atomic_json, read_json
from .diagnostics import ffmpeg

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT/'external'/'SadTalker'
PYTHON = ROOT/'.avatar_venv'/'Scripts'/'python.exe'

def readiness() -> dict:
    files = [REPO/'inference.py', PYTHON, ROOT/'models'/'sadtalker'/'runtime.json',
             REPO/'checkpoints'/'SadTalker_V0.0.2_256.safetensors',
             REPO/'checkpoints'/'mapping_00109-model.pth.tar',
             REPO/'gfpgan'/'weights'/'alignment_WFLW_4HG.pth',
             REPO/'gfpgan'/'weights'/'detection_Resnet50_Final.pth']
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    benchmark = ROOT/'models'/'sadtalker'/'benchmark.json'
    return {'files_present':not missing, 'missing':missing,
            'verification':read_json(benchmark) if benchmark.exists() else None,
            'limitations':'Audio-driven face/head only. Body and hands remain static. Initial face model is 256 pixels.'}

def render_presenter(portrait: str, audio: str, device='auto', cancel_file=None, expression_scale=1.0, pose_style=0) -> tuple[Path, dict]:
    if device not in ('auto', 'cpu'):
        raise ValueError('Select auto GPU/CPU or CPU.')
    if not .5 <= float(expression_scale) <= 1.5 or not 0 <= int(pose_style) <= 45:
        raise ValueError('Presenter expression or pose setting is outside its supported range.')
    state = readiness()
    if not state['files_present']:
        raise RuntimeError('Presenter engine not installed. Missing: ' + ', '.join(state['missing']))
    portrait_path, audio_path = Path(portrait).resolve(), Path(audio).resolve()
    if not portrait_path.is_file() or not audio_path.is_file():
        raise ValueError('Presenter portrait and driving audio must exist.')
    from PIL import Image
    with Image.open(portrait_path) as image:
        if min(image.size) < 128 or max(image.size) > 4096:
            raise ValueError('Use a portrait between 128 and 4096 pixels on each side.')
        image.verify()
    from .composition import duration
    executable = ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg is required for presenter generation.')
    manifest = ROOT/'models'/'sadtalker'/'downloads.json'
    if not manifest.is_file():
        raise RuntimeError('Presenter model download manifest is missing. Complete the verified model setup first.')
    source_manifest = ROOT/'models'/'sadtalker'/'source.json'
    model_version = digest({'models':read_json(manifest), 'source':read_json(source_manifest) if source_manifest.exists() else None})
    key = digest({'portrait':file_hash(portrait_path), 'audio':file_hash(audio_path), 'engine':'SadTalker-v0.0.2-256',
                  'models':model_version, 'device':device, 'expression_scale':expression_scale, 'pose_style':pose_style})
    folder = ROOT/'cache'/'presenters'/key
    folder.mkdir(parents=True, exist_ok=True)
    # Normalize decoder input and reject overlong scenes instead of risking unbounded model memory.
    driving = folder/'driving.wav'
    if not driving.exists():
        run([executable,'-y','-loglevel','error','-i',audio_path,'-ar','16000','-ac','1',driving], cancel_file, timeout=120)
    runtime = read_json(ROOT/'models'/'sadtalker'/'runtime.json')
    limit = 10 if device == 'cpu' or not runtime.get('cuda_available') else 30
    if duration(driving) > limit:
        raise ValueError(f'AI presenter scenes on this device are limited to {limit} seconds. Split this narration into shorter scenes; no speech was truncated.')
    output = folder/'presenter.mp4'
    details = folder/'presenter.json'
    if output.exists() and details.exists():
        record = read_json(details)
        if record['output_sha256'] == file_hash(output):
            return output, record
    check_cancel(cancel_file)
    # Upstream invokes `ffmpeg` by name. A project-local copy avoids changing system PATH.
    bin_dir = ROOT/'external'/'bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    bridge = bin_dir/'ffmpeg.exe'
    if not bridge.exists():
        shutil.copyfile(executable, bridge)
    environment = dict(os.environ)
    environment['PATH'] = str(bin_dir)+os.pathsep+environment.get('PATH','')
    environment['IMAGEIO_FFMPEG_EXE'] = str(bridge)
    environment['OMP_NUM_THREADS'] = '2'
    environment['MKL_NUM_THREADS'] = '2'
    environment['SOP_AVATAR_STATS_PATH'] = str(folder/'runtime_stats.json')
    command = [PYTHON, ROOT/'scripts'/'run_sadtalker.py', '--source_image', portrait_path, '--driven_audio', driving,
               '--checkpoint_dir', REPO/'checkpoints', '--result_dir', folder/'inference',
               '--size','256','--batch_size','1','--preprocess','full','--still',
               '--expression_scale',str(expression_scale),'--pose_style',str(pose_style)]
    started = time.monotonic()
    fallback = False
    try:
        log = run(command+(['--cpu'] if device=='cpu' else []), cancel_file, timeout=3600, cwd=REPO, env=environment)
    except RuntimeError as exc:
        if device != 'auto' or 'out of memory' not in str(exc).lower():
            raise
        fallback = True
        log = run(command+['--cpu'], cancel_file, timeout=7200, cwd=REPO, env=environment)
    clips = list((folder/'inference').glob('*.mp4'))
    if not clips:
        raise RuntimeError('Presenter engine produced no video. Face detection or model inference failed.\n'+log[-1500:])
    selected = max(clips, key=lambda p:p.stat().st_mtime)
    run([executable,'-v','error','-i',selected,'-f','null','-'], cancel_file, timeout=300)
    shutil.copyfile(selected, output)
    (folder/'inference.log').write_text(log, encoding='utf-8')
    record = {'engine':'SadTalker', 'model':'v0.0.2 / 256', 'models_manifest_hash':model_version,
              'portrait_sha256':file_hash(portrait_path), 'audio_sha256':file_hash(audio_path),
              'output_sha256':file_hash(output), 'seconds_elapsed':round(time.monotonic()-started, 2),
              'requested_device':device, 'cpu_fallback':fallback, 'expression_scale':expression_scale,
              'pose_style':pose_style, 'body_motion':'static; not synthesized', 'review_status':'preview, review required'}
    if (folder/'runtime_stats.json').is_file():
        record['runtime_stats'] = read_json(folder/'runtime_stats.json')
    atomic_json(details, record)
    return output, record
