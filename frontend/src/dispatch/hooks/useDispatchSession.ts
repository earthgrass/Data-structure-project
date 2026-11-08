import {useCallback,useEffect,useRef,useState} from 'react';
import type {Snapshot,Comparison,Connection} from '../types';
import {bindComparison,reconcileSnapshot,failureFeedback} from '../sync.mjs';
import {useConfirmedMotion} from './useConfirmedMotion';

class RequestError extends Error {
  constructor(public status:number,message:string){super(message);}
}
async function request(path:string,payload?:unknown,base='/api/v2'):Promise<Snapshot>{
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),15000);
  try{
    const response=await fetch(base+path,{signal:controller.signal,...(payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})});
    const value=await response.json();
    if(!response.ok){
      const original=value.error?.message??`请求失败（${response.status}）`;
      const translated:Record<string,string>={'order ID already used':'订单 ID 已存在，请使用新的唯一 ID。','integer seed required':'Seed 必须是整数。','deadline is not in the future':'签收截止必须晚于当前模拟时刻。'};
      throw new RequestError(response.status,translated[original]??original);
    }
    return value;
  }finally{clearTimeout(timer);}
}
const messages:Record<string,string>={plan:'新计划已独立验证并应用；签收进度仍以实际执行为准。',compare:'双目标比较已完成，结果绑定当前会话和版本。',depart:'配送已开始。',step:'已完成一个真实原子动作。',pause:'已请求暂停；进行中的原子动作将在检查点完成。',add:'订单已加入待处理队列，尚需规划接纳。',automatic:'自动订单已入队，尚需规划接纳。',cancel:'订单已取消，其余任务需重新规划。',expire:'订单已显式过期。',priority:'优先级已更新，请在检查点重新规划。',traffic:'所选方向的交通已更新，请完成已进入动作后重规划。'};

export function useDispatchSession(){
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[comparison,setComparison]=useState<Comparison|null>(null);
  const [connection,setConnection]=useState<Connection>('connecting'),[busy,setBusy]=useState(''),[error,setError]=useState(''),[message,setMessage]=useState('');
  const [playing,setPlaying]=useState(false);
  const motion=useConfirmedMotion();
  const setPlayback=useCallback((value:boolean)=>{setPlaying(value);if(!value)motion.stop();},[motion.stop]);
  const live=useRef<{snapshot:Snapshot|null;comparison:Comparison|null}>({snapshot:null,comparison:null});
  const active=useRef(''),epoch=useRef(0),locked=useRef(false);
  const receive=useCallback((incoming:Snapshot,ticket:number)=>{
    if(ticket!==epoch.current)return;
    const next=reconcileSnapshot(live.current.snapshot,live.current.comparison,incoming,active.current);
    if(next.snapshot!==incoming)return;
    if(incoming.comparison)next.comparison=bindComparison(incoming,incoming.comparison);
    live.current=next;setSnapshot(next.snapshot);setComparison(next.comparison);setConnection('connected');
  },[]);
  const failed=useCallback((exception:unknown,ticket:number)=>{
    if(ticket!==epoch.current)return false;
    setPlaying(false);
    live.current.comparison=null;setComparison(null);
    const feedback=failureFeedback(exception instanceof RequestError?exception.status:null,exception instanceof Error?exception.message:String(exception));
    setConnection(feedback.connection);setError(feedback.error);return feedback.refresh;
  },[]);
  const refresh=useCallback(async(clear=true,allowLocked=false)=>{
    const ticket=epoch.current,id=active.current;
    try{if(id){const incoming=await request(`/sessions/${id}`);if(locked.current&&!allowLocked)return;receive(incoming,ticket);}else{await request('/health',undefined,'/api');if(ticket===epoch.current)setConnection('connected');}if(clear)setError('');}
    catch(e){if(!locked.current||allowLocked)failed(e,ticket);}
  },[receive,failed]);
  useEffect(()=>{
    active.current=sessionStorage.getItem('logiroute-session')??'';
    void refresh();
    const timer=setInterval(()=>{if(!locked.current)void refresh(false);},2000);
    return()=>clearInterval(timer);
  },[refresh]);
  const create=useCallback(async(seed:string)=>{
    if(locked.current)return false;
    locked.current=true;setBusy('create');setPlaying(false);setError('');setMessage('');setConnection('connecting');
    const ticket=++epoch.current;
    try{
      const incoming=await request('/sessions',{profile:'bjut',...(seed===''?{}:{seed:Number(seed)})});
      active.current=incoming.id;sessionStorage.setItem('logiroute-session',incoming.id);
      live.current={snapshot:null,comparison:null};receive(incoming,ticket);setMessage('新场景已创建，等待规划。');return true;
    }catch(e){failed(e,ticket);return false;}finally{locked.current=false;setBusy('');}
  },[receive,failed]);
  const command=useCallback(async(kind:string,fields:Record<string,unknown>={})=>{
    if(locked.current||!live.current.snapshot)return false;
    const ticket=epoch.current,id=active.current;
    locked.current=true;setBusy(kind);setError('');if(kind!=='step')setPlaying(false);
    try{
      const before=live.current.snapshot;
      const incoming=await request(`/sessions/${id}/commands`,{revision:before.revision,command:kind,...fields});
      if(kind==='step'&&ticket===epoch.current)await motion.play(before,incoming);
      receive(incoming,ticket);setMessage(messages[kind]??'操作完成。');return true;
    }catch(e){if(failed(e,ticket))await refresh(false,true);return false;}
    finally{locked.current=false;setBusy('');}
  },[receive,failed,refresh,motion.play]);
  useEffect(()=>{
    if(!playing||!snapshot?.running||busy)return;
    const timer=setTimeout(()=>void command('step'),100);
    return()=>clearTimeout(timer);
  },[playing,snapshot,busy,command]);
  useEffect(()=>{if(!snapshot?.running)setPlaying(false);},[snapshot?.running]);
  useEffect(()=>{if(!message)return;const timer=setTimeout(()=>setMessage(''),6000);return()=>clearTimeout(timer);},[message]);
  const togglePlayback=async()=>{
    if(playing){setPlayback(false);return;}
    if(live.current.snapshot?.ready){if(!await command('depart'))return;}
    setPlayback(true);
  };
  return {snapshot,comparison,connection,busy,error,message,playing,setPlaying:setPlayback,create,command,
    motionClock:motion.clock,speed:motion.speed,setSpeed:motion.setSpeed,togglePlayback,
    reconnect:()=>{setConnection('connecting');void refresh();}};
}
