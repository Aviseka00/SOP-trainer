"""Import externally rendered cloud scenes with their original audio and exact script binding."""
from pathlib import Path
from .schema import digest, file_hash
from .diagnostics import ffmpeg
from .process import run
from .storage import atomic_json,read_json


def configured():
    return True


def render_cloud(text,config,root,cancel_file=None):
    if not config.get('cloud_authorized'):
        raise ValueError('Confirm permission to use the imported presenter clips.')
    clip=config.get('clips',{}).get(digest(text))
    if not clip:
        raise ValueError('No imported presenter clip matches this exact narration. Attach a matching cloud video in Presenter studio.')
    path=Path(clip['path']).resolve()
    if not path.is_relative_to((Path(root)/'approved_media').resolve()) or not path.is_file():
        raise ValueError('Imported presenter must be stored in the project media library.')
    if file_hash(path)!=clip.get('sha256'):
        raise ValueError('Imported presenter changed; attach and review it again.')
    folder=Path(root)/'cache'/'imported_presenters'/digest(clip)
    folder.mkdir(parents=True,exist_ok=True)
    audio,details=folder/'speech.wav',folder/'generation.json'
    if details.exists() and audio.exists():
        record=read_json(details)
        if file_hash(audio)==record['audio_sha256']:
            return path,audio,record
    executable=ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg is required to validate imported presenter speech.')
    run([executable,'-y','-v','error','-i',path,'-vn','-ar','48000','-ac','1',audio],cancel_file,timeout=300)
    run([executable,'-v','error','-i',path,'-f','null','-'],cancel_file,timeout=300)
    record={'engine':'Imported cloud performance','declared_provider':clip.get('provider','external'),
        'video_id':clip.get('video_id',''),'output_sha256':clip['sha256'],'audio_sha256':file_hash(audio),
        'narration_sha256':digest(text),'review_status':'playback review required',
        'provenance':'Locally attached cloud video; script binding is supplied by operator, not independently transcribed.'}
    atomic_json(details,record)
    return path,audio,record
