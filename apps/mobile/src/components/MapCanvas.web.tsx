import React, {useEffect, useRef} from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {baseStyle, empty, pinFeatures, routeFeatures, type MapProps} from '../lib/map';
import {useRouteReveal} from '../hooks/useRouteReveal';
import {useReducedMotion} from '../hooks/useReducedMotion';

export default function MapCanvas(props:MapProps) {
  const container=useRef<HTMLDivElement>(null);
  const map=useRef<maplibregl.Map|null>(null);
  const current=useRef(props);
  useEffect(()=>{current.current=props;},[props]);
  const route=props.routes.find(r=>r.id===props.selected);
  const segments=useRouteReveal(route);
  const visibleSegments=useRef(segments);
  useEffect(()=>{visibleSegments.current=segments;},[segments]);
  const reduced=useReducedMotion();
  useEffect(()=>{
    if(!container.current)return;
    maplibregl.setWorkerUrl(new URL('/maplibre/maplibre-gl-worker.mjs',window.location.href).href);
    const m=new maplibregl.Map({container:container.current,style:baseStyle,center:[-84.387,33.779],zoom:14.2,attributionControl:{compact:true},maxBounds:[[-84.65,33.55],[-84.2,34.0]],minZoom:10});map.current=m;
    m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
    m.on('load',()=>{
      const p=current.current;
      m.addSource('alternatives',{type:'geojson',data:routeFeatures(p.routes,p.selected)});
      m.addSource('selected',{type:'geojson',data:visibleSegments.current});
      m.addSource('pins',{type:'geojson',data:pinFeatures(p.origin,p.destination,p.user)});
      m.addSource('step',{type:'geojson',data:empty});
      m.addLayer({id:'alt-case',type:'line',source:'alternatives',paint:{'line-color':'#ffffff','line-width':8}});
      m.addLayer({id:'alt',type:'line',source:'alternatives',paint:{'line-color':'#929d97','line-width':4,'line-dasharray':[2,1]}});
      m.addLayer({id:'selected-case',type:'line',source:'selected',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#fff','line-width':10}});
      m.addLayer({id:'selected-line',type:'line',source:'selected',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['interpolate',['linear'],['get','cover'],0,'#d49b5b',.4,'#9baf7f',.75,'#386d52',1,'#1a503c'],'line-width':6}});
      m.addLayer({id:'pin-circle',type:'circle',source:'pins',paint:{'circle-radius':['match',['get','kind'],2,8,11],'circle-color':['match',['get','kind'],0,'#fff',1,'#173d2d','#4e8edb'],'circle-stroke-color':'#173d2d','circle-stroke-width':3}});
      m.addLayer({id:'step-halo',type:'circle',source:'step',paint:{'circle-radius':17,'circle-color':'#315d43','circle-opacity':.16}});
      m.addLayer({id:'step-dot',type:'circle',source:'step',paint:{'circle-radius':7,'circle-color':'#315d43','circle-stroke-width':3,'circle-stroke-color':'#fff'}});
      m.setLayoutProperty('canopy','visibility',p.canopy?'visible':'none');
    });
    m.on('click',(e)=>{if(current.current.pickMode)current.current.onPick({longitude:e.lngLat.lng,latitude:e.lngLat.lat,name:'Dropped pin'});});
    const observer=new ResizeObserver(()=>m.resize());observer.observe(container.current);
    return()=>{observer.disconnect();m.remove();map.current=null;};
  },[]);
  useEffect(()=>{
    const m=map.current;if(!m?.getSource('selected'))return;
    (m.getSource('selected') as maplibregl.GeoJSONSource).setData(segments);
  },[segments]);
  useEffect(()=>{
    const m=map.current;if(!m?.getSource('pins'))return;
    (m.getSource('alternatives') as maplibregl.GeoJSONSource).setData(routeFeatures(props.routes,props.selected));
    (m.getSource('pins') as maplibregl.GeoJSONSource).setData(pinFeatures(props.origin,props.destination,props.user));
    m.setLayoutProperty('canopy','visibility',props.canopy?'visible':'none');
  },[props.routes,props.selected,props.origin,props.destination,props.user,props.canopy]);
  useEffect(()=>{
    const m=map.current;if(!m)return;
    const fit=()=>{
      const p=current.current;
      const mobile=m.getContainer().clientWidth<850;
      const height=m.getContainer().clientHeight;
      const padding={top:mobile?120:90,bottom:mobile?Math.min(height*.62+20,height-190):90,left:mobile?35:435,right:p.directionsDocked?360:50};
      const offset:[number,number]=[(padding.left-padding.right)/2,(padding.top-padding.bottom)/2];
      const step=p.stepFocus;
      (m.getSource('step') as maplibregl.GeoJSONSource|undefined)?.setData(step?{type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:step.coordinate},properties:{}}]}:empty);
      m.stop();
      if(step){m.easeTo({center:step.coordinate as [number,number],zoom:17,offset,duration:reduced?0:650});}
      else if(route){
        const b=new maplibregl.LngLatBounds();route.geometry.coordinates.forEach(c=>b.extend(c as [number,number]));
        m.fitBounds(b,{padding,maxZoom:16,linear:true,duration:reduced?0:750});
      }else if(p.user){m.easeTo({center:[p.user.longitude,p.user.latitude],zoom:16,offset,duration:reduced?0:650});}
    };
    if(m.getSource('selected'))fit();else m.once('load',fit);
    let resizeTimer:ReturnType<typeof setTimeout>;
    const resize=()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(fit,120);};
    window.addEventListener('resize',resize);
    return()=>{m.off('load',fit);window.removeEventListener('resize',resize);clearTimeout(resizeTimer);};
    // GPS updates move the position marker, not the user's camera.
  },[props.focus,route,props.directionsDocked,props.stepFocus,reduced]);
  return <div ref={container} style={{position:'absolute',inset:0,cursor:props.pickMode?'crosshair':'grab'}} aria-label="Atlanta walking map. Use the search fields or choose a point on the map."/>;
}
