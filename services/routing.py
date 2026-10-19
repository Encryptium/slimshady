import json, math, time
from datetime import datetime
import numpy as np
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
from shapely import STRtree
from shapely.ops import substring
from services.geo import DATA, project, unproject
from services.shade import ShadeModel

class RouteError(ValueError):
    def __init__(self,code,message):self.code=code;super().__init__(message)

class Router:
    def __init__(self):
        d=json.loads((DATA/'graph.json').read_text());self.edges=d['edges'];self.nodes={int(k):v for k,v in d['nodes'].items()};self.release=d['release']
        self.boundary=shape(json.loads((DATA/'boundary.geojson').read_text())['geometry'])
        self.lines=[project(LineString(e['coords'])) for e in self.edges];self.index=STRtree(self.lines)
        self.graph=nx.MultiDiGraph()
        for e in self.edges:
            if e['foot_oneway']!='-1':self.graph.add_edge(e['u'],e['v'],key=e['id'],eid=e['id'],length=e['length'],reverse=False)
            if e['foot_oneway'] not in {'yes','1','true'}:self.graph.add_edge(e['v'],e['u'],key=e['id'],eid=e['id'],length=e['length'],reverse=True)
        self.shade=ShadeModel(self.edges)
        self.places=json.loads((DATA/('search.json' if (DATA/'search.json').exists() else 'places.json')).read_text());self.quality=json.loads((DATA/'quality.json').read_text())

    def snap(self,position,avoid_stairs):
        p=Point(position['longitude'],position['latitude'])
        if not self.boundary.covers(p):raise RouteError('OUTSIDE_COVERAGE','Choose a point inside the City of Atlanta coverage area.')
        q=project(p); candidates=self.index.query(q.buffer(80))
        ranked=[]
        for i in candidates:
            e=self.edges[i]
            if avoid_stairs and e['steps']:continue
            dist=self.lines[i].distance(q)
            if dist<=80:ranked.append((dist+(0 if e['geometry_quality']=='mapped_path' else 8),dist,int(i)))
        if not ranked:raise RouteError('NO_WALKABLE_ACCESS','No eligible mapped walking path within 80 meters. Pick a public path or entrance nearby.')
        _,distance,i=min(ranked);line=self.lines[i];offset=line.project(q); snapped=line.interpolate(offset)
        return {'eid':i,'offset':offset,'point':snapped,'distance':distance,'coords':list(unproject(snapped).coords)[0]}

    def query_graph(self,start,end,avoid_stairs):
        # Copy adjacency, split both endpoints together even when they lie on one edge.
        g=nx.DiGraph()
        for u,v,key,a in self.graph.edges(keys=True,data=True):
            e=self.edges[a['eid']]
            if avoid_stairs and e['steps']:continue
            if not g.has_edge(u,v) or a['length']<g[u][v]['length']:g.add_edge(u,v,**a,start=0.,stop=1.)
        groups={}
        for vid,s in [(-1,start),(-2,end)]:groups.setdefault(s['eid'],[]).append((s['offset']/self.lines[s['eid']].length,vid))
        for eid,interior in groups.items():
            e=self.edges[eid];p=[(0.,e['u']),*sorted(interior),(1.,e['v'])]
            for u,v in [(e['u'],e['v']),(e['v'],e['u'])]:
                if g.has_edge(u,v) and g[u][v]['eid']==eid:g.remove_edge(u,v)
            for (lo,u),(hi,v) in zip(p,p[1:]):
                data={'eid':eid,'length':(hi-lo)*e['length'],'start':lo,'stop':hi}
                if e['foot_oneway']!='-1':g.add_edge(u,v,**data,reverse=False)
                if e['foot_oneway'] not in {'yes','1','true'}:g.add_edge(v,u,**data,reverse=True)
        return g

    def duration(self,a,speed):
        e=self.edges[a['eid']]
        return a['length']/speed*(1.6 if e['steps'] else 1)+(15 if e['crossing'] and a['length']>1 else 0)

    def fraction(self,a,profile,kind='sample_cover'):
        e=self.edges[a['eid']];count=e['sample_count'];lo=e['sample_start']
        offsets=(np.arange(count)+.5)/count;mask=(offsets>=a['start'])&(offsets<=a['stop'])
        values=profile[kind][lo:lo+count]
        if mask.any():return float(values[mask].mean())
        return float(values[min(count-1,int((a['start']+a['stop'])/2*count))])

    def evaluate(self,g,path,departure,speed):
        elapsed=0.;segments=[];allcoords=[];covered=0.;distance=0.;exposure=0.;approx=0.;treecovered=0.
        for u,v in zip(path,path[1:]):
            a=g[u][v];e=self.edges[a['eid']];duration=self.duration(a,speed)
            profile=self.shade.at(departure+elapsed+duration/2)
            fraction=self.fraction(a,profile)
            line=substring(self.lines[e['id']],a['start'],a['stop'],normalized=True)
            if line.geom_type=='Point':continue
            coords=list(unproject(line).coords)
            if a['reverse']:coords.reverse()
            allcoords.extend(coords if not allcoords else coords[1:])
            length=a['length']; covered+=length*fraction; distance+=length;exposure+=duration*(1-fraction)
            treecovered+=length*e['canopy_fraction']
            if e['geometry_quality']=='street_centerline':approx+=length
            segments.append({'type':'Feature','geometry':{'type':'LineString','coordinates':coords},'properties':{'edgeId':e['id'],'osmWayId':e['osm_id'],'name':e['name'],'length':round(length,1),'seconds':round(duration,1),'cover':round(fraction,3),'treeCover':round(e['canopy_fraction'],3),'geometryQuality':e['geometry_quality'],'crossing':e['crossing'],'steps':e['steps'],'startSeconds':round(elapsed,1)}})
            elapsed+=duration
        instructions=[]
        previous=None
        for seg in segments:
            p=seg['properties'];name=p['name']
            if name!=previous or p['crossing']:
                instructions.append({'text':('Use the mapped crossing on ' if p['crossing'] else 'Take the steps on ' if p['steps'] else 'Continue on ')+name,'coordinate':seg['geometry']['coordinates'][0],'atMeters':0,'seconds':p['startSeconds']})
                previous=name
        # Geometric progress for guidance, independent of GPS ETA assumptions.
        total=0;at_by_time={}
        for s in segments:at_by_time[s['properties']['startSeconds']]=total;total+=s['properties']['length']
        for step in instructions:step['atMeters']=round(at_by_time[step['seconds']],1)
        if allcoords:instructions.append({'text':'Arrive at the mapped destination access point','coordinate':allcoords[-1],'atMeters':round(distance,1),'seconds':round(elapsed,1)})
        return {'distanceMeters':round(distance,1),'durationSeconds':round(elapsed,1),'uncoveredSeconds':round(exposure,1),'coverFraction':round(covered/max(1,distance),3),'treeCoverFraction':round(treecovered/max(1,distance),3),'approximateGeometryFraction':round(approx/max(1,distance),3),'geometry':{'type':'LineString','coordinates':allcoords},'segments':{'type':'FeatureCollection','features':segments},'instructions':instructions,'edgeIds':[g[u][v]['eid'] for u,v in zip(path,path[1:])]}

    def route(self,request):
        tick=time.monotonic();dep=datetime.fromisoformat(request['departureTime'].replace('Z','+00:00')).timestamp();speed=request.get('walkingSpeedMps',1.3)
        prefs=request.get('preferences',{});avoid=prefs.get('avoidStairs',False)
        start=self.snap(request['origin'],avoid);end=self.snap(request['destination'],avoid)
        if start['point'].distance(end['point'])<5:raise RouteError('SAME_LOCATION','Choose two different locations at least 5 meters apart.')
        g=self.query_graph(start,end,avoid)
        def cost(u,v,a):return self.duration(a,speed)
        try:fast=nx.shortest_path(g,-1,-2,weight=cost)
        except (nx.NetworkXNoPath,nx.NodeNotFound):raise RouteError('NO_CONNECTED_ROUTE','These points are not connected by the eligible walking network. Try another public entrance.')
        tfast=sum(self.duration(g[u][v],speed) for u,v in zip(fast,fast[1:]))
        if tfast>10800:raise RouteError('TRIP_TOO_LONG','Please choose a walk under three hours.')
        self.shade.set_region(start['point'],end['point'],speed*(tfast+min(tfast*.6,900)))
        fast_result=self.evaluate(g,fast,dep,speed);tfast=fast_result['durationSeconds']
        sun=self.shade.at(dep);night=sun['elevation']<=0;low_sun=0<sun['elevation']<=5
        candidates=[fast_result];seen={tuple(fast_result['edgeIds'])}
        # Static candidate search is explicitly approximate. Rescore at arrival times.
        if not night and not low_sun:
            for weight in [.5,1,2,4,8,16]:
                def weighted(u,v,a):return self.duration(a,speed)*(1+weight*(1-sun['fraction'][a['eid']]))
                path=nx.shortest_path(g,-1,-2,weight=weighted)
                key=tuple(g[u][v]['eid'] for u,v in zip(path,path[1:]))
                if key in seen:continue
                seen.add(key);r=self.evaluate(g,path,dep,speed)
                if r['durationSeconds']<=tfast+min(tfast*.6,900):candidates.append(r)
        extra=min(float(prefs.get('maxExtraRatio',.2))*tfast,float(prefs.get('maxExtraSeconds',300)))
        best=lambda budget:min((r for r in candidates if r['durationSeconds']<=tfast+budget+.5),key=lambda r:(r['uncoveredSeconds'],r['durationSeconds']))
        recommended=best(extra);shadefirst=best(min(tfast*.4,600));chosen=[]
        for kind,r in [('fastest',fast_result),('recommended',recommended),('shade',shadefirst)]:
            existing=next((v for v in chosen if v['edgeIds']==r['edgeIds']),None)
            if existing:
                existing['badges'].append(kind)
                continue
            item={**r,'id':kind,'kind':kind,'badges':[kind],'extraSeconds':round(r['durationSeconds']-tfast,1),'savedUncoveredSeconds':round(fast_result['uncoveredSeconds']-r['uncoveredSeconds'],1)}
            if night:item['uncoveredSeconds']=0;item['savedUncoveredSeconds']=0;item['coverFraction']=None
            if low_sun:item['uncoveredSeconds']=None;item['savedUncoveredSeconds']=None;item['coverFraction']=None
            chosen.append(item)
        warnings=['Tree cover uses the original 2023 crown map; tree shadow movement and leaf loss are not yet modeled.','Building shadows use available measured or OSM heights; missing heights are not fabricated.','Access and crossings come from OSM and have not been field-verified by this project.']
        if any(r['approximateGeometryFraction']>.01 for r in chosen):warnings.append('Part of this route follows a street centerline: exact sidewalk shade is uncertain. Follow actual sidewalks and legal crossings.')
        if start['distance']>10 or end['distance']>10:warnings.append('Pins were snapped to mapped paths. The approach between each pin and path is not verified or included in guidance.')
        if night:warnings.append('No direct sunlight expected at departure. Choose by walking time; nighttime safety is not modeled.')
        if low_sun:warnings.append('Sun is too low for a reliable shadow estimate. Shade metrics are withheld.')
        localmonth=datetime.fromtimestamp(dep).month
        if localmonth in {11,12,1,2,3}:warnings.append('Leaf-off season: the leaf-on canopy map may substantially overestimate cover.')
        return {'routes':chosen,'departureTime':request['departureTime'],'timeZone':'America/New_York','release':self.release,'model':'2023 mapped crown cover + geometric building shadows','approximateSearch':True,'candidateCount':len(candidates),'night':night,'lowSun':low_sun,'sunElevation':round(sun['elevation'],1),'warnings':warnings,'snapped':{'origin':{'coordinate':start['coords'],'distanceMeters':round(start['distance'],1)},'destination':{'coordinate':end['coords'],'distanceMeters':round(end['distance'],1)}},'processingMs':round((time.monotonic()-tick)*1000)}
