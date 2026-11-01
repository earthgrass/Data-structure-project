import {useCallback,useEffect,useRef,useState} from 'react';
import type {Snapshot} from '../types';
import {segmentDuration} from '../motion.mjs';

/** Replay only an interval ALREADY confirmed by a successful backend step.
 * All vehicles share that interval's clock. Cancelling snaps to its confirmed end.
 */
export function useConfirmedMotion(){
  const [clock,setClock]=useState<number|null>(null),[speed,setSpeed]=useState(1);
  const cancel=useRef<(()=>void)|null>(null),speedRef=useRef(speed);speedRef.current=speed;
  const stop=useCallback(()=>cancel.current?.(),[]);
  const play=useCallback((before:Snapshot,after:Snapshot)=>new Promise<void>(resolve=>{
    const duration=segmentDuration(before.now,after.now,speedRef.current,matchMedia('(prefers-reduced-motion: reduce)').matches);
    if(duration===0){resolve();return;}
    let frame=0,finished=false;const start=performance.now();
    const finish=()=>{if(finished)return;finished=true;cancelAnimationFrame(frame);cancel.current=null;setClock(null);resolve();};
    cancel.current=finish;setClock(before.now);
    const tick=(now:number)=>{if(finished)return;const ratio=Math.min(1,(now-start)/duration);setClock(before.now+(after.now-before.now)*ratio);if(ratio===1)finish();else frame=requestAnimationFrame(tick);};
    frame=requestAnimationFrame(tick);
  }),[]);
  useEffect(()=>()=>stop(),[stop]);
  return {clock,speed,setSpeed,play,stop};
}
