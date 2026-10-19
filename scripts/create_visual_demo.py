"""Produce an engineering demonstration with actual speech and generated graphics."""
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sop_studio.ingestion import storyboard
from sop_studio.visuals import generate, frame
from sop_studio.schema import approve, file_hash
from sop_studio.speech import installed_voices
from sop_studio.composition import ROOT, render

def main():
    source = 'Apply the approved soap to both hands.\nRub your palms together.\nRinse both hands thoroughly with water.\nFluid bed dryer: airflow and fluidization, conceptual illustration only.'
    destination = ROOT/'examples'/'generated_visuals'
    destination.mkdir(parents=True, exist_ok=True)
    rows = storyboard(source)
    for row in rows:
        generated = generate(row, ROOT/'approved_media', 'Animation')
        row.update(media=generated['path'], media_sha256=file_hash(generated['path']), generation=generated,
                   asset_review={'status':'draft', 'review_notes':'Engineering demonstration; not technically approved for training.'})
        approve(row, 'Engineering test — not content release approval')
        frame(row, generated['template'], .35).save(destination/(generated['template'].replace(' ', '_')+'.png'))
        shutil.copyfile(generated['path'], destination/(generated['template'].replace(' ', '_')+'.mp4'))
    voices = installed_voices()
    if not voices:
        raise RuntimeError('No installed Windows voice for the actual speech demonstration.')
    files = render(rows, 'Generated visuals — engineering demonstration', 'Windows offline', voices[0]['id'], 155,
                   output_dir=destination, metadata={'source_text':source, 'not_for_training':True, 'generated_visual_review':'draft'})
    (destination/'latest.json').write_text(json.dumps([str(p) for p in files]), encoding='utf-8')
    print(files[0])

if __name__ == '__main__':
    main()
