"""Out-of-process rendering and disk-backed state survive Streamlit reruns."""
from __future__ import annotations
import json
import subprocess
import sys
import uuid
from pathlib import Path
from .storage import atomic_json, read_json
from .schema import now
from .process import RenderCancelled

ROOT = Path(__file__).resolve().parent.parent
_workers = {}

def start(request: dict, environment: dict | None = None) -> Path:
    from .credentials import NAMES
    import os
    provider = 'kling' if request.get('task')=='generate_visuals' and request.get('provider')=='kling' else (request.get('avatar') or {}).get('provider')
    required_key = {'heygen':'HEYGEN_API_KEY','synthesia':'SYNTHESIA_API_KEY','kling':'KLING_API_KEY'}.get(provider)
    if environment and (not set(environment).issubset(NAMES) or not all(isinstance(v,str) for v in environment.values())):
        raise ValueError('Unsupported worker credential configuration.')
    worker_env = {k:v for k,v in os.environ.items() if k not in NAMES or k==required_key}
    if environment and required_key in environment:
        worker_env[required_key] = environment[required_key]
    folder = ROOT / 'jobs' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    atomic_json(folder / 'request.json', request)
    atomic_json(folder / 'status.json', {'state': 'queued', 'progress': 0, 'updated_at': now()})
    with (folder / 'worker.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, '-m', 'sop_studio.jobs', str(folder)], cwd=ROOT,
                                   stdout=log, stderr=log, env=worker_env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    atomic_json(folder / 'process.json', {'pid': process.pid})
    _workers[folder.name] = process
    return folder

def status(folder: Path) -> dict:
    folder = Path(folder).resolve()
    if folder.parent != (ROOT / 'jobs').resolve():
        raise ValueError('Invalid job directory.')
    data = read_json(folder / 'status.json')
    if data['state'] not in ('queued', 'running') and folder.name in _workers:
        child = _workers[folder.name]
        try:
            child.wait(timeout=1)
            del _workers[folder.name]
        except subprocess.TimeoutExpired:
            pass
    if data['state'] in ('queued', 'running'):
        try:
            pid = read_json(folder / 'process.json')['pid']
            if sys.platform == 'win32':
                import ctypes
                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                else:
                    data.update(state='interrupted', error='Worker is no longer running. Start a new render; cached speech will be reused.')
            else:
                import os
                os.kill(pid, 0)
        except (OSError, ValueError, KeyError):
            data.update(state='interrupted', error='Worker process could not be found.')
    return data

def cancel(folder: Path):
    folder = Path(folder).resolve()
    if folder.parent != (ROOT / 'jobs').resolve():
        raise ValueError('Invalid job directory.')
    (folder / 'cancel').touch()

def worker(folder: Path):
    import os
    atomic_json(folder/'process.json',{'pid':os.getpid()})
    from .composition import render
    def update(state, progress=0, **extra):
        atomic_json(folder / 'status.json', {'state': state, 'progress': progress, 'updated_at': now(), **extra})
    try:
        request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
        update('running')
        if request.get('task') == 'cloud_audition':
            from . import heygen, synthesia
            config = request['avatar']
            adapter = {'heygen': heygen, 'synthesia': synthesia}.get(config.get('provider'))
            if adapter is None:
                raise ValueError('Select HeyGen or Synthesia for a cloud audition.')
            video, audio, record = adapter.render_cloud(request['text'], config, ROOT, folder/'cancel')
            update('complete', 1, video=str(video), audio=str(audio), generation=record)
            return
        if request.get('task') == 'avatar_preview':
            from .avatar import render_presenter
            from .speech import generate_cached
            audio = generate_cached(request['text'], ROOT, request['engine'], request['voice'], request['rate'], request.get('pronunciation'), folder/'cancel')
            video, record = render_presenter(request['portrait'], str(audio), request.get('device','auto'), folder/'cancel', request.get('expression_scale',1.0), request.get('pose_style',0))
            update('complete', 1, video=str(video), generation=record)
            return
        if request.get('task') == 'generate_visuals':
            from .visuals import generate
            from .media import MediaLibrary, visual_content_hash
            from .schema import validate_scene
            from .process import check_cancel
            library = MediaLibrary(ROOT / 'approved_media')
            results = []
            scenes = request['scenes']
            if not isinstance(scenes, list) or not 1 <= len(scenes) <= 2000:
                raise ValueError('Select between 1 and 2,000 scenes.')
            for i, raw in enumerate(scenes):
                check_cancel(folder/'cancel')
                scene = validate_scene(raw, i)
                if request.get('provider') == 'kling':
                    from .kling import generate as generate_kling
                    import shutil
                    generated = generate_kling(scene, ROOT, request['provider_config'], folder/'cancel')
                    destination = ROOT/'approved_media'/('kling_'+generated['sha256']+'.mp4')
                    if not destination.exists():
                        shutil.copyfile(generated['path'],destination)
                    generated = {**generated,'path':str(destination)}
                else:
                    generated = generate(scene, ROOT/'approved_media', request['mode'], request['template'], folder/'cancel')
                generated['scene_content_hash'] = visual_content_hash(scene)
                record = library.add(generated['path'], scene['visual'], f'{generated["template"]} — scene {i+1}',
                    'Generated media: ' + generated['generator'],
                    'Provider-generated draft clip; confirm provider terms and source rights.' if request.get('provider')=='kling' else 'Generated schematic; source document usage rights remain with its owner.', request['sop_id'], request['revision'], generation=generated)
                results.append({'scene_id':scene['scene_id'], 'record':record})
                atomic_json(folder/'visuals.partial.json', {'results':results})
                update('running', (i+1)/len(scenes), completed_scenes=i+1)
            update('complete', 1, results=results)
            return
        files = render(**request, job_dir=folder, cancel_file=folder / 'cancel', progress=lambda p:update('running', p))
        update('complete', 1, files=[str(p) for p in files])
    except RenderCancelled as exc:
        update('cancelled', error=str(exc))
    except BaseException as exc:
        import traceback
        traceback.print_exc()
        update('failed', error=f'{type(exc).__name__}: {exc}')

if __name__ == '__main__':
    worker(Path(sys.argv[1]))
