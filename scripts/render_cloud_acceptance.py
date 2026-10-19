"""Run the actual app compositor and persist a reopenable engineering sample project."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio.storage import read_json,atomic_json,ProjectStore
from sop_studio.schema import approve,digest,file_hash
from sop_studio.media import MediaLibrary
from sop_studio import jobs

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=read_json(folder/'plan.json')
if len(plan['cloud_presenters'])!=len(plan['rows']):
    raise ValueError('All eight exact-script cloud clips are required before rendering.')
library=MediaLibrary(ROOT/'approved_media')
assets={}
for i,row in enumerate(plan['rows'],1):
    record=library.add(row['media'],row['visual'],f'Cloud acceptance scene {i}',
        'Local schematic reviewed against bundled fictional source','Engineering demonstration only','DEMO-HH-001','DEMO-01',generation=row['generation'])
    record=library.review(record,'Engineering acceptance review','Conceptual source labels and warnings inspected in visual_review_sheet.jpg; not operational procedure validation.')
    assets[row['scene_id']]=record
    row['asset_review']={k:record.get(k) for k in ('asset_id','status','reviewer','review_notes','sha256')}
    row['presenter_sha256']=''
    approve(row,'Engineering acceptance review','Source-linked overview of fictional SOP; imported cloud speech and gestures require playback review.')
avatar={'provider':'imported-cloud','cloud_authorized':True,'clips':plan['cloud_presenters']}
project=ProjectStore(ROOT/'projects').save({'title':'Cloud scientist — DEMO SOP acceptance','sop_id':'DEMO-HH-001',
    'source_text':plan['source_text'],'metadata':{'revision':'DEMO-01','effective_date':'Engineering demo only',
    'storyboard_source_hash':plan['brief']['source_text_sha256'],'not_for_operational_training':True},
    'scenes':plan['rows'],'scene_assets':assets,'avatar':avatar,'training_brief':plan['brief'],
    'settings':{'engine':'Windows offline','voice':'','language':'en-IN','rate':155,'preset':'720p landscape','pronunciation':{}}},
    'Engineering acceptance review','Actual cloud clips matched to source-derived speech; local visuals reviewed as schematic examples.')
request={'rows':project['scenes'],'title':project['title'],'engine':'Windows offline','voice':'','rate':155,
    'avatar':avatar,'media_map':{},'preset':'720p landscape','fps':30,'strict_media':True,
    'output_dir':str(folder/'final'),'metadata':{**project['metadata'],'sop_id':project['sop_id'],
    'project_id':project['project_id'],'source_file_sha256':plan['source_file_sha256'],
    'summary':plan['brief'],'cloud_handoff':'Actual HeyGen connector generation, then scene-bound import into app compositor.',
    'kling_status':'Generation HTTP 429; no active API resource package reported. Local schematics used explicitly.'}}
job=jobs.start(request)
plan['render_job']=str(job)
plan['project_id']=project['project_id']
atomic_json(folder/'plan.json',plan)
project['active_job']=str(job)
ProjectStore(ROOT/'projects').save(project,'Engineering acceptance review','Background render started')
print('Render job: '+str(job))
print('Saved project: '+project['project_id'])
