"""Build the real Atlanta walk graph. No synthetic production geometry or shade."""
import json, math, sys, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import rasterio
import networkx as nx
from shapely.geometry import shape, Point, LineString, Polygon, mapping
from shapely.ops import unary_union
from shapely import contains_xy
from services.geo import ROOT, RAW, DATA, project, unproject, FORWARD

PEDESTRIAN={'footway','path','pedestrian','steps','living_street'}
ROAD={'residential','unclassified','service','tertiary','secondary','primary','tertiary_link','secondary_link','primary_link'}
def eligible(t):
    h=t.get('highway'); foot=t.get('foot'); access=t.get('access')
    if foot in {'no','private','use_sidepath'} or (access in {'no','private','customers','permit'} and foot not in {'yes','designated','permissive'}): return False
    if t.get('indoor')=='yes' or t.get('area')=='yes' or t.get('construction') or t.get('proposed'): return False
    if h in PEDESTRIAN: return True
    if h=='cycleway': return foot in {'yes','designated','permissive'}
    if h not in ROAD: return False
    if t.get('service') in {'driveway','parking_aisle','drive-through'}: return False
    # Separately mapped sidewalks must not be duplicated as road-centerline shortcuts.
    if t.get('sidewalk')=='separate' or t.get('sidewalk:both')=='separate': return False
    if h in {'primary','secondary','tertiary','primary_link','secondary_link','tertiary_link'}:
        return any(t.get(k) in {'yes','both','left','right'} for k in ['sidewalk','sidewalk:both','sidewalk:left','sidewalk:right'])
    return t.get('sidewalk')!='no'

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    bdata=json.loads((RAW/'boundary.geojson').read_text())
    boundary=unary_union([shape(f['geometry']) for f in bdata['features']]); city=project(boundary)
    nodes={}; ways={}; dates=[]
    for file in sorted(RAW.glob('osm-?-?.json')):
        print('Reading',file.name,flush=True); d=json.loads(file.read_text(encoding='utf-8'))
        dates.append(d.get('osm3s',{}).get('timestamp_osm_base'))
        for e in d['elements']:
            if e['type']=='node':
                if e['id'] not in nodes or e.get('tags'): nodes[e['id']]=e
            elif e['type']=='way': ways[e['id']]=e
        del d
    print('OSM',len(nodes),'nodes',len(ways),'ways',flush=True)
    walkways=[w for w in ways.values() if eligible(w.get('tags',{})) and all(n in nodes for n in w['nodes'])]
    use=Counter(n for w in walkways for n in set(w['nodes']))
    xy={}; coords={}
    used=set(n for w in walkways for n in w['nodes'])
    ids=list(used); lon=np.array([nodes[n]['lon'] for n in ids]); lat=np.array([nodes[n]['lat'] for n in ids]); x,y=FORWARD.transform(lon,lat)
    inside=contains_xy(city,x,y)
    for i,n in enumerate(ids):
        if inside[i]: xy[n]=(float(x[i]),float(y[i])); coords[n]=[float(lon[i]),float(lat[i])]
    raster=rasterio.open(RAW/'canopy/UTCMosaic2023.tif')
    canopy=raster.read(1); affine=~raster.transform
    def sample_canopy(points):
        a=np.array(points); cols,rows=affine*(a[:,0],a[:,1]); rr=np.floor(rows).astype(int); cc=np.floor(cols).astype(int)
        valid=(rr>=0)&(rr<raster.height)&(cc>=0)&(cc<raster.width)
        values=np.zeros(len(points),dtype=np.uint8); values[valid]=(canopy[rr[valid],cc[valid]]==1)
        return values.tolist()
    edges=[]; graph=nx.Graph(); sample_xy=[]; sample_tree=[]; sample_edges=[]
    for w in walkways:
        tags=w['tags']; path=w['nodes']; section=[]; distance=0
        for k,n in enumerate(path):
            if n not in xy:
                section=[];distance=0;continue
            barrier=nodes[n].get('tags',{})
            if barrier.get('barrier') in {'wall','fence'} or barrier.get('access') in {'private','no'} or barrier.get('foot')=='no':
                section=[];distance=0;continue
            if section: distance+=math.dist(xy[section[-1]],xy[n])
            section.append(n)
            end=k==len(path)-1 or use[n]>1 or distance>=55 or barrier.get('highway')=='crossing'
            if end and len(section)>1:
                line=LineString([xy[a] for a in section]); length=line.length
                if length>0.1 and city.covers(line):
                    explicit=tags['highway'] in PEDESTRIAN|{'cycleway'}
                    # Geometric samples on a centerline are marked approximate in API/UI.
                    ns=max(1,math.ceil(length/3)); positions=[line.interpolate((i+.5)*length/ns) for i in range(ns)]
                    pts=[(p.x,p.y) for p in positions]; tc=sample_canopy(pts); eid=len(edges)
                    edge={'id':eid,'u':section[0],'v':section[-1],'osm_id':w['id'],'name':tags.get('name') or ('Crosswalk' if tags.get('footway')=='crossing' else 'Walking path' if explicit else 'Local street'),
                          'coords':[coords[a] for a in section],'length':round(length,3),'highway':tags['highway'],
                          'crossing':tags.get('footway')=='crossing','steps':tags['highway']=='steps',
                          'geometry_quality':'mapped_path' if explicit else 'street_centerline',
                          'covered':tags.get('covered')=='yes' or tags.get('tunnel') in {'yes','building_passage'},
                          'foot_oneway':tags.get('oneway:foot','no'),'surface':tags.get('surface'),
                          'opening_hours':tags.get('opening_hours'),'access':tags.get('access','public/default'),
                          'canopy_fraction':sum(tc)/len(tc),'sample_start':len(sample_xy),'sample_count':ns}
                    # Conditional access is excluded until its hours can be evaluated correctly.
                    if edge['opening_hours'] or tags.get('access:conditional') or tags.get('foot:conditional'): continue
                    edges.append(edge);graph.add_edge(section[0],section[-1]);sample_xy.extend(pts);sample_tree.extend(tc);sample_edges.extend([eid]*ns)
                section=[n];distance=0
    components=sorted(nx.connected_components(graph),key=len,reverse=True)
    component_of={n:i for i,c in enumerate(components) for n in c}
    for e in edges: e['component']=component_of[e['u']]
    places=[]; buildings=[]
    for n,e in nodes.items():
        t=e.get('tags',{})
        if not t.get('name') or not any(k in t for k in ['amenity','shop','tourism','leisure','railway','public_transport','office','entrance']):continue
        if not boundary.covers(Point(e['lon'],e['lat'])):continue
        places.append({'id':f'n{n}','name':t['name'],'longitude':e['lon'],'latitude':e['lat'],'category':next((t[k] for k in ['amenity','shop','tourism','leisure','railway','office'] if k in t),'place'),'source':f'https://www.openstreetmap.org/node/{n}'})
    for w in ways.values():
        t=w.get('tags',{}); seq=w.get('nodes',[])
        if not t.get('building') or len(seq)<4 or not all(n in nodes for n in seq):continue
        poly=Polygon([(nodes[n]['lon'],nodes[n]['lat']) for n in seq]);poly=poly if poly.is_valid else poly.buffer(0)
        if poly.is_empty or not boundary.intersects(poly):continue
        height=None
        if t.get('height'):
            try:
                value=t['height'].lower().strip();height=float(value.replace('m','').strip()) if 'ft' not in value and "'" not in value else None
                if height is not None and not 2<=height<=400:height=None
            except ValueError: pass
        buildings.append({'id':w['id'],'geometry':mapping(poly),'height':height,'height_source':'OSM height tag' if height else None,'name':t.get('name')})
        if t.get('name'):
            p=poly.representative_point();places.append({'id':f'w{w["id"]}','name':t['name'],'longitude':p.x,'latitude':p.y,'category':t.get('amenity',t.get('building','building')),'source':f'https://www.openstreetmap.org/way/{w["id"]}'})
    live_nodes={str(n):coords[n] for n in graph.nodes}
    release=hashlib.sha256(json.dumps([dates,len(edges),len(buildings)]).encode()).hexdigest()[:12]
    (DATA/'graph.json').write_text(json.dumps({'nodes':live_nodes,'edges':edges,'release':release},separators=(',',':')))
    (DATA/'buildings.json').write_text(json.dumps(buildings,separators=(',',':')))
    (DATA/'places.json').write_text(json.dumps(places,separators=(',',':')))
    (DATA/'boundary.geojson').write_text(json.dumps({'type':'Feature','geometry':mapping(boundary),'properties':{}}))
    np.savez_compressed(DATA/'samples.npz',xy=np.array(sample_xy,dtype=np.float64),canopy=np.array(sample_tree,dtype=np.uint8),edge=np.array(sample_edges,dtype=np.int32))
    report={'release':release,'built_at':datetime.now(timezone.utc).isoformat(),'osm_timestamps':dates,'node_count':len(live_nodes),'edge_count':len(edges),'sample_count':len(sample_xy),'building_count':len(buildings),'osm_height_count':sum(b['height'] is not None for b in buildings),'place_count':len(places),'components':len(components),'largest_component_nodes':len(components[0]),'mapped_path_edges':sum(e['geometry_quality']=='mapped_path' for e in edges),'canopy_resolution_m':list(raster.res),'canopy_year':2023,'canopy_class':1,'canopy_interpretation':'Mapped crown cover, not a measured sunlight or seasonal shadow observation','warnings':['Street-centerline edges do not establish exact sidewalk position.','OSM access and crossings have not been field surveyed by this project.','2023 canopy may differ from current trees.','Zero pixels represent absence from the canopy mask inside the municipal study boundary; outside coverage is excluded.']}
    (DATA/'quality.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
