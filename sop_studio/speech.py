"""Speech adapters. The Windows worker selects an actual installed voice ID."""
from __future__ import annotations
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path
from .process import run
from .schema import digest

async def edge_voices() -> list[dict]:
    import edge_tts
    return await asyncio.wait_for(edge_tts.list_voices(), timeout=20)

async def edge_generate(text, path, voice, rate):
    import edge_tts
    timings = []
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
    with Path(path).open('wb') as stream:
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                stream.write(chunk['data'])
            elif chunk['type'] == 'WordBoundary':
                timings.append({'text': chunk['text'], 'start': chunk['offset'] / 10_000_000,
                                'end': (chunk['offset'] + chunk['duration']) / 10_000_000})
    Path(str(path) + '.words.json').write_text(json.dumps(timings, ensure_ascii=False), encoding='utf-8')

def pronunciation(text: str, mapping: dict[str, str]) -> str:
    for word in sorted(mapping, key=len, reverse=True):
        if not word or not isinstance(mapping[word], str):
            raise ValueError('Pronunciation dictionary must map nonempty terms to spoken text.')
        text = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', lambda _: mapping[word], text)
    return text

def installed_voices() -> list[dict]:
    result = run([sys.executable, '-m', 'sop_studio.speech', 'voices'], timeout=30)
    return json.loads(result)

def generate_cached(text: str, root: Path, engine: str, voice: str, rate,
                    pronunciation_map: dict | None = None, cancel_file: Path | None = None) -> Path:
    spoken = pronunciation(text, pronunciation_map or {})
    cache = root / 'cache' / 'speech'
    cache.mkdir(parents=True, exist_ok=True)
    key = digest({'text': spoken, 'engine': engine, 'voice': voice, 'rate': rate, 'version': 2})
    path = cache / f'{key}.{ "mp3" if engine == "Edge (online)" else "wav"}'
    if path.exists() and path.stat().st_size > 200:
        return path
    temporary = cache / f'{key}_{uuid.uuid4().hex}{path.suffix}'
    request = temporary.with_suffix('.request.json')
    request.write_text(json.dumps({'text': spoken, 'path': str(temporary), 'engine': engine, 'voice': voice, 'rate': rate}), encoding='utf-8')
    try:
        run([sys.executable, '-m', 'sop_studio.speech', 'generate', request], cancel_file, timeout=300)
        if not temporary.exists() or temporary.stat().st_size < 200:
            raise RuntimeError('Speech engine produced no usable audio.')
        temporary.replace(path)
        words = Path(str(temporary) + '.words.json')
        if words.exists():
            words.replace(Path(str(path) + '.words.json'))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        request.unlink(missing_ok=True)
        Path(str(temporary) + '.words.json').unlink(missing_ok=True)
    return path

def main():
    if sys.argv[1] == 'voices':
        import pyttsx3
        engine = pyttsx3.init()
        voices = [{'id': v.id, 'name': v.name, 'languages': [str(x) for x in v.languages]} for v in engine.getProperty('voices')]
        engine.stop()
        print(json.dumps(voices))
        return
    data = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if data['engine'] == 'Edge (online)':
        asyncio.run(edge_generate(data['text'], data['path'], data['voice'], data['rate']))
    elif data['engine'] == 'Windows offline':
        import pyttsx3
        engine = pyttsx3.init()
        ids = [v.id for v in engine.getProperty('voices')]
        if data['voice'] and data['voice'] not in ids:
            raise ValueError('Selected Windows voice is not installed. Select a listed installed voice.')
        if data['voice']:
            engine.setProperty('voice', data['voice'])
        engine.setProperty('rate', int(data['rate']))
        engine.save_to_file(data['text'], data['path'])
        engine.runAndWait()
        engine.stop()
    else:
        raise ValueError('Unsupported speech engine.')

if __name__ == '__main__':
    main()
