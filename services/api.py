import io,json,math,os,re,sqlite3,time,threading
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from functools import lru_cache
from typing import Literal
import httpx,numpy as np,rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_bounds
from PIL import Image
from fastapi import FastAPI,HTTPException,Query,Request,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator
from services.geo import ROOT,RAW,DATA
from services.routing import Router,RouteError

router=None;route_lock=threading.Lock();rate_events=defaultdict(deque)
@asynccontextmanager
async def lifespan(app):
    global router
    router=Router()
    with sqlite3.connect(ROOT/'data/reports.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, created TEXT, category TEXT, longitude REAL, latitude REAL, note TEXT, status TEXT DEFAULT \'pending\')')
    yield

app=FastAPI(title='SlimShady',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.environ.get('CORS_ORIGINS','http://localhost:8081,http://127.0.0.1:8081,http://localhost:8080,http://127.0.0.1:8080').split(','),allow_methods=['GET','POST'],allow_headers=['Content-Type'])

class Position(BaseModel):
    longitude:float=Field(ge=-180,le=180)
    latitude:float=Field(ge=-90,le=90)
class Preferences(BaseModel):
    avoidStairs:bool=False
    maxExtraRatio:float=Field(default=.2,ge=0,le=.6)
    maxExtraSeconds:int=Field(default=300,ge=0,le=900)
class RouteRequest(BaseModel):
    origin:Position
    destination:Position
    departureTime:str
    walkingSpeedMps:float=Field(default=1.3,ge=.5,le=4)
    preferences:Preferences=Field(default_factory=Preferences)
    @field_validator('departureTime')
    @classmethod
    def check_time(cls,v):
        d=datetime.fromisoformat(v.replace('Z','+00:00'))
        if not d.tzinfo:raise ValueError('departureTime must include a UTC offset')
        if not 2020<=d.year<=2035:raise ValueError('Choose a date between 2020 and 2035')
        return v
class LoopRequest(BaseModel):
    origin:Position
    departureTime:str
    durationMinutes:int=Field(default=30,ge=10,le=90)
    activity:Literal['walk','jog']='walk'
    shadePreference:Literal['balanced','more_shade','most_shade']='more_shade'
    avoidStairs:bool=False
    _check_time=field_validator('departureTime')(RouteRequest.check_time.__func__)

class Report(Position):
    category:Literal['blocked_path','missing_sidewalk','incorrect_access','shade_mismatch']
    note:str=Field(default='',max_length=1000)

def limited(request,limit=30):
    key=(request.client.host if request.client else 'local',request.url.path)
    now=time.monotonic();q=rate_events[key]
    while q and now-q[0]>60:q.popleft()
    if len(q)>=limit:raise HTTPException(429,detail={'code':'RATE_LIMIT','message':'Please wait a minute before requesting more routes.'})
    q.append(now)

@app.get('/health/ready')
def health():return {'ready':router is not None,'release':router.release if router else None}
@app.get('/v1/coverage')
def coverage():
    return {'boundary':json.loads((DATA/'boundary.geojson').read_text()),'quality':router.quality,'buildingHeightsAvailable':router.shade.height_count,'capabilities':{'treeCanopy':True,'buildingShadows':True,'dynamicTreeShadows':False,'foregroundNavigation':True,'backgroundNavigation':False,'fieldValidated':False},'sources':[{'name':'Georgia Tech / City of Atlanta · 2023 canopy, 1 m','url':'https://geospatial.gatech.edu/AtlantaUTC/'},{'name':'OpenStreetMap contributors · ODbL','url':'https://www.openstreetmap.org/copyright'},{'name':'USGS 3DEP · 2018 LiDAR, where available','url':'https://www.usgs.gov/3d-elevation-program'}]}
@app.get('/v1/search')
def search(q:str=Query('',max_length=150),limit:int=Query(8,ge=1,le=20)):
    def normalize(value):
        value=re.sub(r'[^a-z0-9 ]',' ',value.casefold())
        words={'st':'street','ave':'avenue','rd':'road','blvd':'boulevard','dr':'drive','eighth':'8th','fifth':'5th','tenth':'10th'}
        return ' '.join(words.get(w,w) for w in value.split())
    query=normalize(q)
    if len(query)<2:return {'results':[]}
    # Search only actual OSM names; arbitrary address lookup is not fabricated.
    words=query.split();found=[]
    for p in router.places:
        name=normalize(p['name'])
        searchable=normalize(' '.join([p['name'],p.get('address',''),p.get('locationLabel','')]))
        if all(w in searchable for w in words):found.append((0 if name==query else 1 if name.startswith(query) else 2,len(name),p))
    found.sort(key=lambda a:a[:2]);unique=[];seen=set()
    for _,__,p in found:
        key=(p['name'],round(p['longitude'],4),round(p['latitude'],4))
        if key not in seen:unique.append(p);seen.add(key)
        if len(unique)==limit:break
    return {'results':unique,'provider':'Local OpenStreetMap place index','hint':'Search a mapped place, or tap the map for any address or entrance.'}
@app.post('/v1/routes')
def routes(body:RouteRequest,request:Request):
    limited(request)
    try:
        with route_lock:return router.route(body.model_dump())
    except RouteError as e:raise HTTPException(422,detail={'code':e.code,'message':str(e)})

@app.post('/v1/loops')
def loops(body:LoopRequest,request:Request):
    from services.loops import loop_routes
    limited(request,10)
    try:
        with route_lock:return loop_routes(router,body.model_dump())
    except RouteError as e:raise HTTPException(422,detail={'code':e.code,'message':str(e)})

@app.get('/v1/network')
def network(west:float,south:float,east:float,north:float):
    if not -180<=west<east<=180 or not -90<=south<north<=90 or east-west>.1 or north-south>.1:raise HTTPException(422,'Zoom in to inspect the walking network.')
    from shapely.geometry import box
    from services.geo import project
    idx=router.index.query(project(box(west,south,east,north)))
    return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'LineString','coordinates':router.edges[int(i)]['coords']},'properties':{'quality':router.edges[int(i)]['geometry_quality'],'name':router.edges[int(i)]['name']}} for i in idx[:10000]]}

@lru_cache(maxsize=512)
def canopy_tile(z,x,y):
    half=20037508.342789244;span=2*half/2**z;west=-half+x*span;north=half-y*span
    dest=np.zeros((256,256),dtype=np.uint8)
    with rasterio.open(RAW/'canopy/UTCMosaic2023.tif') as src:
        reproject(source=rasterio.band(src,1),destination=dest,src_transform=src.transform,src_crs=src.crs,dst_transform=from_bounds(west,north-span,west+span,north,256,256),dst_crs='EPSG:3857',resampling=Resampling.nearest)
    rgba=np.zeros((256,256,4),dtype=np.uint8);rgba[:,:,:3]=[54,112,77];rgba[:,:,3]=np.where(dest==1,130,0)
    out=io.BytesIO();Image.fromarray(rgba).save(out,format='PNG');return out.getvalue()
@app.get('/v1/canopy/{z}/{x}/{y}.png')
def tile(z:int,x:int,y:int):
    if not 10<=z<=19 or not 0<=x<2**z or not 0<=y<2**z:raise HTTPException(404)
    return Response(canopy_tile(z,x,y),media_type='image/png',headers={'Cache-Control':'public, max-age=86400'})

weather_cache={}
@app.get('/v1/weather')
def weather():
    now=time.time()
    if weather_cache.get('expires',0)>now:return weather_cache['data']
    try:
        with httpx.Client(timeout=8,headers={'User-Agent':'ShadeATL local research application','Accept':'application/geo+json'},follow_redirects=True) as c:
            p=c.get('https://api.weather.gov/points/33.7756,-84.3963');p.raise_for_status()
            r=c.get(p.json()['properties']['forecastHourly']);r.raise_for_status();data=r.json();period=data['properties']['periods'][0]
            a=c.get('https://api.weather.gov/alerts/active?point=33.7756,-84.3963')
            result={'available':True,'temperature':period['temperature'],'unit':period['temperatureUnit'],'forecast':period['shortForecast'],'time':period['startTime'],'alerts':[v['properties']['headline'] for v in a.json().get('features',[])] if a.is_success else [],'source':'National Weather Service','location':'Central Atlanta','fetchedAt':datetime.now(timezone.utc).isoformat()}
        weather_cache.update(expires=now+900,data=result);return result
    except Exception:
        return {'available':False,'forecast':'Weather unavailable','source':'National Weather Service','message':'Geometric cover estimates remain available.'}
@app.post('/v1/reports',status_code=201)
def report(body:Report,request:Request):
    limited(request,5)
    from shapely.geometry import Point
    if not router.boundary.covers(Point(body.longitude,body.latitude)):raise HTTPException(422,'Report must be inside coverage.')
    with sqlite3.connect(ROOT/'data/reports.sqlite') as db:
        cur=db.execute('INSERT INTO reports (created,category,longitude,latitude,note) VALUES (?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),body.category,body.longitude,body.latitude,body.note))
        return {'id':cur.lastrowid,'status':'pending','message':'Saved for review. This report has not changed the walking network.'}

if (ROOT/'apps/mobile/dist').exists():app.mount('/',StaticFiles(directory=ROOT/'apps/mobile/dist',html=True),name='web')
