"""Free account resource check; no generation or credential output."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio import credentials,cloud_io
from sop_studio.storage import atomic_json
key=credentials.load(ROOT)['KLING_API_KEY']
end=int(time.time()*1000)
result=cloud_io.request(f'https://api-singapore.klingai.com/account/costs?start_time={end-30*86400000}&end_time={end}', 'Bearer '+key)
data=result.get('data',{})
packages=data.get('resource_pack_subscribe_infos',[])
summary={'code':result.get('code'),'package_count':len(packages),
         'active_packages':sum(p.get('status')=='online' for p in packages),
         'reported_remaining_quantity':sum(float(p.get('remaining_quantity',0)) for p in packages),
         'note':'Provider says remaining-quantity statistics may be delayed. Generation attempt returned HTTP 429.'}
atomic_json(ROOT/'outputs/validation/kling_usage.json',summary)
print(summary)
