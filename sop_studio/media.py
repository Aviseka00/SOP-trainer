"""Revision-aware local asset metadata and deterministic topic retrieval."""
from __future__ import annotations
import uuid
from pathlib import Path
from .schema import file_hash, now, digest
from .storage import atomic_json

def safe_media(path: str, root: Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError('Media must be an existing file in the approved_media library.')
    return resolved

class MediaLibrary:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def add(self, path: str, topic: str, description: str, source: str, license: str,
            sop_id: str = '', revision: str = '', reviewer: str = '', notes: str = '', generation: dict | None = None) -> dict:
        path = safe_media(path, self.root)
        record = {'asset_id': uuid.uuid4().hex, 'path': str(path), 'topic': topic,
                  'description': description, 'source': source, 'license': license,
                  'sop_id': sop_id, 'revision': revision, 'reviewer': reviewer,
                  'review_notes': notes, 'sha256': file_hash(path), 'created_at': now(),
                  'status': 'approved' if reviewer.strip() and source.strip() and license.strip() else 'draft'}
        if generation:
            record.update(generation=generation, status='draft', reviewer='')
        atomic_json(self.root / 'catalog' / f'{record["asset_id"]}.json', record)
        return record

    def review(self, record: dict, reviewer: str, notes: str) -> dict:
        if not reviewer.strip() or not notes.strip():
            raise ValueError('A technical reviewer and review notes are required.')
        safe_media(record['path'], self.root)
        if file_hash(record['path']) != record['sha256']:
            raise ValueError('Asset changed since generation or registration; regenerate or register again.')
        import re
        if not re.fullmatch(r'[a-f0-9]{32}', record.get('asset_id', '')):
            raise ValueError('Invalid asset ID.')
        result = {**record, 'reviewer':reviewer.strip(), 'review_notes':notes.strip(), 'reviewed_at':now(), 'status':'approved'}
        atomic_json(self.root / 'catalog' / f'{result["asset_id"]}.json', result)
        return result

    def records(self) -> list[dict]:
        import json
        result = []
        for path in (self.root / 'catalog').glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                safe_media(record['path'], self.root)
                record['integrity_ok'] = file_hash(record['path']) == record['sha256']
                result.append(record)
            except (OSError, ValueError, KeyError):
                continue
        return result

    def match(self, topic: str, sop_id: str, revision: str) -> list[dict]:
        return [r for r in self.records() if r['status'] == 'approved' and r['integrity_ok']
                and r['topic'] == topic and r['sop_id'] == sop_id and r['revision'] == revision]

def scene_asset(project: dict, row: dict) -> dict | None:
    return project.get('scene_assets', {}).get(row['scene_id']) or project.get('assets', {}).get(row['visual'])

def visual_content_hash(row: dict) -> str:
    return digest({k:row.get(k, '') for k in ('narration', 'visual_description', 'visual')})

def asset_current(record: dict | None, row: dict, project: dict) -> bool:
    if not record:
        return False
    if record.get('sop_id') != project['sop_id'] or record.get('revision') != project['metadata'].get('revision', ''):
        return False
    generation = record.get('generation')
    if generation and generation.get('scene_content_hash') != visual_content_hash(row):
        return False
    try:
        return Path(record['path']).is_file() and file_hash(record['path']) == record['sha256']
    except (OSError, KeyError):
        return False
