import {useEffect,useRef,useState} from 'react';
import type {Command,Connection,Snapshot} from '../types';
import {autoTrafficChoice} from '../auto-traffic.mjs';

/** Opt-in browser timer; every simulated event uses the authoritative traffic command. */
export function useAutoTraffic(data:Snapshot|null,connection:Connection,busy:string,command:Command){
  const [enabled,setEnabled]=useState(false),[count,setCount]=useState(0);
  const tick=useRef(0),inFlight=useRef(false);
  const latest=useRef({data,connection,busy,command});
  latest.current={data,connection,busy,command};
  useEffect(()=>{setEnabled(false);setCount(0);tick.current=0;},[data?.id]);
  const interval=data?.settings.simulated_traffic?.interval_seconds;
  const seed=data?.settings.simulated_traffic?.seed;
  useEffect(()=>{
    if(!enabled||!interval||seed===undefined)return;
    const timer=window.setInterval(()=>{
      const current=latest.current,snapshot=current.data;
      if(inFlight.current||document.hidden||current.busy||current.connection!=='connected'||!snapshot?.plan
          ||!snapshot.plan.report.safe_to_apply||snapshot.needs_replan
          ||snapshot.order_control?.status==='blocked'||snapshot.order_control?.status==='waiting_checkpoint'
          ||!snapshot.orders.some(order=>['pending','planned','in_transit'].includes(order.status)))return;
      const choice=autoTrafficChoice(snapshot,seed,tick.current);
      if(!choice)return;
      inFlight.current=true;
      const sessionId=snapshot.id;
      void current.command('traffic',choice).then(success=>{
        if(latest.current.data?.id!==sessionId)return;
        if(success){tick.current+=1;setCount(tick.current);}else setEnabled(false);
      }).finally(()=>{inFlight.current=false;});
    },interval*1000);
    return()=>window.clearInterval(timer);
  },[enabled,interval,seed,data?.id]);
  return {enabled,setEnabled,count};
}
