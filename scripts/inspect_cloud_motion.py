"""Visual contact sheets and A/V timing evidence; not a phoneme-sync certification."""
import sys,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw,ImageChops,ImageStat
from sop_studio.storage import read_json,atomic_json
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run
from sop_studio.schema import digest
import imageio_ffmpeg

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=read_json(folder/'plan.json')
results=[]
overview=Image.new('RGB',(1280,1600),'white')
for index,row in enumerate(plan['rows'],1):
    clip=plan['cloud_presenters'].get(digest(row['narration']))
    if not clip:
        continue
    path=Path(clip['path'])
    count,seconds=imageio_ffmpeg.count_frames_and_secs(str(path))
    frames=[]
    times=[seconds*k/9 for k in range(1,9)]
    for j,t in enumerate(times):
        target=folder/f'inspect_{index}_{j}.png'
        if not target.exists():
            run([ffmpeg(),'-y','-v','error','-ss',str(t),'-i',path,'-frames:v','1',target],timeout=60)
        frames.append(Image.open(target).convert('RGB'))
    sheet=Image.new('RGB',(1280,1000),'#edf2ef')
    draw=ImageDraw.Draw(sheet)
    metrics={}
    for j,frame in enumerate(frames):
        x,y=(j%4)*320,(j//4)*500
        thumb=frame.copy();thumb.thumbnail((320,180));sheet.paste(thumb,(x,y+25))
        w,h=frame.size
        face=frame.crop((int(w*.41),int(h*.01),int(w*.59),int(h*.36)))
        face.thumbnail((210,210));sheet.paste(face,(x+50,y+210))
        hands=frame.crop((int(w*.34),int(h*.68),int(w*.66),int(h*.96)))
        hands.thumbnail((300,85));sheet.paste(hands,(x+10,y+415))
        draw.text((x+10,y+6),f'Scene {index} / {times[j]:.2f} sec',fill='black')
    for label,bounds in {'face':(.41,.01,.59,.36),'hands':(.34,.68,.66,.96)}.items():
        changes=[]
        for a,b in zip(frames,frames[1:]):
            w,h=a.size
            box=tuple(int(v*(w if i%2==0 else h)) for i,v in enumerate(bounds))
            changes.append(statistics.mean(ImageStat.Stat(ImageChops.difference(a.crop(box),b.crop(box))).mean))
        metrics[label+'_mean_pixel_change']=round(statistics.mean(changes),3)
    sheet.save(folder/f'motion_sheet_{index}.jpg',quality=92)
    for column,j in enumerate((0,2,4,6)):
        thumb=frames[j].copy()
        thumb.thumbnail((320,180))
        overview.paste(thumb,(column*320,(index-1)*200+20))
    ImageDraw.Draw(overview).text((10,(index-1)*200+3),f'Scene {index}',fill='black')
    results.append({'scene':index,'frames':count,'duration_seconds':seconds,'motion_metrics':metrics,
                    'contact_sheet':str(folder/f'motion_sheet_{index}.jpg'),
                    'limits':'ROI pixel change indicates visible movement, not phoneme accuracy, semantic gesture alignment or natural gaze.'})
atomic_json(folder/'motion_evidence.json',{'scenes':results,'status':'visual sampling and structural evidence; playback assessment pending'})
overview.save(folder/'performance_overview.jpg',quality=92)
print('Prepared '+str(len(results))+' motion contact sheets.')
