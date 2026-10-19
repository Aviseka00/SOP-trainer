"""Authorized HeyGen voice cloning from locally extracted media samples."""
import base64
import json
import math
import re
import wave
from pathlib import Path
from . import heygen
from .diagnostics import ffmpeg
from .process import run
from .schema import digest, file_hash, now
from .storage import atomic_json, read_json

EXTENSIONS = ['mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v', 'wmv', 'mpeg', 'mpg', '3gp', 'flv', 'ts', 'mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'opus', 'wma']

def extract_sample(source, destination, start=0, seconds=60):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, seconds)) or start < 0 or not 5 <= seconds <= 180:
        raise ValueError('Choose a nonnegative start and a sample length of 5–180 seconds.')
    executable = ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg is required to extract the voice sample.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.partial.wav')
    try:
        run([executable, '-y', '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe', '-ss', str(start), '-i', Path(source),
             '-t', str(seconds), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', temporary], timeout=180)
        with wave.open(str(temporary), 'rb') as stream:
            duration = stream.getnframes()/stream.getframerate()
            data = stream.readframes(stream.getnframes())
        if duration < 5:
            raise ValueError('At least five seconds of audio is required. Choose an earlier start or a longer recording.')
        import array
        samples = array.array('h', data)
        rms = math.sqrt(sum(v*v for v in samples)/max(1, len(samples)))
        if rms < 20:
            raise ValueError('The sample is silent or too quiet. Choose clear speech from one speaker.')
        temporary.replace(destination)
        return {'path': str(destination), 'sha256': file_hash(destination), 'duration': duration,
                'start': start, 'source_sha256': file_hash(source), 'rms_dbfs': round(20*math.log10(rms/32768), 1)}
    finally:
        temporary.unlink(missing_ok=True)

def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{5,150}', value):
        raise ValueError('Invalid provider voice ID.')
    return value

def create(sample, name, speaker, consent, root, key=None):
    if consent is not True or not speaker.strip():
        raise ValueError('Record the speaker name and explicit authorization before cloning.')
    if not 1 <= len(name.strip()) <= 64:
        raise ValueError('Use a voice name of 1–64 characters.')
    path = Path(sample['path'])
    if file_hash(path) != sample['sha256'] or path.stat().st_size > 16*1024*1024:
        raise ValueError('Voice sample changed or exceeds the provider inline limit.')
    identity = {'sample': sample['sha256'], 'name': name.strip(), 'speaker': speaker.strip()}
    folder = Path(root)/'cache'/'voice_clones'/digest(identity)
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder/'submission.json'
    if journal.exists():
        previous = read_json(journal)
        if previous.get('voice_id'):
            return previous
        raise RuntimeError('Previous clone submission has an uncertain outcome. Check the HeyGen dashboard before submitting again.')
    payload = {'mode': 'instant', 'name': name.strip(), 'similarity': 'max', 'remove_background_noise': True,
               'audio': [{'type': 'base64', 'media_type': 'audio/wav', 'data': base64.b64encode(path.read_bytes()).decode('ascii')}]}
    record = {**identity, 'consent': True, 'consented_at': now(), 'status': 'submitting'}
    with journal.open('x', encoding='utf-8') as stream:
        json.dump(record, stream)
    result = heygen.api('models/audio/voices', payload, key=key)
    record.update(voice_id=valid_id(result.get('voice_id')), status='PENDING')
    atomic_json(journal, record)
    return record

def status(voice_id, key=None):
    return heygen.api('models/audio/voices/' + valid_id(voice_id), key=key)

def synthesize(text, voice_id, root, language='', key=None, cancel_file=None):
    from .process import check_cancel
    check_cancel(cancel_file)
    valid_id(voice_id)
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 5000:
        raise ValueError('Cloned-voice speech requires 1–5,000 characters per scene. Split longer scenes.')
    payload = {'model': 'heygen-voice-1', 'voice_id': voice_id, 'text': text, 'expressiveness_boost': .5}
    if language:
        payload['language'] = language
    folder = Path(root)/'cache'/'clone_speech'/digest(payload)
    folder.mkdir(parents=True, exist_ok=True)
    record_path, audio = folder/'speech.json', folder/'speech.wav'
    if record_path.exists():
        record = read_json(record_path)
        if audio.exists() and file_hash(audio) == record.get('sha256'):
            return record
    journal = folder/'submission.json'
    if journal.exists():
        submission = read_json(journal)
        if not submission.get('audio_url'):
            raise RuntimeError('Previous speech submission has an uncertain outcome. Check HeyGen before retrying; it will not be submitted again automatically.')
        result = submission
    else:
        with journal.open('x', encoding='utf-8') as stream:
            json.dump({'status': 'submitting'}, stream)
        result = heygen.api('models/audio/tts', payload, key=key)
        atomic_json(journal, {'audio_url': result.get('audio_url', ''), 'status': 'generated'})
    if not heygen.trusted_media(result.get('audio_url', '')):
        raise ValueError('Provider returned an unsupported speech URL.')
    heygen.download(result['audio_url'], audio, cancel_file)
    with wave.open(str(audio), 'rb') as stream:
        if stream.getnframes() <= 0:
            raise ValueError('Provider returned empty speech.')
    import time
    record = {'audio_url': result['audio_url'], 'path': str(audio), 'sha256': file_hash(audio), 'created': time.time(), 'voice_id': voice_id}
    atomic_json(record_path, record)
    return record
