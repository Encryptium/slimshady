"""Download original public Atlanta source data, with provenance and checksums."""
import argparse, hashlib, json, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'; RAW.mkdir(parents=True,exist_ok=True)
MANIFEST=ROOT/'data/manifests'; MANIFEST.mkdir(parents=True,exist_ok=True)
C=httpx.Client(timeout=240, follow_redirects=True,headers={'User-Agent':'ShadeATL/0.1 local prototype; source ingestion'})
BBOX=(-84.56,33.64,-84.28,33.90)
def save_meta(name,url,path,extra=None):
    d={'source':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'file':str(path.relative_to(ROOT)),
       'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**(extra or {})}
    (MANIFEST/f'{name}.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
def download(name,url,extra=None):
    p=RAW/name
    if not p.exists():
        tmp=p.with_suffix(p.suffix+'.part')
        with C.stream('GET',url) as r:
            r.raise_for_status()
            with tmp.open('wb') as f:
                n=0; last=time.monotonic()
                for b in r.iter_bytes(1024*1024):
                    f.write(b); n+=len(b)
                    if time.monotonic()-last>10: print(name,round(n/1e6),'MB',flush=True); last=time.monotonic()
        tmp.replace(p)
    save_meta(p.stem,url,p,extra); print('Ready',p.name,p.stat().st_size,flush=True); return p
def canopy():
    p=download('UTCMosaic2023.zip','https://cura.design.gatech.edu/UTC/UTCMosaic2023.zip',
        {'publisher':'Georgia Tech Center for Urban Resilience and Analytics / City of Atlanta','acquisition_year':2023,
         'description':'Original 1-meter classified urban tree canopy raster derived from WorldView-2 imagery.',
         'catalog_item':'https://www.arcgis.com/home/item.html?id=33c5f759da6546b9ab7f28c1f7e5bdb7',
         'license_status':'Publisher explicitly offers this download. No named redistribution license in catalog; retain attribution; do not redistribute raw file as a licensed data product.'})
    with zipfile.ZipFile(p) as z:
        for i in z.infolist():
            target=(RAW/'canopy'/i.filename).resolve()
            if not target.is_relative_to((RAW/'canopy').resolve()): raise ValueError('Unsafe archive path')
            if not target.exists(): z.extract(i,RAW/'canopy')
        print('Extracted',z.namelist(),flush=True)

def fetch_osm(query):
    """Public mirrors sometimes reject POST even when their GET endpoint works."""
    for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
        for method in ['POST','GET']:
            try:
                print('Fetching OSM',method,endpoint,flush=True)
                r=C.post(endpoint,data={'data':query}) if method=='POST' else C.get(endpoint,params={'data':query})
                r.raise_for_status();d=r.json()
                if 'remark' in d:raise ValueError(d['remark'])
                if not isinstance(d.get('elements'),list):raise ValueError('Invalid Overpass response: missing elements')
                return d,endpoint
            except (httpx.HTTPError,ValueError) as ex:
                print(type(ex).__name__,str(ex)[:250],flush=True)
    raise RuntimeError('Both Overpass endpoints failed. Wait before rerunning; completed extracts are retained.')

def osm():
    # Four bounded queries preserve original OSM node references and real tags.
    west,south,east,north=BBOX
    for iy in range(2):
      for ix in range(2):
        s=south+(north-south)*iy/2; n=south+(north-south)*(iy+1)/2
        w=west+(east-west)*ix/2; e=west+(east-west)*(ix+1)/2
        p=RAW/f'osm-{iy}-{ix}.json'
        if p.exists(): print('Cached',p.name,flush=True); continue
        query=f'''[out:json][timeout:180];(way[highway]({s},{w},{n},{e});way[building]({s},{w},{n},{e});node[name]({s},{w},{n},{e}););out body;>;out skel qt;'''
        d,endpoint=fetch_osm(query)
        p.write_text(json.dumps(d,separators=(',',':')),encoding='utf-8')
        save_meta(p.stem,endpoint,p,{'query':query,'license':'ODbL 1.0','attribution':'© OpenStreetMap contributors','timestamp':d.get('osm3s',{}).get('timestamp_osm_base')})
        print('Elements',len(d['elements']),flush=True)
def boundary():
    url='https://services2.arcgis.com/I9cUOJUZvdGAJncI/arcgis/rest/services/Canopy_Data_2023_WFL1/FeatureServer/2/query'
    r=C.get(url,params={'f':'geojson','where':'1=1','outFields':'*','outSR':4326}); r.raise_for_status()
    d=r.json()
    if 'features' not in d: raise ValueError(d)
    p=RAW/'boundary.geojson'; p.write_text(json.dumps(d),encoding='utf-8')
    save_meta('boundary',str(r.url),p,{'publisher':'City of Atlanta / Georgia Tech','vintage':2024})
def lidar():
    r=C.get('https://tnmaccess.nationalmap.gov/api/v1/products',params={'datasets':'Lidar Point Cloud (LPC)','bbox':'-84.43,33.73,-84.35,33.81','max':1000,'outputFormat':'JSON'})
    r.raise_for_status(); d=r.json(); (RAW/'lidar-catalog.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
    print('Total',d.get('total'),flush=True)
    for item in d.get('items',[]): print(item['title'],item.get('sizeInBytes'),flush=True)
def lidar_tiles():
    from concurrent.futures import ThreadPoolExecutor
    (RAW/'lidar').mkdir(exist_ok=True)
    d=json.loads((RAW/'lidar-catalog.json').read_text())
    # Real 2018 acquisition, restricted to the central district for this release.
    bbox=(-84.42,33.745,-84.365,33.805)
    selected=[]
    for i in d['items']:
        b=i['boundingBox']
        if 'GA_Statewide_2018_B18_DRRA' in i['title'] and b['minX']<bbox[2] and b['maxX']>bbox[0] and b['minY']<bbox[3] and b['maxY']>bbox[1]: selected.append(i)
    (MANIFEST/'lidar-selection.json').write_text(json.dumps({'bbox':bbox,'items':selected,'source':'USGS 3DEP','acquisition_year':2018,'license':'Public domain'},indent=2))
    print('LiDAR tiles',len(selected),'MB',round(sum(i['sizeInBytes'] for i in selected)/1e6),flush=True)
    def one(i):
        url=i['downloadURL']; name='lidar/'+url.split('/')[-1]
        return download(name,url,{'publisher':'USGS 3DEP','acquisition_year':2018,'license':'Public domain'})
    with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(one,selected))
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('source',choices=['canopy','osm','boundary','lidar','lidar_tiles','all']);a=p.parse_args()
    for name in (['canopy','boundary','osm'] if a.source=='all' else [a.source]): globals()[name]()
