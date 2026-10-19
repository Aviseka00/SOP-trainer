"""Download confirmed cloud renders for composition and frame/audio analysis."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio.cloud_io import download
from sop_studio.storage import read_json,atomic_json
from sop_studio.schema import file_hash,digest

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=read_json(folder/'plan.json')
for i,row in enumerate(plan['rows'],1):
    details=folder/f'presenter_details_{i}.json'
    if not details.exists():
        continue
    result=read_json(details)
    if result.get('status')!='completed':
        continue
    saved=read_json(folder/f'presenter_{i}.json')
    if saved['script']!=row['narration']:
        raise ValueError('Presenter script does not match planned scene.')
    target=ROOT/'approved_media'/f'acceptance_cloud_{saved["video_id"]}.mp4'
    if not target.exists():
        download(result['videoUrl'],target,('heygen.ai','heygen.com'))
    plan['cloud_presenters'][digest(row['narration'])]={'path':str(target),'sha256':file_hash(target),
        'provider':saved['provider'],'video_id':saved['video_id']}
    print(f'Scene {i}: saved cloud video ({result.get("duration")} seconds)')
atomic_json(folder/'plan.json',plan)
