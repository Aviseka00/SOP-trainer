"""Screen mouth/eye activity using existing face landmarks; never equate it with viseme accuracy."""
import sys,json,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import cv2,numpy as np,torch
from facexlib.alignment import FAN,landmark_98_to_68

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
weights=ROOT/'external/SadTalker/gfpgan/weights'
assert (weights/'alignment_WFLW_4HG.pth').is_file(),'Existing alignment checkpoint is required; no model download is allowed.'
torch.set_num_threads(2)
model=FAN(num_modules=4,num_landmarks=98,device='cpu')
model.load_state_dict(torch.load(weights/'alignment_WFLW_4HG.pth',map_location='cpu')['state_dict'],strict=True)
model.eval()
print('Existing face model loaded on CPU.',flush=True)
results=[]
for index,row in enumerate(plan['rows'],1):
    import hashlib
    key=hashlib.sha256(json.dumps(row['narration'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    clip=plan['cloud_presenters'].get(key)
    if not clip:
        continue
    output=folder/f'landmarks_scene_{index}.json'
    if output.exists():
        results.append(json.loads(output.read_text()))
        continue
    cap=cv2.VideoCapture(clip['path'])
    fps=cap.get(cv2.CAP_PROP_FPS)
    frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    values=[]
    for f in range(0,frame_count,max(1,round(frame_count/8))):
        cap.set(cv2.CAP_PROP_POS_FRAMES,f)
        ok,frame=cap.read()
        if not ok:
            break
        h,w=frame.shape[:2]
        crop=frame[int(h*.01):int(h*.36),int(w*.41):int(w*.59)]
        with torch.no_grad():
            points=landmark_98_to_68(model.get_landmarks(crop))
        distance=lambda a,b:float(np.linalg.norm(points[a]-points[b]))
        mouth=distance(62,66)/max(1,distance(60,64))
        left=(distance(37,41)+distance(38,40))/max(1,2*distance(36,39))
        right=(distance(43,47)+distance(44,46))/max(1,2*distance(42,45))
        values.append({'time':round(f/fps,4),'mouth_opening_ratio':round(mouth,4),'eye_opening_ratio':round((left+right)/2,4)})
        print(f'Scene {index}: sampled frame {len(values)}',flush=True)
    cap.release()
    mouth=np.array([v['mouth_opening_ratio'] for v in values])
    eyes=np.array([v['eye_opening_ratio'] for v in values])
    record={'scene':index,'fps':fps,'frame_count':frame_count,'sample_count':len(values),
            'mouth_opening_range':float(np.ptp(mouth)),'eye_opening_range':float(np.ptp(eyes)),
            'samples':values,'limitation':'Activity screening only. Does not establish phoneme-to-viseme correctness, gaze target or meaningful gesture timing.'}
    output.write_text(json.dumps(record,indent=2),encoding='utf-8')
    results.append(record)
    print(f'Scene {index}: analyzed {len(values)} face frames',flush=True)
(folder/'landmark_evidence.json').write_text(json.dumps({'scenes':results,'quality_certification':False},indent=2),encoding='utf-8')
