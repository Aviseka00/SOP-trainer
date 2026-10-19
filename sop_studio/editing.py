"""Shared editing, recovery and timed-cue validation."""
import math
from pathlib import Path
from .schema import digest, file_hash
from .media import asset_current

WORKFLOW = ['Source document', 'Summary & key points', 'Storyboard & script',
            'Visual generation', 'Presenter studio', 'Voice studio', 'QA review', 'Export center']

def content_digest(project):
    return digest({k: v for k, v in project.items() if k not in ('history', 'saved_at')})

def validate_cues(cues, duration=None, check_assets=True):
    if not isinstance(cues, list) or len(cues) > 100:
        raise ValueError('Use at most 100 phrase cues per scene.')
    previous = 0.0
    for cue in cues:
        if not isinstance(cue, dict) or not isinstance(cue.get('text'), str) or not cue['text'].strip():
            raise ValueError('Every phrase cue needs caption text.')
        start, end = cue.get('start'), cue.get('end')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
            raise ValueError('Cue times must be finite seconds.')
        if start < previous or end <= start or (duration is not None and end > duration + .001):
            raise ValueError('Phrase cues must be ordered, nonoverlapping and within the measured audio duration.')
        previous = end
        asset = cue.get('asset')
        if asset and not isinstance(asset, dict):
            raise ValueError('Phrase visual metadata must be an object.')
        if asset and check_assets:
            if asset.get('status') != 'approved' or not Path(asset.get('path', '')).is_file() or file_hash(asset['path']) != asset.get('sha256'):
                raise ValueError('Phrase visual is missing, changed or not technically approved.')
    return cues

def readiness(project, approved, strict=True):
    issues = []
    avatar = project.get('avatar', {})
    if project.get('settings', {}).get('require_presenter_audition') and avatar.get('provider') in ('heygen', 'synthesia'):
        from .presenter_quality import audition_signature
        reviewed_signature = project.get('presenter_quality_review', {}).get('signature')
        if not any(audition_signature(avatar, r['narration']) == reviewed_signature for r in project['scenes']):
            issues.append(('Presenter studio', None, 'Generate and review one presenter audition with the current configuration before full production.'))
    if project.get('settings', {}).get('require_complete_source'):
        from .presenter_quality import coverage
        report = coverage(project)
        if report['missing']:
            issues.append(('Source document', None, f'{len(report["missing"])} source segments are absent from the storyboard. Build the full source storyboard or explicitly choose overview mode.'))
    rows = project['scenes']
    if avatar.get('native_voice_clone'):
        if avatar.get('provider') != 'heygen' or not avatar.get('voice_consent'):
            issues.append(('Voice studio', None, 'Authorize and apply the cloned voice to a HeyGen presenter.'))
        for index, row in enumerate(rows):
            if len(row['narration']) > 5000:
                issues.append(('Storyboard & script', index, f'Scene {index+1}: split cloned-voice narration into scenes of at most 5,000 characters.'))
    if not project['source_text'].strip():
        issues.append(('Source document', None, 'Upload and retain the source SOP.'))
    if not rows:
        issues.append(('Source document', None, 'Build a storyboard.'))
    import hashlib
    source = hashlib.sha256(project['source_text'].encode()).hexdigest()
    if project['metadata'].get('storyboard_source_hash', source) != source:
        issues.append(('Source document', None, 'Source changed: rebuild the storyboard.'))
    if not project.get('settings', {}).get('voice') and project.get('avatar', {}).get('provider') not in ('heygen', 'synthesia', 'imported-cloud'):
        issues.append(('Voice studio', None, 'Discover and save a narration voice.'))
    for i, row in enumerate(rows):
        if not approved(row):
            issues.append(('QA review', i, f'Scene {i+1}: review the current content.'))
        asset = project.get('scene_assets', {}).get(row['scene_id']) or project.get('assets', {}).get(row['visual'])
        if strict and (not asset_current(asset, row, project) or asset.get('status') != 'approved'):
            issues.append(('Visual generation', i, f'Scene {i+1}: attach a current, reviewed visual.'))
        try:
            validate_cues(row.get('phrase_cues', []))
            if any(c.get('asset') for c in row.get('phrase_cues', [])) and project.get('presenter') and row['layout'] not in ('Demonstration full screen', 'Presenter side-by-side'):
                raise ValueError('Use a full demonstration or side-by-side layout for phrase visuals.')
            for cue in row.get('phrase_cues', []):
                if cue.get('asset') and not asset_current(cue['asset'], row, project):
                    raise ValueError('Phrase visual does not match the current source revision or narration.')
        except ValueError as exc:
            issues.append(('Storyboard & script', i, f'Scene {i+1}: {exc}'))
    return issues
