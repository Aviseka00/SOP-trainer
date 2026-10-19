"""Optional HeyGen v3 API adapter. Credentials come only from the process environment."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from .schema import digest, file_hash
from .storage import atomic_json, read_json
from .process import run, check_cancel
from .diagnostics import ffmpeg
from .cloud_io import https_handler

DEFAULT_SCIENTIST = 'b8e355741ea5b8e72a12fc8bda3c7d29'
DEFAULT_VOICE = '09c3d65e44e247dd8b78a97a903feb58'
MOTION = 'Maintain natural camera eye contact and blinking. Use calm open-palm explanatory hand gestures timed to spoken phrases. Relax hands between phrases. Avoid excessive movement.'


def configured():
    return bool(os.environ.get('HEYGEN_API_KEY', '').strip())


def api(route, payload=None, key=None):
    key = key or os.environ.get('HEYGEN_API_KEY', '').strip()
    if not key:
        raise ValueError('Set HEYGEN_API_KEY in the app process environment, then restart the app. The chat connection does not supply an API key.')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request('https://api.heygen.com/v3/'+route,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'X-Api-Key':key, 'Content-Type':'application/json', **({'Idempotency-Key':digest(payload)} if payload is not None else {})})
    try:
        with urllib.request.build_opener(NoRedirect, https_handler()).open(request, timeout=60) as response:
            result = json.loads(response.read(4*1024*1024))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HeyGen API returned HTTP {exc.code}. Check API access and credits. A submission is never retried automatically.') from None
    except (OSError, ValueError):
        raise RuntimeError('HeyGen API connection failed or returned invalid JSON. Check the saved submission before retrying.') from None
    return result.get('data', result)


def trusted_media(url):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return parsed.scheme == 'https' and not parsed.username and not parsed.password and parsed.port in (None,443) and any(host == d or host.endswith('.'+d) for d in ('heygen.ai','heygen.com'))


def download(url, output, cancel_file=None):
    if not trusted_media(url):
        raise ValueError('HeyGen returned an unsupported video host. Download through the provider dashboard instead.')
    class MediaRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not trusted_media(newurl):
                raise ValueError('Unsupported media redirect.')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    temporary = output.with_suffix('.partial')
    try:
        with urllib.request.build_opener(MediaRedirect, https_handler()).open(url, timeout=120) as source, temporary.open('wb') as target:
            total = 0
            while True:
                check_cancel(cancel_file)
                chunk = source.read(1024*1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 500*1024*1024:
                    raise ValueError('Presenter video exceeds the 500 MB download limit.')
                target.write(chunk)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def render_cloud(text, config, root, cancel_file=None):
    """Return the original provider video AND its own speech; never replace its audio."""
    if not configured() or not config.get('cloud_authorized'):
        raise ValueError('Configure the HeyGen API key and explicitly enable cloud narration submission in Presenter studio.')
    if config.get('native_voice_clone') and not config.get('voice_consent'):
        raise ValueError('Record speaker authorization in Voice studio before using a cloned voice.')
    for field in ('avatar_id','voice_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{5,150}', config.get(field,'')):
            raise ValueError('Invalid HeyGen '+field)
    if not text.strip() or len(text) > 20000:
        raise ValueError('Cloud narration must contain 1–20,000 characters.')
    payload = {'type':'avatar', 'avatar_id':config['avatar_id'], 'voice_id':config['voice_id'], 'script':text,
               'engine':{'type':'avatar_iv'}, 'resolution':'720p', 'aspect_ratio':'16:9',
               'motion_prompt':config.get('motion_prompt',MOTION), 'expressiveness':'medium',
               'voice_settings':{'locale':config.get('locale','en-IN')}, 'title':'SOP training scene'}
    folder = Path(root)/'cache'/'heygen'/(digest({'payload': payload, 'cloned_audio': True}) if config.get('native_voice_clone') else digest(payload))
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder/'submission.json'
    record_file = folder/'generation.json'
    video, audio = folder/'presenter.mp4', folder/'speech.wav'
    if record_file.exists() and video.exists() and audio.exists():
        record = read_json(record_file)
        if record['output_sha256'] == file_hash(video) and record['audio_sha256'] == file_hash(audio):
            return video, audio, record
    if journal.exists():
        submission = read_json(journal)
        if not submission.get('video_id'):
            raise RuntimeError('Previous cloud submission has an unknown outcome. Check HeyGen before creating another job. Journal: '+str(journal))
    else:
        if config.get('native_voice_clone'):
            from .voice_clone import synthesize
            speech = synthesize(text, config['voice_id'], root, language=config.get('locale', ''), cancel_file=cancel_file)
            payload.pop('script')
            payload.pop('voice_id')
            payload.pop('voice_settings')
            payload['audio_url'] = speech['audio_url']
        # Record intent BEFORE the paid POST; an uncertain response must not cause duplicate billing.
        try:
            with journal.open('x', encoding='utf-8') as stream:
                json.dump({'status':'submitting', 'payload_hash':digest(payload)}, stream)
        except FileExistsError:
            raise RuntimeError('Another cloud submission started for this scene. Resume from its saved job after it receives a video ID.') from None
        submission = api('videos', payload)
        if not isinstance(submission, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', submission.get('video_id','')):
            raise RuntimeError('HeyGen returned no video ID; check the provider dashboard before retrying.')
        atomic_json(journal, {'video_id':submission['video_id'], 'status':'submitted'})
    deadline = time.monotonic()+1800
    while time.monotonic() < deadline:
        check_cancel(cancel_file)
        state = api('videos/'+submission['video_id'])
        if state.get('status') in ('failed','cancelled'):
            raise RuntimeError('HeyGen presenter job '+state['status']+'. Review the provider dashboard; it will not be resubmitted automatically.')
        if state.get('status') == 'completed':
            download(state['video_url'], video, cancel_file)
            executable = ffmpeg()
            if not executable:
                raise RuntimeError('FFmpeg is required to decode cloud presenter speech.')
            run([executable,'-y','-v','error','-i',video,'-vn','-ar','48000','-ac','1',audio], cancel_file, timeout=300)
            run([executable,'-v','error','-i',video,'-f','null','-'], cancel_file, timeout=300)
            record = {'engine':'HeyGen Avatar IV', 'video_id':submission['video_id'], 'payload_sha256':digest(payload),
                      'output_sha256':file_hash(video), 'audio_sha256':file_hash(audio),
                      'body_motion':'provider synthesized; playback review required', 'review_status':'draft'}
            atomic_json(record_file, record)
            return video, audio, record
        for _ in range(30):
            check_cancel(cancel_file)
            time.sleep(1)
    raise RuntimeError('HeyGen is still processing. Resume rendering to reuse the saved video ID without another submission.')
