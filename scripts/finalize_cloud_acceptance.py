"""Publish engineering evidence inside the workspace and attach outputs to the saved demo project."""
import sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio.storage import read_json,atomic_json,ProjectStore
from sop_studio.schema import file_hash

folder=ROOT/'outputs/validation/cloud_acceptance'
report=read_json(folder/'acceptance_report.json')
plan=read_json(folder/'plan.json')
landmarks=read_json(folder/'landmark_evidence.json')
motion=read_json(folder/'motion_evidence.json')
report['facial_activity']=[{k:s[k] for k in ('scene','sample_count','mouth_opening_range','eye_opening_range')} for s in landmarks['scenes']]
report['hand_activity']=[{'scene':s['scene'],'mean_pixel_change':s['motion_metrics']['hands_mean_pixel_change']} for s in motion['scenes']]
report['visual_review']={'sampled_frames_per_scene':8,'findings':'Fictional identity remains consistent in sampled frames; lips change shape, eyes blink/change openness, and both hands gesture. Minor generated facial/finger artifacts remain possible.',
    'not_certified':'Exact viseme-to-phoneme accuracy and meaning-specific hand/eye timing are not independently certified by these measurements.'}
report['saved_project_id']=plan['project_id']
atomic_json(folder/'acceptance_report.json',report)
destination=ROOT/'examples/cloud_acceptance'
destination.mkdir(parents=True,exist_ok=True)
original=Path(report['video'])
for suffix in ('.mp4','.srt','.vtt','.txt'):
    shutil.copyfile(original.with_suffix(suffix),destination/('SOP_Cloud_Scientist_Demo'+suffix))
for name in ('final_preview.png','visual_review_sheet.jpg','motion_sheet_1.jpg','motion_sheet_3.jpg','sample_sop.pdf'):
    shutil.copyfile(folder/name,destination/name)
atomic_json(destination/'acceptance_report.json',report)
store=ProjectStore(ROOT/'projects')
project=store.load(plan['project_id'])
state=read_json(Path(plan['render_job'])/'status.json')
project['last_files']=state['files']
store.save(project,'Engineering acceptance review','Actual eight-scene cloud sample exported and timing evidence recorded; audiovisual quality has stated limits.')
print('Video: '+str(destination/'SOP_Cloud_Scientist_Demo.mp4'))
print('Verified copy SHA-256: '+file_hash(destination/'SOP_Cloud_Scientist_Demo.mp4'))
