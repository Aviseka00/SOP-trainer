"""Build source-linked local visuals for the actual cloud presenter acceptance plan."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio.storage import read_json,atomic_json
from sop_studio.visuals import generate,frame
from sop_studio.media import visual_content_hash
from sop_studio.schema import file_hash
from PIL import Image,ImageDraw

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=read_json(folder/'plan.json')
from sop_studio.visuals import choose_template
sheet=Image.new('RGB',(1280,1480),'white')
for i,row in enumerate(plan['rows']):
    template='Source process card' if row['narration'].startswith('Check that') else choose_template(row)
    item=generate(row,ROOT/'approved_media','Animation',template)
    item['scene_content_hash']=visual_content_hash(row)
    row.update(media=item['path'],media_sha256=file_hash(item['path']),generation=item,layout='Presenter side-by-side')
    still=frame(row,template,.25)
    still.thumbnail((640,350))
    x,y=(i%2)*640,(i//2)*370
    sheet.paste(still,(x,y+20))
    ImageDraw.Draw(sheet).text((x+12,y+3),f'Scene {i+1}: {template}',fill='black')
sheet.save(folder/'visual_review_sheet.jpg',quality=92)
atomic_json(folder/'plan.json',plan)
print('Prepared eight actual contextual animation MP4s and visual review sheet.')
