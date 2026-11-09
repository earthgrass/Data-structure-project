import type {Snapshot} from '../types';
import {fmt} from '../presentation';
import {windowEvidenceCurrent} from '../windows.mjs';

export function TimeWindowPanel({data,showRelaxed,setShowRelaxed,onVehicle,selected}:{data:Snapshot;showRelaxed:boolean;setShowRelaxed:(v:boolean)=>void;onVehicle:(id:string)=>void;selected:string}){
  const info=data.time_windows,live=windowEvidenceCurrent(data);
  if(!info)return <div className="d-window-panel"><h3>当前场景尚未启用严格时间窗</h3><p>在“场景与管理”选择严格预约窗，新建同一 Seed 的校内配送场景。</p></div>;
  const probe=info.orders?.find(o=>o.id===info.probe_order_id);
  const original=info.relaxed_routes?.find(r=>r.vehicle===selected)?.service_order;
  const current=data.plan?.routes.find(r=>r.vehicle===selected)?.actions.filter(a=>a.kind==='deliver').flatMap(a=>a.ids);
  const serviceNames=(ids:string[])=>ids.map(id=>{const order=data.orders.find(o=>o.id===id);return `${data.nodes.find(n=>n.id===order?.destination)?.name??order?.destination??''} (${id})`;}).join(' → ');
  return <div className="d-window-panel"><h3>{info.mode==='strict'?'严格预约 · 签收完成截止':'宽松对照 · 原始时间窗'}</h3>
    <p>时间单位为模拟分钟。最早时间限制服务开始，截止时间限制签收完成；到达后还要等待、服务并传播后续时刻。</p>
    <div className="d-window-facts"><div><small>初始窗口宽度</small><b>{fmt(info.window_min_minutes)}–{fmt(info.window_max_minutes)} 分</b></div><div><small>原宽松路线超时</small><b>{info.baseline_late_orders.length} 单</b></div><div><small>路线结构改变</small><b>{info.changed_vehicles.length} 辆车</b></div></div>
    {info.mode==='strict'?<><p className="d-window-proof">只改变订单时间窗，保留地点、需求、优先级、车辆和道路。以下是初始 distance 规划的真实对照；“严格计划完成”不代表已签收。</p>
      {probe&&<p>{probe.id} 在原计划中于 {fmt(probe.baseline_end)} 分完成；最终预约窗为 {fmt(probe.earliest)}–{fmt(probe.deadline)} 分，严格计划于 {fmt(probe.strict_end)} 分签收。改变路线的车辆：{info.changed_vehicles.join('、')}。</p>}
      <div className="d-actions">{info.changed_vehicles.map(id=><button key={id} onClick={()=>onVehicle(id)}>查看 {id} 路线变化</button>)}</div>
      {original?.length&&current?.length&&live?<div className="d-window-sequence"><p><b>{selected} 原服务顺序：</b>{serviceNames(original)}</p><p><b>严格窗服务顺序：</b>{serviceNames(current)}</p></div>:null}
      <label className="d-window-toggle"><input type="checkbox" disabled={!live} checked={showRelaxed&&live} onChange={e=>setShowRelaxed(e.target.checked)}/>地图叠加选中车辆的原宽松路线（灰色虚线）</label>
      {!live&&<p className="d-inline-warn">场景已执行、订单/路况已改变，或当前目标不是 distance。下表仅保留初始对照，地图叠加已停用。</p>}
      <p className="d-muted">最小计划签收余量 {fmt(info.minimum_completion_slack_minutes!)} 分。等于截止时间可签收，超过即不可行。</p>
      <div className="d-table-scroll"><table className="d-window-table"><thead><tr><th>订单 / 地点</th><th>开始下限 → 完成截止</th><th>原宽松计划完成</th><th>严格计划完成</th></tr></thead><tbody>{info.orders?.map(o=><tr key={o.id}><td><b>{o.id}</b><small>{data.nodes.find(n=>n.id===o.destination)?.name??o.destination}</small></td><td>{fmt(o.earliest)} → {fmt(o.deadline)}</td><td className={o.baseline_end>o.deadline?'d-window-late':''}>{fmt(o.baseline_end)}{o.baseline_end>o.deadline?' · 超时':''}</td><td>{fmt(o.strict_end)}</td></tr>)}</tbody></table></div>
    </>:<p>本场景用于观察原宽松路线。要施加强约束，请在场景设置中选择严格预约窗后，新建相同 Seed 的场景。</p>}
  </div>;
}
