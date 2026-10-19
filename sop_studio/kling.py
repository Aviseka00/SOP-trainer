"""Kling official text-to-video API for contextual, draft demonstration clips."""
import os
from pathlib import Path
from . import cloud_io
from .schema import digest, file_hash
from .storage import read_json, atomic_json
from .process import run
from .diagnostics import ffmpeg

MODELS = ('kling-v2-6', 'kling-v2-5-turbo')


def configured():
    return bool(os.environ.get('KLING_API_KEY','').strip())


def api(route, payload=None, key=None):
    secret = key or os.environ.get('KLING_API_KEY','').strip()
    if not secret:
        raise ValueError('Configure a Kling developer API key in AI providers. Website passwords are not API keys.')
    response = cloud_io.request('https://api-singapore.klingai.com/v1/'+route, 'Bearer '+secret, payload)
    if response.get('code') != 0 or not isinstance(response.get('data'), (dict,list)):
        raise RuntimeError('Kling rejected the request. Check developer access, model entitlement and credits in the provider dashboard.')
    return response['data']


def generate(scene, root, config, cancel_file=None):
    if not configured() or not config.get('cloud_authorized'):
        raise ValueError('Configure Kling credentials and authorize cloud visual generation first.')
    model = config.get('model','kling-v2-6')
    duration = str(config.get('duration',5))
    if model not in MODELS or duration not in ('5','10'):
        raise ValueError('Unsupported Kling model or duration.')
    context = scene.get('visual_description') or scene['narration']
    prompt = ('Create a clear laboratory training concept clip. Depict only the supplied source context, with restrained camera motion and no invented equipment labels, quantities or procedural steps. '
              'For prohibited actions show a conceptual warning rather than demonstrating the prohibited action. No speech, music or on-screen text. Source context: '+context)
    if len(prompt)>2500:
        raise ValueError('Shorten the animation context to fit the Kling prompt limit; no content was silently truncated.')
    payload = {'model_name':model, 'prompt':prompt, 'negative_prompt':'distorted anatomy, illegible text, invented labels',
               'duration':duration, 'mode':'pro', 'sound':'off', 'aspect_ratio':'16:9'}
    folder = Path(root)/'cache'/'kling'/digest(payload)
    details, video = folder/'generation.json', folder/'video.mp4'
    if details.exists() and video.exists():
        record = read_json(details)
        if record['sha256'] == file_hash(video):
            return record
    video, record = cloud_io.task(root,'kling',payload,lambda p:api('videos/text2video',p),lambda i:api('videos/text2video/'+i),
        lambda r:r.get('task_id'),lambda r:r.get('task_status'),('succeed',),('failed',),
        lambda r:r['task_result']['videos'][0]['url'],('klingai.com','kwimgs.com','kwai.net'),cancel_file)
    executable = ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg is required to validate generated clips.')
    run([executable,'-v','error','-i',video,'-f','null','-'],cancel_file,timeout=300)
    record.update(path=str(video), sha256=file_hash(video), generator='Kling official API / '+model,
                  mode='Animation', template='Kling contextual clip', model=model, prompt=prompt,
                  duration_seconds=int(duration), review_status='draft; inspect procedure fidelity')
    atomic_json(details,record)
    return record
