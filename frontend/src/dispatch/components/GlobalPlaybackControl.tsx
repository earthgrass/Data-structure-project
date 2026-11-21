import type {Snapshot} from '../types';

export function GlobalPlaybackControl({data,playing,busy,connected,objective,toggle,plan}:{data:Snapshot|null;playing:boolean;busy:string;connected:boolean;objective:string;toggle:()=>Promise<void>;plan:()=>Promise<boolean>}){
  const automatic=data?.order_control?.status==='waiting_checkpoint';
  const blocked=data?.order_control?.status==='blocked';
  const complete=!data?.running&&data?.audit.complete_all;
  const needsPlan=!!data&&!data.ready&&!data.running&&!complete;
  const label=automatic?'自动停靠中':blocked?'规划受阻':playing?'暂停配送':data?.running?'继续配送':data?.ready?'开始配送':complete?'配送完成':'规划路线';
  const disabled=!data||!connected||!!busy||!!automatic||!!blocked||!!complete;
  return <button className={'d-global-playback'+(playing?' is-playing':'')} disabled={disabled} onClick={()=>{if(needsPlan)void plan();else void toggle();}} title={playing?'停止自动推进；已确认的当前动作仍会完整显示':needsPlan?`按${objective==='cost'?'最低成本':'最短距离'}生成并验证计划`:'在当前会话继续自动推进'} aria-label={label}><span aria-hidden="true">{playing?'Ⅱ':needsPlan?'↗':'▶'}</span>{label}</button>;
}
