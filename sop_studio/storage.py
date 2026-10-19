"""Atomic local persistence with version snapshots; not a regulated audit trail."""
from __future__ import annotations
import json
import re
import os
import uuid
import time
from pathlib import Path
from .schema import validate_project, now, digest

def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers/antivirus can briefly hold the target open while a job polls status.
        for attempt in range(12):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(.01 * (attempt+1))
    finally:
        tmp.unlink(missing_ok=True)

def read_json(path: Path) -> dict:
    for attempt in range(12):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(.01 * (attempt+1))

class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, project_id: str) -> Path:
        if not re.fullmatch(r'[a-f0-9]{32}', project_id):
            raise ValueError('Invalid project ID.')
        return self.root / project_id

    def save(self, data: dict, actor: str = 'local operator', reason: str = 'Project saved') -> dict:
        project = validate_project(data)
        folder = self.folder(project['project_id'])
        project['saved_at'] = now()
        previous = folder / 'project.json'
        if previous.exists():
            prior = json.loads(previous.read_text(encoding='utf-8'))
            version = digest(prior)
            atomic_json(folder / 'history' / f'{version}.json', prior)
        project['history'] = project['history'] + [{'at': now(), 'actor': actor, 'reason': reason,
                                                   'content_hash': digest({k:v for k,v in project.items() if k != 'history'})}]
        atomic_json(previous, project)
        return project

    def load(self, project_id: str) -> dict:
        return validate_project(json.loads((self.folder(project_id) / 'project.json').read_text(encoding='utf-8')))

    def list(self) -> list[dict]:
        projects = []
        for path in self.root.glob('*/project.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                projects.append({k:data.get(k, '') for k in ('project_id', 'title', 'saved_at', 'sop_id')})
            except (OSError, ValueError):
                continue
        return sorted(projects, key=lambda p:p['saved_at'], reverse=True)

    def versions(self, project_id):
        versions = []
        for path in (self.folder(project_id) / 'history').glob('*.json'):
            try:
                data = validate_project(read_json(path))
                versions.append({'version': path.stem, 'saved_at': data.get('saved_at', ''),
                                 'title': data['title'], 'scenes': len(data['scenes'])})
            except (OSError, ValueError):
                continue
        return sorted(versions, key=lambda item: item['saved_at'], reverse=True)

    def restore(self, project_id, version):
        if not re.fullmatch(r'[a-f0-9]{64}', version):
            raise ValueError('Invalid version.')
        data = validate_project(read_json(self.folder(project_id) / 'history' / (version + '.json')))
        if data['project_id'] != project_id:
            raise ValueError('Snapshot belongs to another project.')
        return self.save(data, reason='Restored snapshot ' + version[:12])
