"""Read public GIS metadata; save responses and print a compact evidence inventory."""
import json
import re
from pathlib import Path
import httpx
import sys
sys.stdout.reconfigure(encoding='utf-8')

OUT = Path('data/raw/discovery')
OUT.mkdir(parents=True, exist_ok=True)
client = httpx.Client(timeout=90, follow_redirects=True, headers={'User-Agent': 'ShadeATL research prototype'})

def get(name, url, **params):
    r = client.get(url, params=params)
    r.raise_for_status()
    d = r.json()
    (OUT / f'{name}.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
    return d

app = json.loads(Path('canopy-app.json').read_text(encoding='utf-8-sig'))
def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from strings(v)
    elif isinstance(x, list):
        for v in x: yield from strings(v)
for s in strings(app):
    if s.startswith('https:') and ('hub.arcgis' in s or '.zip' in s):
        print(s)

for label, query in [('canopy', 'Atlanta canopy 2023'), ('landcover', 'Atlanta land cover'), ('sidewalk', 'Atlanta sidewalk')]:
    d = get(label, 'https://www.arcgis.com/sharing/rest/search', f='json', q=query, num=50)
    for r in d.get('results', []):
        if r['id'] in ['2830093f1a2941a6bf90e37ac7cf63d4','33c5f759da6546b9ab7f28c1f7e5bdb7','9e650bed2e7e49f0a1bb183212c9a99f']:
            print(label, json.dumps(r))
            svc=get(r['id'],r['url'],f='pjson')
            print('SERVICE', json.dumps(svc)[:16000])
            for layer in svc.get('layers',[]):
                l=get(r['id']+'_'+str(layer['id']),r['url']+'/'+str(layer['id']),f='json')
                print('LAYER',json.dumps(l)[:5000])

base='https://gis.atlantaga.gov/dpcd/rest/services/OpenDataService1/MapServer/10'
print('BUILDING_SAMPLE',json.dumps(get('buildings_sample',base+'/query',f='json',where='1=1',outFields='STORIES,BASEELEV,ROOFELEV',resultRecordCount=5,returnGeometry='false'))[:3000])
