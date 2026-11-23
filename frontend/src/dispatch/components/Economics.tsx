import {useState} from 'react';
import type {Snapshot,StudioParameters} from '../types';
import {fmt} from '../presentation';
import {Icon} from './Common';

export function EconomicsPanel({data,busy,error,onTrial,onCreate}:{data:Snapshot;busy:boolean;error:string;onTrial:(p:StudioParameters)=>Promise<boolean>;onCreate:()=>void}){
 const [draft,setDraft]=useState<StudioParameters|null>(data.studio?.parameters??null);
 if(!data.studio||!draft)return <div className="s-parameters"><span className="s-eyebrow">SCENARIO LAB</span><h2>把成本变成可解释的决策</h2><p>新版场景默认启用3个中转站，并提供逐车载重与燃油成本试算。原会话继续保留。</p><button onClick={onCreate}>创建参数化场景</button></div>;
 const model=data.studio,planned=model.planned,baseline=model.trial?.before;
 const locked=data.running||data.now!==0||data.traffic_version!==0||data.orders.some(o=>o.location[0]!=='warehouse');
 const fields:[keyof Pick<StudioParameters,'fuel_per_100km'|'fuel_price'|'driver_hourly'|'maintenance_per_km'>,string,string][]=[['fuel_per_100km','单位油耗','L / 100km'],['fuel_price','燃油单价','元 / L'],['driver_hourly','司机时薪','元 / h'],['maintenance_per_km','维护成本','元 / km']];
 return <div className="s-parameters"><div className="s-parameters-title"><span className="s-eyebrow">SCENARIO LAB</span><h2>运营参数</h2><p>先调整，再由后端按最低成本实际试算。</p></div>
  {planned&&<section className="s-results">{model.auto_replan&&<p className="s-difference">{model.auto_replan}</p>}{model.planned_late_orders?.length? <p className="d-inline-warn">当前计划预计超时：{model.planned_late_orders.map(o=>`${o.id}（${fmt(o.delay_minutes)} 分）`).join('、')} · 预计独立罚金 ¥{fmt(model.planned_late_penalty_total??0)}。{!data.single_vehicle&&'允许迟到的手动特急会单独标记。'}</p>:null}{model.late_orders.length>0&&<p className="d-inline-warn">实际超时记录：{model.late_orders.map(o=>`${o.id}（${o.status==='delivered'?'已签收':'未签收'}）`).join('、')} · 模拟罚金 ¥{fmt(model.late_penalty_total??model.late_orders.reduce((a,o)=>a+o.penalty,0))}。罚金与道路运输成本分列。</p>}<span className="s-eyebrow">ACTUAL PLAN</span><h3>当前后端计划</h3><div className="s-result-grid"><div><small>路线总距离</small><b>{fmt(planned.distance)}<em>km</em></b></div><div><small>预计燃油</small><b>{fmt(planned.fuel_liters)}<em>L</em></b></div></div>
   <div className="s-cost-total"><span>总运输成本</span><strong>¥ {fmt(planned.total_cost)}</strong></div>
   <dl><div><dt>燃油费</dt><dd>¥ {fmt(planned.fuel_cost)}</dd></div><div><dt>行驶工时费</dt><dd>¥ {fmt(planned.labor_cost)}</dd></div><div><dt>维护费</dt><dd>¥ {fmt(planned.maintenance_cost)}</dd></div></dl>
   <p>接纳 {data.plan?.accepted.length} 单 / 未接纳 {data.plan?.deferred.length} 单 · {data.plan?.report.complete_all?'完整覆盖':'部分服务'}</p>
   {data.now>0&&<p className="s-difference">已实际行驶 {fmt(model.executed.distance)} km · 已发生运输费 ¥{fmt(model.executed.total_cost)}。当前计划可能包含已执行部分，请分别查看。</p>}
   {baseline&&<p className="s-difference">原参数计划：{fmt(baseline.distance)} km · ¥{fmt(baseline.cost)} · 接纳{baseline.accepted}单。参数已改变，费用差额不代表算法优化率。</p>}
  </section>}
  <form onSubmit={e=>{e.preventDefault();void onTrial(draft);}}>
   <div className="s-presets">{!data.single_vehicle&&<button type="button" onClick={()=>setDraft({...draft,capacities:Object.fromEntries(data.vehicles.map(v=>[v.id,v.role==='trunk'?draft.capacities[v.id]:model.presets.delivery_capacity_kg]))})}>末端{model.presets.delivery_capacity_kg}kg试算</button>}<button type="button" title="人为极端参数敏感性实验，并非真实油价" onClick={()=>setDraft({...draft,fuel_price:model.presets.fuel_price_stress})}>高油价压力测试</button></div><fieldset><legend>01 / 成本模型</legend><div className="s-field-grid">{fields.map(([key,label,unit])=><label key={key}>{label}<span className="s-unit-input"><input type="number" step="any" min="0" required aria-label={label} value={draft[key]} onChange={e=>setDraft({...draft,[key]:e.target.value})}/><small>{unit}</small></span></label>)}</div></fieldset>
   {!data.single_vehicle&&<fieldset><legend>02 / 启用中转站 <span>至少3个</span></legend><div className="s-hub-options">{model.available_hubs.map(h=><label key={h.id}><input type="checkbox" checked={draft.hub_ids.includes(h.id)} onChange={e=>setDraft({...draft,hub_ids:e.target.checked?[...draft.hub_ids,h.id]:draft.hub_ids.filter(k=>k!==h.id)})}/><span>{h.name.replace('（游泳馆北侧）','')}<small>{h.id}</small></span></label>)}</div></fieldset>}
   <fieldset><legend>03 / 逐车载重上限 <span>kg</span></legend><p className="s-helper">需求、装货与容量比较全程 Decimal。当前载货不会被参数试算改写。</p><div className="s-capacities">{data.vehicles.map(v=><label key={v.id}><span><Icon name="fleet" size={16}/>{v.id}</span><input aria-label={`${v.id} 载重上限`} type="number" min="0.1" step="any" required value={draft.capacities[v.id]??v.capacity} onChange={e=>setDraft({...draft,capacities:{...draft.capacities,[v.id]:e.target.value}})}/></label>)}</div></fieldset>
   <div className="s-experiment-note"><Icon name="audit"/><p>只在尚未执行时创建独立试算会话，保留同一批订单、地点和时间窗。原会话不变。小容量可能产生部分服务。</p></div>
   {error&&<p role="alert" className="d-inline-error">{error}</p>}
   {locked&&<p className="d-inline-warn">场景已执行或路况已更新。请新建场景后调整参数，不能重置在途货物。</p>}
   <button className="s-trial-button" disabled={busy||locked||(!data.single_vehicle&&draft.hub_ids.length<3)}><Icon name="arrow"/>{busy?'正在处理…':'按最低成本试算'}</button>
   {locked&&<button type="button" onClick={onCreate} disabled={busy}>新建场景</button>}
  </form>
  <details className="s-model"><summary>计算公式与真实性边界</summary><p>{model.model_note}</p><p>不同道路等级使用配置中的模拟油耗系数；司机时薪使时间与距离产生真实权衡。载重影响可行订单与分配，不假设油耗随载荷精确变化。</p><a href={model.official_map_url} target="_blank" rel="noreferrer">北工大官方校园地图 ↗</a></details>
 </div>;
}
