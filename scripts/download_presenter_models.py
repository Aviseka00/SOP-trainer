"""Explicit SadTalker model setup. Official release URLs; records hashes and sizes."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def download(url, target, expected_digest=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if expected_digest and hashlib.sha256(target.read_bytes()).hexdigest() != expected_digest:
            raise ValueError('Existing model checksum mismatch: ' + target.name)
        return
    partial = target.with_suffix(target.suffix+'.part')
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as stream:
        total = response.headers.get('Content-Length', 'unknown')
        print(f'Downloading {target.name}: {total} bytes', flush=True)
        next_report = 32 * 1024**2
        while True:
            chunk = response.read(1024**2)
            if not chunk:
                break
            stream.write(chunk)
            h.update(chunk)
            size += len(chunk)
            if size >= next_report:
                print(f'{target.name}: {size//1024**2} MB received', flush=True)
                next_report += 32*1024**2
    if expected_digest and h.hexdigest() != expected_digest:
        raise ValueError('Downloaded model checksum mismatch: ' + target.name)
    partial.replace(target)
    return size, h.hexdigest()

def main():
    if '--download' not in sys.argv:
        raise SystemExit('Run with --download to explicitly download approximately 1 GB of presenter weights. Runtime packages require additional disk space. See docs/PRESENTER.md for licenses and limitations.')
    headers = {'User-Agent':'SOP-Trainer-Studio-model-setup'}
    req = urllib.request.Request('https://api.github.com/repos/OpenTalker/SadTalker/releases/tags/v0.0.2-rc', headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        release = json.load(response)
    folder = ROOT/'external'/'SadTalker'
    names = ['SadTalker_V0.0.2_256.safetensors', 'mapping_00109-model.pth.tar']
    items = []
    for name in names:
        asset = next(a for a in release['assets'] if a['name'] == name)
        signature = asset.get('digest') or ''
        items.append((asset['browser_download_url'], folder/'checkpoints'/name,
                      signature.split(':',1)[1] if signature.startswith('sha256:') else None))
    for name, release_tag in [('alignment_WFLW_4HG.pth','v0.1.0'), ('detection_Resnet50_Final.pth','v0.1.0')]:
        items.append((f'https://github.com/xinntao/facexlib/releases/download/{release_tag}/{name}', folder/'gfpgan'/'weights'/name, None))
    records = []
    for url, path, expected in items:
        download(url, path, expected)
        records.append({'url':url, 'path':str(path), 'bytes':path.stat().st_size,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'upstream_digest_verified':bool(expected)})
    (ROOT/'models'/'sadtalker').mkdir(parents=True, exist_ok=True)
    (ROOT/'models'/'sadtalker'/'downloads.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print('Presenter model downloads complete.', flush=True)

if __name__ == '__main__':
    main()
