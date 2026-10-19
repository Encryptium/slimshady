import json, sys
from pathlib import Path
import httpx
sys.stdout.reconfigure(encoding='utf-8')
out=Path('data/raw/discovery'); out.mkdir(parents=True,exist_ok=True)
c=httpx.Client(timeout=180,follow_redirects=True,headers={'User-Agent':'ShadeATL local research prototype'})
def get(name,url,**p):
    r=c.get(url,params=p); r.raise_for_status(); d=r.json()
    (out/f'{name}.json').write_text(json.dumps(d,indent=2),encoding='utf-8'); return d
for q in ['owner:tgiarrusso canopy 2023','Atlanta DSM','Atlanta LiDAR','Atlanta canopy type:"Image Service"']:
    d=get('search_'+str(abs(sum(map(ord,q)))),'https://www.arcgis.com/sharing/rest/search',f='json',q=q,num=100)
    print(q)
    for v in d.get('results',[]): print(v['id'],v['title'],v['type'],v.get('url'))
for id in ['33c5f759da6546b9ab7f28c1f7e5bdb7']:
    d=get(id+'_item','https://www.arcgis.com/sharing/rest/content/items/'+id,f='json')
    print('CANOPY_ITEM',json.dumps(d))
    for suffix in ['data','resources','relatedItems']:
        d=get(id+'_'+suffix,'https://www.arcgis.com/sharing/rest/content/items/'+id+'/'+suffix,f='json',relationshipType='Service2Data',direction='forward')
        print(suffix,json.dumps(d)[:6000])
d=get('3dep','https://tnmaccess.nationalmap.gov/api/v1/products',datasets='Lidar Point Cloud (LPC)',bbox='-84.43,33.73,-84.35,33.81',max=10,outputFormat='JSON')
print('3DEP',json.dumps(d)[:14000])
