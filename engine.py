"""Compatibility facade for SOP Trainer Studio's modular engine."""
from sop_studio.schema import CATEGORIES, LAYOUTS
from sop_studio.ingestion import extract, category, storyboard
from sop_studio.composition import ROOT, render, duration, stamp, font, wrap, placeholder
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run
from sop_studio.speech import edge_generate as edge_tts, generate_cached

for folder in ('approved_media', 'outputs', 'jobs'):
    (ROOT / folder).mkdir(exist_ok=True)

def synth(text, path, engine, voice, rate):
    import shutil
    shutil.copyfile(generate_cached(text, ROOT, engine, voice, rate), path)
