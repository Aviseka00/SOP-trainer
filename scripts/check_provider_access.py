"""Read-only provider checks; never prints credentials or account video data."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from sop_studio import credentials, synthesia, kling
from sop_studio.storage import atomic_json
from sop_studio.schema import now

keys = credentials.load(ROOT)
results = {}
for name, action in [('Synthesia',lambda:synthesia.api('videos',key=keys.get('SYNTHESIA_API_KEY'))),
                     ('Kling',lambda:kling.api('videos/text2video?pageNum=1&pageSize=1',key=keys.get('KLING_API_KEY')))]:
    try:
        action()
        results[name] = {'read_access':'verified'}
    except (RuntimeError,ValueError) as exc:
        results[name] = {'read_access':'failed','error':str(exc)}
    print(name+': '+str(results[name]))
atomic_json(ROOT/'outputs'/'validation'/'provider_access.json', {'checked_at':now(),'results':results,'paid_generation':False})
