import type {Snapshot,Vehicle} from '../types';
import {labels,fmt,vehicleColor} from '../presentation';
import {actionPhase} from '../sync.mjs';
import {Badge,Icon} from './Common';

function LoadBar({car}:{car:Vehicle}){
  const ratio=Number(car.load)/Number(car.capacity);
  // Visualization only; exact text is preserved, never used for a capacity decision.
  return <div className="d-load-track" role="img" aria-label={`载货 ${car.load}，容量 ${car.capacity}；进度为示意比例`}><span style={{width:`${Number.isFinite(ratio)?Math.max(0,Math.min(100,ratio*100)):0}%`}}/></div>;
}
export function FleetList({data,selected,onSelect,compact=false}:{data:Snapshot;selected:string;onSelect:(id:string)=>void;compact?:boolean}){
  return <div className={'d-fleet-list '+(compact?'compact':'')} aria-label="车辆选择">{data.vehicles.map(v=><button key={v.id} className={'d-vehicle '+(v.id===selected?'selected':'')} aria-pressed={v.id===selected} onClick={()=>onSelect(v.id)} style={{'--car-color':vehicleColor(data,v.id)} as React.CSSProperties}>
    <div className="d-vehicle-top"><span className="d-vehicle-icon"><Icon name="fleet" size={22}/></span><strong>{v.id}</strong><Badge tone={v.current?'info':'neutral'}>{v.current?labels[v.current.kind]:'停靠'}</Badge></div>
    <div className="d-vehicle-role">{v.role==='trunk'?'干线补货':'末端配送'} · 基地 {v.base}</div>
    <div className="d-load-label"><span>实际装载</span><b>{v.load} <small>/ {v.capacity}</small></b></div><LoadBar car={v}/>
    <div className="d-vehicle-position"><Icon name="pin" size={16}/>{v.position}<span>{v.cargo.length} 单在车</span></div>
  </button>)}</div>;
}
export function RouteTimeline({data,car}:{data:Snapshot;car:Vehicle}){
  const route=data.plan?.routes.find(r=>r.vehicle===car.id);
  const names={current:'当前动作',completed:'已完成',paused:'待重规划',pending:'未执行',unknown:'阶段未确认'};
  if(!route?.actions.length)return <p className="d-muted d-pad">暂无配送行程；闲置车辆没有虚构任务。</p>;
  return <ol className="d-timeline">{route.actions.map((a,index)=>{const phase=actionPhase(data,a);return <li key={index} className={phase}>
    <span className="d-time-dot">{phase==='completed'?'✓':a.kind==='drive'?'↗':'•'}</span><div><div className="d-time-title"><strong>{labels[a.kind]??a.kind}</strong><span>{names[phase]}</span></div><p>{a.source}{a.target!==a.source?` → ${a.target}`:''}</p>{a.ids.length>0&&<p className="d-manifest">{a.ids.join(' · ')}</p>}<time>{fmt(a.start)} – {fmt(a.end)} 分钟</time></div>
  </li>;})}</ol>;
}
export function VehicleInspector({data,car}:{data:Snapshot;car:Vehicle}){
  const route=data.plan?.routes.find(r=>r.vehicle===car.id);
  return <aside className="d-card d-inspector" aria-label="选中车辆详情"><div className="d-card-head"><div><span className="d-eyebrow">VEHICLE INSPECTOR</span><h2>{car.id}<small>{car.role==='trunk'?'干线车辆':'末端车辆'}</small></h2></div><span className="d-vehicle-icon" style={{color:vehicleColor(data,car.id)}}><Icon name="fleet" size={26}/></span></div>
    <div className="d-inspector-body"><dl><div><dt>配送员 / 基地</dt><dd>{car.courier_id} / {car.base}</dd></div><div><dt>最近到达节点</dt><dd>{car.position}</dd></div><div><dt>当前模拟时刻</dt><dd>{fmt(data.now)} 分钟</dd></div></dl>
      <div className="d-load-label"><span>真实载货</span><b>{car.load} / {car.capacity}</b></div><LoadBar car={car}/>
      <p className="d-current-action"><Icon name="clock" size={17}/>{car.current?`${labels[car.current.kind]} · ${car.current.source}${car.current.target!==car.current.source?' → '+car.current.target:''}`:'已停靠，暂无进行中动作'}</p>
      <details><summary>车上订单（{car.cargo.length}）</summary><p className="d-manifest">{car.cargo.join(' · ')||'当前为空车'}</p></details>
      {route&&<div className="d-route-metrics"><span>计划距离<b>{fmt(route.total_distance)} km</b></span><span>计划成本<b>{fmt(route.total_cost)} 元</b></span><span>计划返抵<b>{fmt(route.end_time)} 分钟</b></span></div>}
    </div><div className="d-inspector-timeline"><h3>本轮完整行程</h3>{data.needs_replan&&<p className="d-inline-warn">未来动作已暂停；进行中动作按原子规则完成。</p>}<RouteTimeline data={data} car={car}/></div>
  </aside>;
}
