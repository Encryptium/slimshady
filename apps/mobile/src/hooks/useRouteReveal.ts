import {useEffect, useState} from 'react';
import type {Route} from '../lib/types';
import {revealRoute} from '../lib/routeReveal';
import {useReducedMotion} from './useReducedMotion';
const empty:Route['segments']={type:'FeatureCollection',features:[]};
export function useRouteReveal(route?:Route) {
  const reduced=useReducedMotion();
  const [frame,setFrame]=useState<{route?:Route;segments:Route['segments']}>({segments:empty});
  useEffect(()=>{
    if(!route||reduced!==false)return;
    let id=0,start=0,last=0;
    function tick(now:number){
      if(!start)start=now;
      const progress=Math.min(1,(now-start)/850);
      if(now-last>=30||progress===1){setFrame({route,segments:revealRoute(route!,1-Math.pow(1-progress,2))});last=now;}
      if(progress<1)id=requestAnimationFrame(tick);
    }
    id=requestAnimationFrame(tick);
    return()=>cancelAnimationFrame(id);
  },[route,reduced]);
  return !route?empty:reduced!==false?route.segments:frame.route===route?frame.segments:empty;
}
