import {useEffect,useMemo,useRef,useState} from 'react';
import type {Snapshot} from '../types';
import {projectNodes} from '../viewport.mjs';

/** One O(V) projection per graph/size change; edges use O(1) lookups. UI geometry only. */
export function useNetworkViewport(nodes:Snapshot['nodes']){
  const frame=useRef<HTMLDivElement>(null);
  const [size,setSize]=useState({width:800,height:450}),[zoom,setZoom]=useState(1);
  const [center,setCenter]=useState<[number,number]|null>(null);
  useEffect(()=>{
    const element=frame.current;if(!element)return;
    const observer=new ResizeObserver(([entry])=>{const {width,height}=entry.contentRect;if(width&&height)setSize({width,height});});
    observer.observe(element);return()=>observer.disconnect();
  },[]);
  useEffect(()=>{setZoom(1);setCenter(null);},[nodes.length,size.width,size.height]);
  const points=useMemo(()=>projectNodes(nodes,size.width,size.height),[nodes,size]);
  const [cx,cy]=center??[size.width/2,size.height/2];
  return {frame,size,points,zoom,transform:`translate(${size.width/2} ${size.height/2}) scale(${zoom}) translate(${-cx} ${-cy})`,
    zoomBy:(delta:number)=>setZoom(z=>Math.max(1,Math.min(2.5,z+delta))),
    reset:()=>{setZoom(1);setCenter(null);},focus:(id:string)=>{setCenter(points.get(id)??null);setZoom(1.5);}};
}
