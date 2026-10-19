"""Prepare a reusable demo-SOP acceptance plan and one live Kling task."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import re
from sop_studio import credentials,jobs
from sop_studio.ingestion import extract
from sop_studio.summary import build_brief,brief_scenes
from sop_studio.storage import atomic_json,read_json
from sop_studio.schema import file_hash

folder=ROOT/'outputs/validation/cloud_acceptance'
folder.mkdir(parents=True,exist_ok=True)
plan_file=folder/'plan.json'
if plan_file.exists():
    plan=read_json(plan_file)
else:
    import fitz
    text=(ROOT/'examples/hand_hygiene.txt').read_text(encoding='utf-8')
    pdf=fitz.open()
    page=pdf.new_page()
    page.insert_textbox(fitz.Rect(36,36,559,806),text,fontsize=10)
    pdf.save(folder/'sample_sop.pdf')
    pdf.close()
    source=extract('sample_sop.pdf',(folder/'sample_sop.pdf').read_bytes())
    brief=build_brief(source,8)
    for point in brief['points']:
        point['speech']=re.sub(r'^\d+(?:\.\d+)*[.)]?\s*','',point['speech'])
    rows=brief_scenes(brief,source)
    plan={'source_file':str(folder/'sample_sop.pdf'),'source_file_sha256':file_hash(folder/'sample_sop.pdf'),
          'source_text':source,'brief':brief,'rows':rows,'cloud_presenters':{},'engineering_example_only':True}
    atomic_json(plan_file,plan)
if not plan.get('kling_job'):
    row=next(r for r in plan['rows'] if 'Apply the approved soap' in r['narration'])
    keys=credentials.load(ROOT)
    plan['kling_job']=str(jobs.start({'task':'generate_visuals','provider':'kling','scenes':[row],
        'provider_config':{'model':'kling-v2-6','duration':5,'cloud_authorized':True},
        'sop_id':'DEMO-HH-001','revision':'DEMO-01','mode':'Animation','template':'Automatic'},
        environment={'KLING_API_KEY':keys['KLING_API_KEY']}))
    atomic_json(plan_file,plan)
print('Plan: '+str(plan_file))
print('Kling task: '+plan['kling_job'])
for i,row in enumerate(plan['rows']):
    print(str(i+1)+': '+row['narration'])
