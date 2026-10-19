"""Download official SadTalker source into external/, without installing it globally."""
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
target = ROOT/'external'/'SadTalker'
if (target/'inference.py').is_file():
    print('Official source already present:', target)
else:
    url = 'https://codeload.github.com/OpenTalker/SadTalker/zip/refs/heads/main'
    print('Downloading official source archive, approximately 70 MB.', flush=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        blob = response.read(120*1024**2)
        if response.read(1):
            raise ValueError('Source archive exceeded 120 MB; inspect upstream changes before continuing.')
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 400*1024**2:
            raise ValueError('Expanded source exceeds 400 MB.')
        for item in archive.infolist():
            parts = Path(item.filename).parts[1:]
            if not parts:
                continue
            destination = target.joinpath(*parts).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise ValueError('Invalid archive path.')
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(item))
hashes = {p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
          for p in target.rglob('*.py')}
folder = ROOT/'models'/'sadtalker'
folder.mkdir(parents=True, exist_ok=True)
(folder/'source.json').write_text(json.dumps({'repository':'https://github.com/OpenTalker/SadTalker', 'reference':'main at download time', 'source_hashes':hashes}, indent=2), encoding='utf-8')
print('Source hashes recorded.')
