"""Explicit evidence model: original crown cover + sun-position building shadows.

Canopy is a map of crowns, not a measured direct-beam transmittance model. We
therefore return modeled cover and uncovered time, never a temperature reduction.
"""
import json, math
from datetime import datetime, timezone
from functools import lru_cache
import numpy as np
import pandas as pd
import pvlib
from shapely.geometry import shape, Polygon, box
from shapely.ops import unary_union
from shapely.affinity import translate
from shapely import STRtree, points
from services.geo import DATA, project

def swept_shadow(polygon, dx, dy):
    """Sweep every boundary edge; preserves concave shapes instead of a hull."""
    pieces=[polygon,translate(polygon,xoff=dx,yoff=dy)]
    polygons=list(polygon.geoms) if polygon.geom_type=='MultiPolygon' else [polygon]
    for poly in polygons:
        for ring in [poly.exterior,*poly.interiors]:
            for a,b in zip(ring.coords, list(ring.coords)[1:]):
                quad=Polygon([a,b,(b[0]+dx,b[1]+dy),(a[0]+dx,a[1]+dy)])
                if quad.area>0:pieces.append(quad)
    return unary_union(pieces)

class ShadeModel:
    def __init__(self,edges):
        self.edges=edges
        s=np.load(DATA/'samples.npz'); self.xy=s['xy'];self.canopy=s['canopy'].astype(bool);self.sample_edges=s['edge']
        self.point_geometries=points(self.xy)
        self.counts=np.bincount(self.sample_edges,minlength=len(edges))
        filename=DATA/'buildings-height.json'
        self.buildings=json.loads((filename if filename.exists() else DATA/'buildings.json').read_text())
        self.obstacles=[(project(shape(b['geometry'])),b['height']) for b in self.buildings if b.get('height')]
        self.height_count=len(self.obstacles)
        self.permanent=np.array([e['covered'] for e in edges])[self.sample_edges]
        self.region=None
        self.active_indices=np.arange(len(self.xy))

    def set_region(self,start,end,max_distance):
        # Every route within the time budget lies in this conservative rectangle:
        # its Euclidean excursion beyond either endpoint is at most half its length.
        # Round outward for reuse across nearby queries. Unknown areas stay canopy-only.
        pad=max_distance/2+50
        bounds=(math.floor((min(start.x,end.x)-pad)/500)*500,
                math.floor((min(start.y,end.y)-pad)/500)*500,
                math.ceil((max(start.x,end.x)+pad)/500)*500,
                math.ceil((max(start.y,end.y)+pad)/500)*500)
        if bounds==self.region:return
        self.region=bounds
        x,y=self.xy.T
        self.active_indices=np.flatnonzero((x>=bounds[0])&(y>=bounds[1])&(x<=bounds[2])&(y<=bounds[3]))
        self.profile.cache_clear()

    @staticmethod
    def sun(timestamp):
        result=pvlib.solarposition.get_solarposition(pd.DatetimeIndex([datetime.fromtimestamp(timestamp,timezone.utc)]),33.77,-84.39)
        return float(result['azimuth'].iloc[0]),float(result['apparent_elevation'].iloc[0])

    @lru_cache(maxsize=10)
    def profile(self,bucket):
        timestamp=bucket*300
        az,el=self.sun(timestamp)
        building=np.zeros(len(self.xy),dtype=bool)
        # Low sun requires a far larger occluder domain; withhold numerical shade.
        if el>5:
            azr=math.radians(az);tan=math.tan(math.radians(el));polys=[]
            for poly,h in self.obstacles:
                dist=max(0,h-1)/tan
                dx,dy=-math.sin(azr)*dist,-math.cos(azr)*dist
                if self.region:
                    a,b,c,d=poly.bounds;w,s,e,n=self.region
                    if c+max(0,dx)<w or a+min(0,dx)>e or d+max(0,dy)<s or b+min(0,dy)>n:continue
                polys.append(swept_shadow(poly,dx,dy))
            if polys:
                tree=STRtree(polys);pairs=tree.query(self.point_geometries[self.active_indices],predicate='intersects')
                if pairs.size:building[self.active_indices[np.unique(pairs[0])]]=True
        structural=building|self.permanent
        # Canopy count is not rescaled with arbitrary season or weather multipliers.
        cover=structural|self.canopy
        fractions=np.bincount(self.sample_edges,weights=cover,minlength=len(self.edges))/self.counts
        structural_fractions=np.bincount(self.sample_edges,weights=structural,minlength=len(self.edges))/self.counts
        return {'fraction':fractions,'structural':structural_fractions,'sample_cover':cover,'sample_building':structural,'elevation':el,'azimuth':az}

    def at(self,timestamp):return self.profile(int(timestamp//300))
