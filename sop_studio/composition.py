"""Frame-based CPU compositor; recorded presenters are not synthetic lip-sync."""
from __future__ import annotations
import json
import math
import shutil
import uuid
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from . import __version__
from .diagnostics import ffmpeg
from .process import run, check_cancel
from .schema import validate_scene, file_hash, now, LAYOUTS
from .speech import generate_cached
from .storage import atomic_json

ROOT = Path(__file__).resolve().parent.parent
PRESETS = {'720p landscape': (1280, 720), '1080p landscape': (1920, 1080), '1080p portrait': (1080, 1920)}

def duration(path, executable=None, cancel_file=None):
    path = Path(path)
    if path.suffix.lower() == '.wav':
        with wave.open(str(path), 'rb') as stream:
            return stream.getnframes() / stream.getframerate()
    probe = shutil.which('ffprobe')
    if probe:
        return float(run([probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', path], cancel_file, timeout=60).strip())
    raise ValueError('Decode non-WAV audio before measuring duration when FFprobe is unavailable.')

def stamp(seconds, vtt=False):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}{"." if vtt else ","}{ms%1000:03}'

def font(size):
    for path in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def wrap(draw, text, ft, max_width):
    lines, current = [], ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if draw.textbbox((0, 0), candidate, font=ft)[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines

def placeholder(row, dest, title):
    image = Image.new('RGB', (1280, 720), '#142e2a')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 28, 1252, 692), 22, outline='#6d9b83', width=3)
    draw.text((64, 58), title[:55], font=font(32), fill='#b7dca4')
    draw.text((64, 145), row['visual'], font=font(46), fill='white')
    for i, line in enumerate(wrap(draw, row['narration'], font(28), 1100)[:6]):
        draw.text((64, 250 + i * 42), line, font=font(28), fill='#dae7db')
    draw.text((64, 600), 'PLACEHOLDER — NOT A PROCEDURAL DEMONSTRATION', font=font(22), fill='#ffce91')
    image.save(dest)

def reference_overlay(dest, width, height, title, reference, accent='#246b50', brand=''):
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    band = max(74, int(height * .075))
    draw.rectangle((0, height-band, width, height), fill=(10, 30, 26, 225))
    draw.rectangle((0, height-band, width, height-band+5), fill=accent)
    size = max(18, int(width / 65))
    ft = font(size)
    for i, line in enumerate(wrap(draw, f'{brand + " | " if brand else ""}{title}  |  {reference}', ft, width-64)[:2]):
        draw.text((32, height-band+10+i*(size+4)), line, font=ft, fill='white')
    image.save(dest)

def caption_overlay(dest, width, height, text, style):
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    size = max(24, int(width / 36))
    while True:
        ft = font(size)
        lines = wrap(draw, text, ft, width - 100)
        if len(lines) * (size + 8) < height * .40 or size <= 14:
            break
        size -= 2
    bottom = height - max(74, int(height*.075)) - 16
    top = bottom - len(lines)*(size+8) - 20
    draw.rounded_rectangle((30, top, width-30, bottom), 12, fill=(0, 0, 0, 220))
    for i, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=ft)
        draw.text(((width-(box[2]-box[0]))/2, top+8+i*(size+8)), line, font=ft,
                  fill='#ffe38a' if style == 'High contrast' else 'white')
    image.save(dest)

def preflight(rows, media_map, presenter_path, preexisting_audio, strict_media=False):
    if not rows:
        raise ValueError('Create at least one scene before rendering.')
    if preexisting_audio is not None and len(preexisting_audio) != len(rows):
        raise ValueError('Provide exactly one audio file for each scene.')
    clean = []
    for i, row in enumerate(rows):
        legacy = 'scene_id' not in row and 'original_instruction' not in row
        valid = validate_scene(row, i)
        if not row.get('approved') or (not legacy and not valid.get('approved')):
            raise ValueError(f'Scene {i+1} requires review of its current content.')
        if legacy:
            valid.update(approved=True, review_status='legacy approval')
        media = row.get('media') or media_map.get(row.get('visual'), '')
        if media and not Path(media).is_file():
            raise ValueError(f'Scene {i+1}: attached media no longer exists.')
        if media and row.get('media_sha256') and file_hash(media) != row['media_sha256']:
            raise ValueError(f'Scene {i+1}: attached media changed since approval.')
        if row.get('presenter_sha256') and (not presenter_path or file_hash(presenter_path) != row['presenter_sha256']):
            raise ValueError(f'Scene {i+1}: presenter changed since approval.')
        if strict_media and not media:
            raise ValueError(f'Scene {i+1} is missing an approved demonstration.')
        if strict_media and row.get('generation') and (row.get('asset_review') or {}).get('status') != 'approved':
            raise ValueError(f'Scene {i+1}: generated visual needs technical approval before strict export.')
        if media and Path(media).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.mp4', '.mov', '.mkv', '.webm', '.avi'):
            raise ValueError(f'Scene {i+1}: unsupported demonstration format.')
        if presenter_path and valid['layout'] != LAYOUTS[0] and not Path(presenter_path).is_file():
            raise ValueError('Recorded presenter file is missing.')
        if preexisting_audio is not None and not Path(preexisting_audio[i]).is_file():
            raise ValueError(f'Scene {i+1}: narration audio is missing.')
        clean.append(valid)
    return clean

def render(rows, title, engine, voice, rate, presenter_path=None, media_map=None,
           output_dir=None, progress=None, preexisting_audio=None, *, preset='720p landscape', fps=30,
           cancel_file=None, job_dir=None, metadata=None, strict_media=False, pronunciation_map=None, avatar=None, production=None):
    """Return (MP4, SRT, manifest), preserving the original public call signature."""
    media_map = media_map or {}
    production = production or {}
    import re
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', production.get('accent', '#246b50')):
        raise ValueError('Brand accent must be a six-digit hex color.')
    if production.get('transition', 'Cut') not in ('Cut', 'Fade') or production.get('caption_style', 'Classic') not in ('Classic', 'High contrast'):
        raise ValueError('Unsupported transition or caption style.')
    rows = preflight(rows, media_map, presenter_path, preexisting_audio, strict_media)
    cloud = bool(avatar and avatar.get('provider') in ('heygen','synthesia','imported-cloud'))
    if cloud:
        from . import heygen, synthesia, cloud_import
        cloud_adapter = {'heygen':heygen,'synthesia':synthesia,'imported-cloud':cloud_import}[avatar['provider']]
        cloud_name = {'heygen':'HeyGen','synthesia':'Synthesia','imported-cloud':'Imported cloud'}[avatar['provider']]
        if not cloud_adapter.configured() or not avatar.get('cloud_authorized'):
            raise ValueError('Configure and authorize the selected cloud presenter first.')
    if avatar and not cloud:
        from .avatar import readiness
        if not readiness()['files_present']:
            raise RuntimeError('AI presenter engine setup is incomplete. Open Presenter studio for missing files.')
        if not avatar.get('portrait') or not Path(avatar['portrait']).is_file():
            raise ValueError('Select an AI presenter portrait first.')
        if avatar.get('portrait_sha256') != file_hash(avatar['portrait']):
            raise ValueError('AI presenter portrait changed. Select it again and re-review scenes.')
    if preset not in PRESETS or fps not in (25, 30):
        raise ValueError('Unsupported output preset or frame rate.')
    executable = ffmpeg()
    if not executable:
        raise RuntimeError('FFmpeg missing. Run INSTALL_WINDOWS.bat to install imageio-ffmpeg.')
    width, height = PRESETS[preset]
    job = Path(job_dir) if job_dir else ROOT / 'jobs' / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=True)
    out = Path(output_dir) if output_dir else ROOT / 'outputs'
    out.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(out).free < 256 * 1024**2:
        raise RuntimeError('Less than 256 MB free disk space. Free space before rendering.')
    clips, subtitles, vtt_cues, timeline = [], [], [], []
    frame_offset = 0
    for i, row in enumerate(rows):
        check_cancel(cancel_file)
        scene_presenter = presenter_path
        presenter_record = None
        if cloud:
            scene_presenter, original_audio, presenter_record = cloud_adapter.render_cloud(row['narration'], avatar, ROOT, cancel_file)
        else:
            original_audio = Path(preexisting_audio[i]) if preexisting_audio is not None else generate_cached(row['narration'], ROOT, engine, voice, rate, pronunciation_map, cancel_file)
        audio = job / f'normalized_{i:04}.wav'
        run([executable, '-y', '-loglevel', 'error', '-i', original_audio, '-vn', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-ac', '1', audio], cancel_file, timeout=300)
        audio_duration = duration(audio)
        if audio_duration <= 0:
            raise RuntimeError(f'Scene {i+1} narration audio is empty.')
        frames = max(1, math.ceil(audio_duration * fps))
        scene_duration = frames / fps
        from .editing import validate_cues
        cues = validate_cues(row.get('phrase_cues', []), audio_duration)
        if metadata:
            from .media import asset_current
            context = {'sop_id': metadata.get('sop_id', ''), 'metadata': metadata}
            for cue in cues:
                if cue.get('asset') and not asset_current(cue['asset'], row, context):
                    raise ValueError('Phrase visual does not match the current SOP revision or narration.')
        selected_media = row.get('media') or media_map.get(row['visual'], '')
        src = Path(selected_media) if selected_media else job / f'placeholder_{i:04}.png'
        if not selected_media:
            placeholder(row, src, title)
        if avatar and not cloud and row['layout'] != LAYOUTS[0]:
            from .avatar import render_presenter
            # Loudness normalization changes amplitude, not timing. Reuse the same cached
            # TTS waveform that drove the audition, avoiding another expensive animation.
            scene_presenter, presenter_record = render_presenter(avatar['portrait'], str(original_audio), avatar.get('device','auto'), cancel_file,
                avatar.get('expression_scale',1.0), avatar.get('pose_style',0))
        use_presenter = bool(scene_presenter and row['layout'] != LAYOUTS[0])
        source_video = src.suffix.lower() in ('.mp4', '.mov', '.mkv', '.webm', '.avi')
        command = [executable, '-y', '-loglevel', 'error', '-threads', '2', '-filter_complex_threads', '1']
        command += ['-stream_loop', '-1', '-ss', str(row.get('media_offset', 0)), '-i', src] if source_video else ['-loop', '1', '-framerate', str(fps), '-i', src]
        if use_presenter:
            command += ['-i', scene_presenter] if presenter_record else ['-stream_loop', '-1', '-i', scene_presenter]
        audio_index = 2 if use_presenter else 1
        command += ['-i', audio]
        overlay_index = audio_index + 1
        overlay = job / f'reference_{i:04}.png'
        reference_overlay(overlay, width, height, title, row['reference'], production.get('accent', '#246b50'), production.get('brand', '')[:80])
        command += ['-loop', '1', '-framerate', str(fps), '-i', overlay]
        next_input = overlay_index + 1
        visual_inputs, caption_inputs = [], []
        for cue in cues:
            if cue.get('asset'):
                path = Path(cue['asset']['path'])
                video = path.suffix.lower() in ('.mp4', '.mov', '.mkv', '.webm', '.avi')
                command += ['-stream_loop', '-1', '-i', path] if video else ['-loop', '1', '-framerate', str(fps), '-i', path]
                visual_inputs.append((next_input, cue))
                next_input += 1
        if production.get('burn_captions'):
            for ci, cue in enumerate(cues or [{'start': 0, 'end': audio_duration, 'text': row['narration']}]):
                cap = job / f'caption_{i}_{ci}.png'
                caption_overlay(cap, width, height, cue['text'], production.get('caption_style', 'Classic'))
                command += ['-loop', '1', '-framerate', str(fps), '-i', cap]
                caption_inputs.append((next_input, cue))
                next_input += 1
        def fit(index, w, h, name):
            hold = 'tpad=stop_mode=clone:stop_duration=1,' if presenter_record and index == 1 else ''
            return f'[{index}:v]setpts=PTS-STARTPTS,{hold}scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x142e2a,setsar=1,fps={fps},format=yuv420p[{name}]'
        if use_presenter and row['layout'] == 'Presenter full screen':
            filters = fit(1, width, height, 'canvas')
        elif use_presenter and row['layout'] == 'Presenter side-by-side':
            panel = (width // 2) // 2 * 2
            filters = fit(1, panel, height, 'presenter') + ';' + fit(0, width-panel, height, 'demo') + ';[presenter][demo]hstack=inputs=2[canvas]'
        elif use_presenter and row['layout'] == 'Presenter circular picture-in-picture':
            diameter = int(min(width, height)*.32)//2*2
            hold = 'tpad=stop_mode=clone:stop_duration=1,' if presenter_record else ''
            circle = f"[1:v]setpts=PTS-STARTPTS,{hold}scale={diameter}:{diameter}:force_original_aspect_ratio=increase,crop={diameter}:{diameter},setsar=1,fps={fps},format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(pow(X-W/2,2)+pow(Y-H/2,2),pow(W/2-2,2)),255,0)'[presenter]"
            filters = fit(0, width, height, 'demo')+';'+circle+';[demo][presenter]overlay=W-w-24:24[canvas]'
        elif use_presenter:
            pw, ph = (int(width * .30)//2*2, int(height * .30)//2*2)
            filters = fit(0, width, height, 'demo') + ';' + fit(1, pw, ph, 'presenter') + ';[demo][presenter]overlay=W-w-24:24[canvas]'
        else:
            filters = fit(0, width, height, 'canvas')
        current = 'canvas'
        for ci, (index, cue) in enumerate(visual_inputs):
            if use_presenter and row['layout'] != 'Presenter side-by-side':
                raise ValueError('Use side-by-side or demonstration full screen for phrase visual switching.')
            cw = (width - (width//2)//2*2) if use_presenter else width
            x = width-cw
            filters += f';[{index}:v]setpts=PTS-STARTPTS+{cue["start"]}/TB,scale={cw}:{height}:force_original_aspect_ratio=decrease,pad={cw}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x142e2a,setsar=1[phrase{ci}]'
            filters += f';[{current}][phrase{ci}]overlay={x}:0:enable=\'gte(t,{cue["start"]})*lt(t,{cue["end"]})\'[timed{ci}]'
            current = f'timed{ci}'
        band = max(74, int(height * .075))
        filters += f';[{current}]scale={width}:{height-band}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:0:color=0x142e2a[content]'
        filters += f';[{overlay_index}:v]format=rgba[reference];[content][reference]overlay=0:0[branded]'
        current = 'branded'
        for ci, (index, cue) in enumerate(caption_inputs):
            filters += f';[{current}][{index}:v]overlay=0:0:enable=\'gte(t,{cue["start"]})*lt(t,{cue["end"]})\'[captioned{ci}]'
            current = f'captioned{ci}'
        fade = min(.2, scene_duration/4)
        transition = f'fade=t=in:st=0:d={fade},fade=t=out:st={scene_duration-fade}:d={fade},' if production.get('transition') == 'Fade' else ''
        filters += f';[{current}]{transition}format=yuv420p[v]'
        # PCM intermediates avoid AAC encoder delay at every scene boundary.
        clip = job / f'clip_{i:04}.mkv'
        command += ['-filter_complex', filters, '-map', '[v]', '-map', f'{audio_index}:a:0',
                    '-af', 'apad', '-t', f'{scene_duration:.9f}', '-r', str(fps),
                    '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                    '-c:a', 'pcm_s16le', '-ar', '48000', clip]
        run(command, cancel_file)
        clips.append(clip)
        start, end = frame_offset/fps, (frame_offset+frames)/fps
        for cue in cues or [{'start': 0, 'end': scene_duration, 'text': row['narration']}]:
            subtitles.append(f'{len(subtitles)+1}\n{stamp(start+cue["start"])} --> {stamp(start+cue["end"])}\n{cue["text"]}\n')
            vtt_cues.append(f'{stamp(start+cue["start"], True)} --> {stamp(start+cue["end"], True)}\n{cue["text"]}\n')
        words_path = Path(str(original_audio) + '.words.json')
        words = json.loads(words_path.read_text(encoding='utf-8')) if words_path.exists() else []
        timeline.append({'scene': i+1, 'scene_id': row['scene_id'], 'start': start, 'end': end,
                         'start_frame': frame_offset, 'end_frame': frame_offset+frames,
                         'audio': {'path': str(original_audio), 'sha256': file_hash(original_audio), 'duration': audio_duration},
                         'words': [{**word, 'start': start+word['start'], 'end': start+word['end']} for word in words],
                         'alignment': 'TTS word boundaries' if words else 'scene boundaries only; no word alignment',
                         'demonstration': {'path': str(src), 'sha256': file_hash(src), 'offset': row['media_offset'], 'start': start, 'end': end, 'placeholder': not bool(selected_media), 'generation':row.get('generation'), 'asset_review':row.get('asset_review')},
                         'presenter': {'path': str(scene_presenter) if use_presenter else None, 'type': cloud_name+(' performance' if cloud_name=='Imported cloud' else ' cloud performance') if cloud else 'SadTalker audio-driven face' if presenter_record else 'recorded, not lip-synced', 'generation':presenter_record},
                         'caption': {'start': start, 'end': end, 'phrases': cues, 'timing_source': row.get('phrase_timing_source', 'manual audio review') if cues else 'scene boundaries'}, 'transition': production.get('transition', 'Cut'),
                         'reference': row['reference'], 'layout': row['layout']})
        frame_offset += frames
        atomic_json(job / 'timeline.partial.json', {'timeline': timeline})
        if progress:
            progress((i+1)/(len(rows)+1))
    check_cancel(cancel_file)
    playlist = job / 'concat.txt'
    playlist.write_text(''.join(f"file '{p.name}'\nduration {(item['end_frame']-item['start_frame'])/fps:.9f}\n" for p, item in zip(clips, timeline)), encoding='utf-8')
    base = out / f'SOP_Training_{job.name}'
    mp4, srt, manifest = base.with_suffix('.mp4'), base.with_suffix('.srt'), base.with_suffix('.json')
    staging = job / 'final.mp4'
    run([executable, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', playlist,
         '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-t', f'{frame_offset/fps:.9f}', '-movflags', '+faststart', staging], cancel_file)
    run([executable, '-v', 'error', '-i', staging, '-f', 'null', '-'], cancel_file)
    shutil.copyfile(staging, mp4)
    srt.write_text('\n'.join(subtitles), encoding='utf-8')
    vtt = base.with_suffix('.vtt')
    vtt.write_text('WEBVTT\n\n' + '\n'.join(vtt_cues), encoding='utf-8')
    script = base.with_suffix('.txt')
    script.write_text(title + '\n\n' + '\n\n'.join(f'{r["reference"]}\n{r["narration"]}' for r in rows), encoding='utf-8')
    plan = base.with_suffix('.storyboard.json')
    atomic_json(plan, {'title': title, 'scenes': rows, 'metadata': metadata or {}})
    atomic_json(manifest, {'title': title, 'created_at': now(), 'app_version': __version__, 'scenes': rows,
        'timeline': timeline, 'fps': fps, 'resolution': [width, height], 'duration_frames': frame_offset,
        'metadata': metadata or {}, 'speech': {'engine': cloud_name if cloud else engine, 'voice': avatar.get('voice_id','video original speech') if cloud else voice, 'rate': None if cloud else rate, 'pronunciation': {} if cloud else pronunciation_map or {}},
        'ffmpeg_version': run([executable, '-version'], timeout=10).splitlines()[0],
        'presenter_sha256': file_hash(presenter_path) if presenter_path else None,
        'artifacts': {p.name: {'path': str(p), 'sha256': file_hash(p), 'bytes': p.stat().st_size} for p in [mp4, srt, vtt, script, plan]},
        'release_status': 'review required', 'production': production,
        'avatar':avatar, 'warning': 'Human content review controls only; not regulatory validation or Part 11 compliance. AI facial animation requires playback review; recorded presenter footage is not automatically lip-synced.'})
    if progress:
        progress(1.0)
    return mp4, srt, manifest
