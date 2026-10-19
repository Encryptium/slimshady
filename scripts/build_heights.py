"""Derive roof/ground heights from classified USGS returns, never guessed levels.

Each 1 km source tile is rasterized at 2 m. Only class-6 building returns can
establish a roof; class-2 returns establish local ground. No-return buildings
retain an unknown height. The 2018 acquisition age stays visible in metadata.
"""
import json,sys,time
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import laspy,numpy as np
from scipy.ndimage import distance_transform_edt
from pyproj import Transformer
from shapely.geometry import shape,box
from shapely.ops import transform
from shapely import STRtree,contains_xy
from services.geo import RAW,DATA

def main():
    start=time.monotonic();buildings=json.loads((DATA/'buildings.json').read_text())
    project=Transformer.from_crs(4326,6350,always_xy=True).transform
    polys=[transform(project,shape(b['geometry'])) for b in buildings];index=STRtree(polys)
    evidence=defaultdict(list);files=sorted((RAW/'lidar').glob('*.laz'))
    print('Deriving heights from',len(files),'original USGS tiles',flush=True)
    for number,file in enumerate(files):
        las=laspy.read(file)
        crs=las.header.parse_crs()
        if not crs or crs.sub_crs_list[0].to_epsg()!=6350:raise ValueError(f'Unexpected source CRS in {file}')
        if crs.sub_crs_list[1].axis_info[0].unit_name!='metre':raise ValueError('Unrecognized vertical units')
        x=np.asarray(las.x);y=np.asarray(las.y);z=np.asarray(las.z);classification=np.asarray(las.classification)
        west=np.floor(x.min()/2)*2;south=np.floor(y.min()/2)*2
        w=int(np.floor((x.max()-west)/2))+1;h=int(np.floor((y.max()-south)/2))+1
        col=np.floor((x-west)/2).astype(int);row=np.floor((y-south)/2).astype(int);flat=row*w+col
        ground=np.full(h*w,np.inf,dtype=np.float32);roof=np.full(h*w,-np.inf,dtype=np.float32)
        np.minimum.at(ground,flat[classification==2],z[classification==2])
        np.maximum.at(roof,flat[classification==6],z[classification==6])
        ground=ground.reshape(h,w);roof=roof.reshape(h,w)
        distances,nearest=distance_transform_edt(~np.isfinite(ground),return_indices=True)
        filled=ground[nearest[0],nearest[1]]
        tile=box(west,south,west+2*w,south+2*h)
        for bid in index.query(tile,predicate='intersects'):
            poly=polys[bid];xmin,ymin,xmax,ymax=poly.bounds
            c0=max(0,int((xmin-west)//2));c1=min(w,int((xmax-west)//2)+1)
            r0=max(0,int((ymin-south)//2));r1=min(h,int((ymax-south)//2)+1)
            if c0>=c1 or r0>=r1:continue
            rr,cc=np.mgrid[r0:r1,c0:c1]
            interior=contains_xy(poly,west+(cc+.5)*2,south+(rr+.5)*2)
            good=interior & np.isfinite(roof[r0:r1,c0:c1]) & np.isfinite(filled[r0:r1,c0:c1]) & (distances[r0:r1,c0:c1]<=15)
            heights=roof[r0:r1,c0:c1][good]-filled[r0:r1,c0:c1][good]
            heights=heights[(heights>=2)&(heights<350)]
            if len(heights)>=4:evidence[int(bid)].extend(heights.tolist())
        print(number+1,'/',len(files),file.stem.split('_')[-1],len(evidence),'footprints with classified roof evidence',flush=True)
    matched=0;added=0
    for bid,heights in evidence.items():
        if len(heights)<6:continue
        value=float(np.percentile(heights,90));b=buildings[bid]
        b['lidar_height']=round(value,2);b['lidar_cells']=len(heights);b['lidar_acquisition_year']=2018
        matched+=1
        if b.get('height') is None:
            b['height']=round(value,2);b['height_source']='USGS 3DEP 2018: class-6 roof / class-2 local ground';added+=1
    output=DATA/'buildings-height.json';temp=output.with_suffix('.tmp');temp.write_text(json.dumps(buildings,separators=(',',':')));temp.replace(output)
    report={'source':'USGS GA_Statewide_2018_B18_DRRA / GA_Statewide_B2_2018','acquisition_year':2018,'tiles_processed':len(files),'matched_buildings':matched,'new_measured_heights':added,'total_available_heights':sum(b.get('height') is not None for b in buildings),'method':'90th percentile 2-meter classified roof elevation minus nearest classified local ground, maximum ground interpolation distance 30 m; minimum 6 roof cells. Existing OSM heights retained.','horizontal_crs':'EPSG:6350','vertical_datum':'NAVD88, Geoid12B, metres','duration_seconds':round(time.monotonic()-start),'limitations':['2018 structures can differ from present buildings.','2.5D footprint extrusion approximates roof geometry.','Ground interpolation and roof rasterization introduce error.','No field validation performed.']}
    (DATA/'height-quality.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
