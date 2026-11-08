import {useEffect,useMemo,useRef,useState} from 'react';
import type {Snapshot} from '../types';
import {projectNodes} from '../viewport.mjs';
import {mapProjection} from '../geography.mjs';

/** One O(V) projection per graph/size change; edges use O(1) lookups. UI geometry only. */
export function useNetworkViewport(nodes:Snapshot['nodes'],bounds?:number[]){
  const frame=useRef<HTMLDivElement>(null);
  const [size,setSize]=useState({width:800,height:450}),[zoom,setZoom]=useState(1);
  const [center,setCenter]=useState<[number,number]|null>(null);
  useEffect(()=>{
    const element=frame.current;if(!element)return;
    const observer=new ResizeObserver(([entry])=>{const {width,height}=entry.contentRect;if(width&&height)setSize({width,height});});
    observer.observe(element);return()=>observer.disconnect();
  },[]);
  useEffect(()=>{setZoom(bounds&&size.width<760?1.7:1);setCenter(null);},[nodes.length,size.width,size.height,!!bounds]);
  const project=useMemo(()=>bounds?mapProjection(bounds,size.width,size.height,size.width<760?32:100):null,[bounds,size]);
  const points=useMemo(()=>project?new Map(nodes.map(n=>[n.id,project([n.x,n.y])])):projectNodes(nodes,size.width,size.height),[nodes,size,project]);
  const [cx,cy]=center??[size.width/2,size.height/2];
  return {frame,size,points,project,zoom,transform:`translate(${size.width/2} ${size.height/2}) scale(${zoom}) translate(${-cx} ${-cy})`,
    zoomBy:(delta:number)=>setZoom(z=>Math.max(1,Math.min(8,z+delta))),
    panBy:(dx:number,dy:number)=>setCenter(current=>{const [x,y]=current??[cx,cy];return [x-dx/zoom,y-dy/zoom];}),
    reset:()=>{setZoom(1);setCenter(null);},focus:(id:string)=>{setCenter(points.get(id)??null);setZoom(1.5);}};
}
