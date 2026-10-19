"""Measure timing introduced by composition and inspect exact scene provenance."""
import sys,json,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import numpy as np,imageio_ffmpeg
from sop_studio.storage import read_json,atomic_json
from sop_studio.schema import file_hash
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run

folder=ROOT/'outputs/validation/cloud_acceptance'
plan=read_json(folder/'plan.json')
state=read_json(Path(plan['render_job'])/'status.json')
assert state['state']=='complete',state
video,srt,manifest_path=map(Path,state['files'])
manifest=read_json(manifest_path)
decoded=folder/'final_decoded_audio.wav'
run([ffmpeg(),'-y','-v','error','-i',video,'-vn','-ar','48000','-ac','1',decoded],timeout=120)
def waveform(path):
    with wave.open(str(path),'rb') as stream:
        assert stream.getnchannels()==1 and stream.getsampwidth()==2 and stream.getframerate()==48000
        return np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(float)
audio=waveform(decoded)
metrics=[]
for i,item in enumerate(manifest['timeline']):
    original=waveform(Path(plan['render_job'])/f'normalized_{i:04}.wav')
    start=round(item['start']*48000)
    actual=audio[start:start+len(original)]
    a,b=original[::96],actual[::96]
    n=min(len(a),len(b))
    a,b=a[:n],b[:n]
    trim=50
    a=a[trim:-trim]
    candidates=[]
    for lag in range(-25,26):
        shifted=b[trim+lag:n-trim+lag]
        aa=a-a.mean();bb=shifted-shifted.mean()
        score=float(np.dot(aa,bb)/max(1e-12,np.linalg.norm(aa)*np.linalg.norm(bb)))
        candidates.append((score,lag))
    score,lag=max(candidates)
    assert item['presenter']['generation']['output_sha256']==plan['cloud_presenters'][plan['rows'][i]['generation']['source_narration_hash']]['sha256']
    metrics.append({'scene':i+1,'introduced_audio_offset_ms':lag*2,'waveform_correlation':round(score,5),
                    'scene_start_seconds':item['start'],'scene_end_seconds':item['end']})
count,seconds=imageio_ffmpeg.count_frames_and_secs(str(video))
assert count==manifest['duration_frames']
assert all(abs(m['introduced_audio_offset_ms'])<=20 and m['waveform_correlation']>.9 for m in metrics),metrics
run([ffmpeg(),'-y','-v','error','-ss','12','-i',video,'-frames:v','1',folder/'final_preview.png'],timeout=60)
run([ffmpeg(),'-v','error','-i',video,'-f','null','-'],timeout=180)
report={'status':'end-to-end technical pass; semantic performance review remains separate',
        'source_pdf':plan['source_file'],'source_pdf_sha256':plan['source_file_sha256'],
        'source_kind':'Bundled fictional sample SOP, not a user operational procedure',
        'video':str(video),'video_sha256':file_hash(video),'frame_count':count,'duration_seconds':seconds,
        'cloud_scenes':len(manifest['timeline']),'speech':'Original HeyGen video audio, normalized without time stretching',
        'timing':metrics,'kling':'Live generation rejected HTTP 429; usage API reported zero active packages. Local schematic fallback used explicitly.',
        'limitations':['Waveform checks measure timing added by composition, not original phoneme-to-viseme accuracy.',
                       'Facial landmark and hand ROI activity do not certify gaze intent or semantic gesture timing.',
                       'Final operational training requires human source and full audiovisual playback review.']}
atomic_json(folder/'acceptance_report.json',report)
print(json.dumps({k:report[k] for k in ('status','video','frame_count','duration_seconds','cloud_scenes','timing')},indent=2))
