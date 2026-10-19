import React,{useRef,useEffect} from 'react';
import {Map,Camera,GeoJSONSource,Layer,type CameraRef} from '@maplibre/maplibre-react-native';
import {useRouteReveal} from '../hooks/useRouteReveal';
import {useReducedMotion} from '../hooks/useReducedMotion';
import {baseStyle,pinFeatures,routeFeatures,type MapProps} from '../lib/map';
export default function MapCanvas(p:MapProps){
  const camera=useRef<CameraRef>(null);
  const selected=p.routes.find(r=>r.id===p.selected);
  const segments=useRouteReveal(selected);
  const reduced=useReducedMotion();
  const current=useRef(p);useEffect(()=>{current.current=p;},[p]);
  useEffect(()=>{if(p.stepFocus){camera.current?.flyTo({center:p.stepFocus.coordinate as [number,number],zoom:17,duration:reduced?0:650});}else if(selected){const c=selected.geometry.coordinates;camera.current?.fitBounds([Math.min(...c.map(p=>p[0])),Math.min(...c.map(p=>p[1])),Math.max(...c.map(p=>p[0])),Math.max(...c.map(p=>p[1]))],{padding:{top:100,bottom:360,left:40,right:40},duration:reduced?0:750});}else if(current.current.user)camera.current?.flyTo({center:[current.current.user.longitude,current.current.user.latitude],zoom:16,duration:reduced?0:650});},[p.focus,p.stepFocus,selected,reduced]);
  const style={...baseStyle,layers:baseStyle.layers.map(l=>l.id==='canopy'?{...l,layout:{visibility:p.canopy?'visible' as const:'none' as const}}:l)};
  return <Map style={{flex:1}} mapStyle={style} onPress={e=>{if(p.pickMode)p.onPick({longitude:e.nativeEvent.lngLat[0],latitude:e.nativeEvent.lngLat[1],name:'Dropped pin'});}}>
    <Camera ref={camera} initialViewState={{center:[-84.392,33.777],zoom:14}}/>
    <GeoJSONSource id="alternatives" data={routeFeatures(p.routes,p.selected)}><Layer id="alternatives-line" type="line" paint={{'line-color':'#929d97','line-width':5,'line-dasharray':[2,1]}}/></GeoJSONSource>
    <GeoJSONSource id="selected" data={segments}>
      <Layer id="route-case" type="line" paint={{'line-color':'white','line-width':10}}/>
      <Layer id="route" type="line" paint={{'line-color':['interpolate',['linear'],['get','cover'],0,'#d49b5b',.75,'#386d52',1,'#1a503c'],'line-width':6}}/>
    </GeoJSONSource>
    <GeoJSONSource id="pins" data={pinFeatures(p.origin,p.destination,p.user)}><Layer id="pin" type="circle" paint={{'circle-radius':9,'circle-color':['match',['get','kind'],0,'white',1,'#173d2d','#4e8edb'],'circle-stroke-color':'#173d2d','circle-stroke-width':3}}/></GeoJSONSource>
  </Map>;
}
