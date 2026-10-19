"""Optional Synthesia v2 presenter; keep the returned video's original speech."""
import os
import re
from pathlib import Path
from . import cloud_io
from .diagnostics import ffmpeg
from .schema import digest, file_hash
from .storage import atomic_json, read_json
from .process import run


def configured():
    return bool(os.environ.get('SYNTHESIA_API_KEY','').strip())


def api(route, payload=None, key=None):
    secret = key or os.environ.get('SYNTHESIA_API_KEY','').strip()
    if not secret:
        raise ValueError('Configure your Synthesia Legacy (v2) API key in AI providers.')
    return cloud_io.request('https://api.synthesia.io/v2/'+route, secret, payload)


def render_cloud(text, config, root, cancel_file=None):
    if not configured() or not config.get('cloud_authorized'):
        raise ValueError('Configure and authorize Synthesia before rendering.')
    avatar_id = config.get('avatar_id','')
    if not re.fullmatch(r'[A-Za-z0-9_:.-]{1,200}', avatar_id) or not text.strip() or len(text)>20000:
        raise ValueError('Select a valid accessible Synthesia avatar and nonempty speech under 20,000 characters.')
    payload = {'title':'SOP training scene', 'visibility':'private', 'aspectRatio':'16:9',
               'test':bool(config.get('test_mode',True)),
               'input':[{'scriptText':text, 'avatar':avatar_id, 'background':'off_white'}]}
    folder = Path(root)/'cache'/'synthesia'/digest(payload)
    video, audio, details = folder/'video.mp4', folder/'speech.wav', folder/'generation.json'
    if details.exists() and video.exists() and audio.exists():
        record = read_json(details)
        if record['output_sha256']==file_hash(video) and record['audio_sha256']==file_hash(audio):
            return video,audio,record
    video, record = cloud_io.task(root, 'synthesia', payload, lambda p:api('videos',p), lambda i:api('videos/'+i),
        lambda r:r.get('id'), lambda r:r.get('status'), ('complete',), ('failed','error','rejected'),
        lambda r:r['download'], ('synthesia.io',), cancel_file)
    executable = ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg is required for Synthesia composition.')
    run([executable,'-y','-v','error','-i',video,'-vn','-ar','48000','-ac','1',audio], cancel_file, timeout=300)
    run([executable,'-v','error','-i',video,'-f','null','-'], cancel_file, timeout=300)
    record.update(engine='Synthesia', output_sha256=file_hash(video), audio_sha256=file_hash(audio),
                  review_status='draft', test_mode=payload['test'], body_motion='provider performance; not independently verified')
    atomic_json(details,record)
    return video,audio,record
