import httpx,json,time
from pathlib import Path
i=next(i for i in json.loads(Path('data/raw/lidar-catalog.json').read_text())['items'] if '2018' in i['title'])
url=i['downloadURL'].replace('https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/','https://prd-tnm.s3.amazonaws.com/StagedProducts/')
t=time.monotonic()
r=httpx.get(url,headers={'Range':'bytes=0-1048575'},timeout=60)
print(r.status_code,len(r.content),time.monotonic()-t,url)
if r.status_code==206: Path('data/raw/discovery/lidar-mirror.json').write_text(json.dumps({'url':url,'status':206,'seconds':time.monotonic()-t}))
