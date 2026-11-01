import type {Snapshot,Command,Connection} from '../types';
import {Badge,Icon} from './Common';
import {fmt} from '../presentation';

export function KPIStrip({data}:{data:Snapshot}){
  const delivered=data.orders.filter(o=>o.status==='delivered').length;
  const active=data.orders.filter(o=>!['cancelled','expired'].includes(o.status)).length;
  const pending=data.orders.filter(o=>o.status==='pending').length;
  const transit=data.orders.filter(o=>o.status==='in_transit').length;
  const moving=data.vehicles.filter(v=>v.current!==null).length;
  const entries=[{icon:'orders',title:'客户签收',value:`${delivered}`,unit:`/ ${active} 单`,caption:'实际签收，区别于计划接纳'},
    {icon:'inventory',title:'待处理订单',value:String(pending),unit:'单',caption:`运输中 ${transit} 单 · 已规划 ${data.orders.filter(o=>o.status==='planned').length} 单`},
    {icon:'fleet',title:'执行中车辆',value:String(moving),unit:`/ ${data.vehicles.length} 辆`,caption:'含行驶、装卸、服务及等待'},
    {icon:'clock',title:'模拟时刻',value:fmt(data.now),unit:'分钟',caption:data.needs_replan?'需要重规划':data.running?'按原子动作执行中':data.ready?'有效计划待出发':data.audit.complete_all?'客户已全部签收':'当前已停靠'}];
  return <section className="d-kpis" aria-label="调度核心指标">{entries.map(e=><article key={e.title}><div><span>{e.title}</span><strong>{e.value}<small>{e.unit}</small></strong><p>{e.caption}</p></div><span className="d-kpi-icon"><Icon name={e.icon} size={22}/></span></article>)}</section>;
}
export function DispatchToolbar({data,objective,setObjective,busy,connection,command,onResults,onCreate,playing,setPlaying}:{data:Snapshot;objective:string;setObjective:(v:string)=>void;busy:string;connection:Connection;command:Command;onResults:()=>void;onCreate:()=>void;playing:boolean;setPlaying:(v:boolean)=>void}){
  const unavailable=!!busy||connection!=='connected';
  let primary='规划路线',hint='先生成并验证配送计划，再开始配送。';
  let action:()=>void=()=>void command('plan',{objective});
  if(data.running){primary=data.needs_replan?'推进至检查点':'下一节点暂停';action=()=>void command(data.needs_replan?'step':'pause');hint=data.needs_replan?'进行中的原子动作完成后即可重新规划。':'车辆位置和载货由后端逐动作更新。';}
  else if(data.needs_replan){primary='重新规划';hint='保留真实位置和载货，在当前检查点构造续程。';}
  else if(data.plan&&data.orders.some(o=>o.status==='pending'&&!data.plan!.accepted.includes(o.id)&&!data.plan!.deferred.some(([id])=>id===o.id))){primary='规划待处理订单';hint='存在上次计划尚未考虑的新订单；旧计划保留，请先规划。';}
  else if(data.ready){primary='开始配送';action=()=>void command('depart');hint='计划已验证，签收将在真实服务动作完成后增加。';}
  else if(data.audit.complete_all){primary='查看结果';action=onResults;hint='客户已全部签收，查看历史审计和结果。';}
  else if(data.plan){primary='规划待处理订单';hint='旧计划保留为执行依据，可重新规划剩余订单。';}
  return <section className="d-dispatch-toolbar" aria-label="调度操作"><div className="d-target"><label htmlFor="dispatch-objective">规划目标</label><select id="dispatch-objective" value={objective} onChange={e=>setObjective(e.target.value)} disabled={!!busy}><option value="distance">最短距离</option><option value="cost">最低成本</option></select></div>
    <button className="d-primary" disabled={unavailable} onClick={action}>{busy?'处理中…':primary}<Icon name="arrow" size={16}/></button>
    <button disabled={unavailable||!data.running} onClick={()=>void command('step')} title={!data.running?'后端无进行中的动作':''}>单步推进</button>
    <button disabled={unavailable&&!playing||!data.running} onClick={()=>setPlaying(!playing)} title={!data.running?'开始配送后可自动调用后端step':''}>{playing?'暂停动画':'播放动画'}</button>
    <button className="d-quiet" onClick={onCreate} disabled={!!busy}>新建场景</button>
    <p className="d-toolbar-hint">{connection!=='connected'?'连接不可用；请先重新连接。':busy?'正在等待后端确认；请勿重复提交。':hint}</p>
  </section>;
}
export function PlanCoverage({data}:{data:Snapshot}){
  if(!data.plan)return null;
  return <div className="d-coverage"><Badge tone={data.plan.report.valid?'info':'danger'}>{data.plan.report.valid?'上次计划已验证':'计划验证异常'}</Badge><span>接纳 <b>{data.plan.accepted.length}</b> 单 · 未接纳 <b>{data.plan.deferred.length}</b> 单</span><span className="d-muted">计划接纳不代表客户已签收</span>{data.plan.traffic_version!==data.traffic_version&&<Badge tone="warn">路线 v{data.plan.traffic_version} / 当前交通 v{data.traffic_version}</Badge>}</div>;
}
