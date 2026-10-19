"""Index actual OSM named areas and street access points; never invent addresses."""
import json, sys, re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collections import defaultdict
import httpx
from shapely.geometry import Point, shape
from services.geo import DATA, RAW
from services.search import enrich_locations
from scripts.acquire_data import save_meta

def main():
    path=RAW/'osm-named-areas.json'
    if not path.exists():
        query='[out:json][timeout:90];(nwr["name"]["leisure"](33.64,-84.56,33.90,-84.28);rel["name"]["building"](33.64,-84.56,33.90,-84.28);way["name"]["amenity"](33.64,-84.56,33.90,-84.28););out center tags;'
        url='https://overpass-api.de/api/interpreter'
        with httpx.Client(timeout=240,headers={'User-Agent':'ShadeATL/0.1 source ingestion'}) as c:
            r=c.get(url,params={'data':query});r.raise_for_status();result=r.json()
            if 'remark' in result:raise ValueError(result['remark'])
            path.write_bytes(r.content)
        save_meta('osm-named-areas',url,path,{'query':query,'license':'ODbL 1.0 / OpenStreetMap contributors'})
    boundary=shape(json.loads((DATA/'boundary.geojson').read_text())['geometry'])
    places=json.loads((DATA/'places.json').read_text());known={p['id'] for p in places}
    for e in json.loads(path.read_text(encoding='utf-8'))['elements']:
        t=e.get('tags',{});p=e.get('center');eid=e['type'][0]+str(e['id'])
        if eid in known or not p or not t.get('name') or not boundary.covers(Point(p['lon'],p['lat'])):continue
        if not any(k in t for k in ['leisure','amenity','building','tourism','shop']):continue
        places.append({'id':eid,'name':t['name'],'longitude':p['lon'],'latitude':p['lat'],'category':next((t[k] for k in ['leisure','amenity','tourism','shop'] if k in t),'building'),'source':f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}'})
        known.add(eid)
    groups=defaultdict(list)
    graph_edges=json.loads((DATA/'graph.json').read_text())['edges']
    for edge in graph_edges:
        if edge['name'] not in {'Walking path','Local street','Crosswalk'}:groups[edge['name']].append(edge)
    for name,edges in groups.items():
        # Several real access locations on long streets; no interpolated addresses.
        cells={}
        for edge in edges:
            p=edge['coords'][len(edge['coords'])//2];key=(round(p[0]*250),round(p[1]*250))
            cells.setdefault(key,(p,edge))
        for key,(p,e) in cells.items():
            places.append({'id':f's{e["id"]}','name':name,'longitude':p[0],'latitude':p[1],'category':'street · mapped access point','source':f'https://www.openstreetmap.org/way/{e["osm_id"]}'})
    enrich_locations(places, RAW, graph_edges)
    (DATA/'search.json').write_text(json.dumps(places,separators=(',',':')))
    print(f'Indexed {len(places)} real OSM places and street access points.')
if __name__=='__main__':main()
