"""Compose the benchmarked synthetic presenter using its original speech and cached model output."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sop_studio.composition import ROOT, render
from sop_studio.ingestion import storyboard
from sop_studio.schema import approve, file_hash
from sop_studio.speech import installed_voices
from sop_studio.visuals import generate

def main():
    benchmark = json.loads((ROOT/'models/sadtalker/benchmark.json').read_text(encoding='utf-8'))
    rows = storyboard(benchmark['test_text'])
    row = rows[0]
    diagram = generate(row, ROOT/'approved_media', 'Illustration')
    row.update(layout='Presenter circular picture-in-picture', media=diagram['path'], media_sha256=file_hash(diagram['path']),
               generation=diagram, asset_review={'status':'draft', 'review_notes':'Engineering example only.'})
    approve(row, 'Engineering integration test')
    portrait = ROOT/'approved_media/presenters/fictional_educator.png'
    files = render(rows, 'AI presenter — engineering demonstration', 'Windows offline', installed_voices()[0]['id'], 155,
        avatar={'portrait':str(portrait), 'portrait_sha256':file_hash(portrait), 'device':'cpu', 'expression_scale':1.0, 'pose_style':0},
        output_dir=ROOT/'examples/ai_presenter', metadata={'not_for_training':True, 'actual_engine':'SadTalker', 'benchmark':benchmark})
    (ROOT/'examples/ai_presenter/composed_latest.json').write_text(json.dumps([str(p) for p in files]), encoding='utf-8')
    manifest = json.loads(files[2].read_text(encoding='utf-8'))
    assert manifest['timeline'][0]['presenter']['type'] == 'SadTalker audio-driven face'
    assert manifest['timeline'][0]['presenter']['generation']['output_sha256'] == benchmark['output_sha256']
    print(files[0])

if __name__ == '__main__':
    main()
