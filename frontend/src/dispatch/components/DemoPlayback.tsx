import type {Snapshot} from '../types';
import {fmt} from '../presentation';

export function DemoPlayback({data,playing,busy,clock,speed,setSpeed,toggle}:{data:Snapshot;playing:boolean;busy:string;clock:number|null;speed:number;setSpeed:(v:number)=>void;toggle:()=>Promise<void>}){
  return <section className="d-demo-playback" aria-label="配送动画演示"><div><strong>配送过程演示</strong><p>{clock!==null?`回放已确认时段 · ${fmt(clock)} 分钟；指标在动作边界同步`:'按后端真实动作推进：装货 → 干线运输 → 到站卸货 → 末端配送 → 签收返仓'}</p></div>
    <label>播放倍速<select value={speed} onChange={e=>setSpeed(Number(e.target.value))} title="后续动作的动画倍速；不改变业务行驶时间">{[.5,1,2,4].map(s=><option key={s} value={s}>{s}×</option>)}</select></label>
    <button className="d-primary" disabled={!playing&&(!!busy||!data.running&&!data.ready)} onClick={()=>void toggle()} title="暂停会显示本次已确认动作的结果，然后停止后续推进">{playing?'暂停动画':'播放配送动画'}</button>
    <span className="d-demo-note">动画插值仅作演示，不是实时 GPS。车辆暂停请用“下一节点暂停”。</span>
  </section>;
}
