"""Validated, backward-compatible project records (standard library only)."""
from __future__ import annotations
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

LAYOUTS = ['Demonstration full screen', 'Presenter picture-in-picture', 'Presenter side-by-side', 'Presenter full screen', 'Presenter circular picture-in-picture']
CATEGORIES = {
    'Hand hygiene': ['handwash', 'hand wash', 'wash hands', 'soap', 'hand hygiene', 'rinse', 'scrub', 'palms'],
    'Gowning': ['gown', 'coverall', 'shoe cover', 'donning', 'doffing', 'ppe', 'mask'],
    'Disinfection': ['sanitiz', 'disinfect', 'alcohol', 'wipe', 'cleaning'],
    'Equipment': ['equipment', 'dryer', 'fbd', 'machine', 'calibrat', 'operate'],
    'Documentation': ['logbook', 'record', 'document', 'sign', 'batch record'],
    'Safety': ['hazard', 'spill', 'emergency', 'injury', 'alarm'],
    'Material handling': ['dispens', 'weigh', 'transfer', 'container', 'material'],
    'Aseptic technique': ['aseptic', 'sterile', 'laminar', 'biosafety', 'grade a'],
}

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def scene_fingerprint(row: dict) -> str:
    return digest({k: v for k, v in row.items() if k not in ('approved', 'review_status', 'reviewer', 'reviewed_at', 'review_hash', 'review_comments')})

def validate_scene(row: dict, index: int = 0) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f'Scene {index + 1} must be an object.')
    narration = row.get('narration')
    if not isinstance(narration, str) or not narration.strip():
        raise ValueError(f'Scene {index + 1} has empty or invalid narration.')
    if len(narration) > 20000:
        raise ValueError('A scene cannot exceed 20,000 characters; split the instruction explicitly.')
    result = dict(row)
    defaults = {'scene_id': uuid.uuid4().hex, 'original_instruction': narration, 'language': 'en-IN',
                'visual': 'General', 'visual_description': '', 'demonstration_type': 'approved-media',
                'layout': LAYOUTS[0], 'reference': str(row.get('source', f'Source segment {index+1}')),
                'seconds': max(1, round(len(narration.split()) / 155 * 60, 2)), 'safety_classification': 'standard',
                'review_status': 'draft', 'approved': False, 'media': '', 'review_comments': '',
                'flags': [], 'entities': {}, 'media_offset': 0.0}
    for key, value in defaults.items():
        result.setdefault(key, value)
    for key in ('scene_id', 'original_instruction', 'language', 'visual', 'visual_description', 'demonstration_type', 'reference', 'review_comments', 'media'):
        if not isinstance(result[key], str):
            raise ValueError(f'Invalid {key} in scene {index+1}.')
    if result['layout'] not in LAYOUTS or result['visual'] not in list(CATEGORIES) + ['General']:
        raise ValueError(f'Invalid scene layout or category in scene {index+1}.')
    for key in ('seconds', 'media_offset'):
        if isinstance(result[key], bool) or not isinstance(result[key], (float, int)) or not math.isfinite(result[key]) or result[key] < 0:
            raise ValueError(f'{key} must be a finite nonnegative number.')
    if result['safety_classification'] not in ('standard', 'critical', 'prohibited'):
        raise ValueError('Unknown safety classification.')
    if not isinstance(result['flags'], list) or not all(isinstance(v, str) for v in result['flags']):
        raise ValueError('Scene flags must be strings.')
    from .editing import validate_cues
    validate_cues(result.get('phrase_cues', []), check_assets=False)
    if result.get('review_hash') != scene_fingerprint(result):
        result.update(approved=False, review_status='draft')
    return result

def validate_project(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get('scenes'), list):
        raise ValueError('Project must contain a scenes list.')
    if len(data['scenes']) > 2000:
        raise ValueError('Limit: 2,000 scenes per project. Split the source into projects.')
    result = dict(data)
    result.setdefault('project_id', uuid.uuid4().hex)
    result.setdefault('title', 'Untitled training')
    result.setdefault('sop_id', '')
    result.setdefault('source_text', '')
    result.setdefault('metadata', {})
    result.setdefault('history', [])
    result.setdefault('assets', {})
    result.setdefault('scene_assets', {})
    for key in ('project_id', 'title', 'sop_id', 'source_text'):
        if not isinstance(result[key], str):
            raise ValueError(f'{key} must be text.')
    if not isinstance(result['metadata'], dict) or not isinstance(result['history'], list) or not isinstance(result['assets'], dict) or not isinstance(result['scene_assets'], dict):
        raise ValueError('Invalid metadata, history or assets.')
    for key in ('revision', 'effective_date'):
        if key in result['metadata'] and not isinstance(result['metadata'][key], str):
            raise ValueError(f'{key} must be text.')
    settings = result.get('settings')
    if settings is not None:
        if not isinstance(settings, dict):
            raise ValueError('Settings must be an object.')
        if settings.get('engine', 'Windows offline') not in ('Windows offline', 'Edge (online)'):
            raise ValueError('Unknown speech engine.')
        if not isinstance(settings.get('voice', ''), str) or not isinstance(settings.get('language', ''), str):
            raise ValueError('Voice and language must be text.')
        rate = settings.get('rate', 155)
        if settings.get('engine', 'Windows offline') == 'Windows offline':
            if isinstance(rate, bool) or not isinstance(rate, int) or not 100 <= rate <= 220:
                raise ValueError('Offline speech rate must be between 100 and 220.')
        elif rate not in ('-20%', '-10%', '+0%', '+10%', '+20%'):
            raise ValueError('Unsupported online speech rate.')
        if settings.get('preset', '720p landscape') not in ('720p landscape', '1080p landscape', '1080p portrait'):
            raise ValueError('Unsupported video preset.')
        dictionary = settings.get('pronunciation', {})
        if not isinstance(dictionary, dict) or not all(isinstance(k, str) and k and isinstance(v, str) for k,v in dictionary.items()):
            raise ValueError('Invalid pronunciation dictionary.')
    result['scenes'] = [validate_scene(r, i) for i, r in enumerate(data['scenes'])]
    ids = [r['scene_id'] for r in result['scenes']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate scene IDs.')
    result['schema_version'] = 2
    return result

def approve(row: dict, reviewer: str, comments: str = '') -> None:
    if not reviewer.strip():
        raise ValueError('Enter the reviewer name before approval.')
    validated = validate_scene(row)
    row.update(validated)
    row.update(reviewer=reviewer.strip(), reviewed_at=now(), review_comments=comments,
               approved=True, review_status='approved')
    row['review_hash'] = scene_fingerprint(row)

def invalidate(row: dict) -> None:
    row.update(approved=False, review_status='draft')
    row.pop('review_hash', None)
