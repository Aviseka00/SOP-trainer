"""Source coverage and content-bound presenter audition review."""
import re
from .ingestion import storyboard
from .schema import digest

def normalized(text):
    return re.sub(r'\s+', ' ', text).strip().casefold()

def coverage(project):
    units = storyboard(project.get('source_text', '')) if project.get('source_text', '').strip() else []
    spoken = [normalized(r.get('original_instruction', '')) for r in project['scenes']]
    missing = [r for r in units if not any(normalized(r['original_instruction']) in text for text in spoken)]
    return {'total': len(units), 'covered': len(units)-len(missing), 'missing': missing}

def audition_signature(config, text):
    return digest({'presenter': config, 'narration': text})

def apply_quality_preset(project):
    settings = project.setdefault('settings', {})
    settings['preset'] = '1080p landscape'
    settings['require_complete_source'] = True
    settings['require_presenter_audition'] = True
    settings['production'] = {**settings.get('production', {}), 'burn_captions': True,
                              'caption_style': 'High contrast', 'transition': 'Fade',
                              'accent': settings.get('production', {}).get('accent', '#246b50')}
