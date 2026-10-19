"""Build a portable source ZIP without environments, private projects or cached inputs."""
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ['app.py', 'app_workspace.py', 'engine.py', 'legacy_pro.py', 'requirements.txt', 'requirements-lock.txt', 'requirements-avatar.txt', 'requirements-avatar-lock.txt', 'INSTALL_AI_PRESENTER.bat',
           'README.md', 'START_WINDOWS.bat', 'INSTALL_WINDOWS.bat', 'DIAGNOSE_WINDOWS.bat', 'TEST_WINDOWS.bat',
           'CHANGELOG.md', '.streamlit', 'sop_studio', 'scripts', 'tests', 'examples', 'docs']

def package():
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    archive = destination / 'SOP_Trainer_AI_Presenter_0.7.0.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for entry in INCLUDE:
            path = ROOT / entry
            files = path.rglob('*') if path.is_dir() else [path]
            for file in files:
                if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                    if file.parent == ROOT/'examples'/'ai_presenter' and file.name.startswith('SOP_Training_'):
                        import json
                        index = file.parent/'composed_latest.json'
                        if index.exists():
                            current = Path(json.loads(index.read_text(encoding='utf-8'))[0]).stem
                            if not file.name.startswith(current+'.'):
                                continue
                    output.write(file, 'SOP_Trainer_AI/' + file.relative_to(ROOT).as_posix())
        for folder in ('approved_media', 'jobs', 'outputs', 'projects', 'models'):
            output.writestr(f'SOP_Trainer_AI/{folder}/.keep', '')
        output.write(ROOT/'approved_media'/'README.md', 'SOP_Trainer_AI/approved_media/README.md')
        for name in ('fictional_educator.png', 'fictional_lab_scientist.png', 'fictional_lab_technician.png', 'fictional_lab_scientist_gestures.png'):
            portrait = ROOT/'approved_media'/'presenters'/name
            if portrait.exists():
                output.write(portrait, 'SOP_Trainer_AI/approved_media/presenters/' + name)
        # Only engineering-created acceptance artifacts, never arbitrary user output.
        latest = ROOT / 'outputs' / 'acceptance' / 'latest.json'
        if latest.exists():
            import json
            video = Path(json.loads(latest.read_text(encoding='utf-8'))[0])
            for extension in ('.mp4', '.srt', '.vtt', '.txt', '.storyboard.json', '.json'):
                file = video.with_suffix(extension)
                if file.exists():
                    output.write(file, 'SOP_Trainer_AI/examples/acceptance/' + file.name)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum + '  ' + archive.name + '\n', encoding='ascii')
    with zipfile.ZipFile(archive) as check:
        if check.testzip():
            raise RuntimeError('Release ZIP integrity check failed.')
    print(f'{archive}\nSHA-256: {checksum}')

if __name__ == '__main__':
    package()
