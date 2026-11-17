import {useState} from 'react';
import type {Snapshot} from '../types';
import type {InsightMetrics,TimelineOrder} from '../insight-types';
import {fmt,labels,priorities} from '../presentation';
import {explanationFor,filterTimeline,rejectionContext,signedDifference,timePosition,timelineDomain} from '../planning-insights.mjs';

const metricLabels:[keyof InsightMetrics,string,string][]=[['distance','剩余距离','km'],['cost','剩余模拟成本','元'],['travel_time','剩余行驶时间','分']];
const stages:Record<string,string>={load:'装货',deliver:'客户签收',unload:'中转卸货',return:'返仓',travel:'道路行驶',priority:'优先级约束',assignment:'站点分配',inventory:'库存衔接'};
const reasonLabels:Record<string,string>={capacity:'车辆容量不足',completion_deadline:'超过完成截止',unreachable:'选定路径不可达',return_unreachable:'返程不可达',critical_precedence:'特急服务顺序冲突',inventory_not_released:'货物尚未释放',unsupported_warehouse:'仓库不受支持',missing_protected_hub:'已承诺订单缺少站点',heuristic_incomplete:'启发式未找到可行安排'};

export function RejectionDetails({data,orderId}:{data:Snapshot;orderId:string}){
 const explanation=explanationFor(data,orderId),context=rejectionContext(data);
 if(!explanation)return null;
 return <details className="i-rejection"><summary>为什么未接纳 {orderId}？</summary>
  {context?.stale&&<p className="i-notice">以下是上一次尝试的证据。订单、路况或模拟时间与执行进度已变化，当前结果需重新规划确认。</p>}
  {context?.source==='blocked_proposal'&&<p className="i-notice">本次续程未通过安全应用检查；原计划与载货已保留。</p>}
  {context.source==='rejected_response'&&<p className="i-notice">失败提案，未应用。此为本次手动规划响应中的证据，原计划、位置与载货未被替换。</p>}
  <p>{explanation.summary}</p>
  {explanation.attempts.map((attempt,index)=><article key={index} className="i-attempt">
   <strong>{attempt.hub??'未选定站点'} · {attempt.vehicle??'未选定车辆'}</strong>
   <span>{stages[attempt.stage]??attempt.stage}：{reasonLabels[attempt.code]??attempt.code}</span>
   {attempt.order_ids.length>0&&<span>阻塞任务：{attempt.order_ids.join('、')}</span>}
   {attempt.load!==null&&attempt.capacity!==null&&<span className="i-exact">该次候选载荷 {attempt.load} kg ＞ 容量 {attempt.capacity} kg</span>}
   {attempt.service_end!==null&&attempt.deadline!==null&&<span>候选完成 {String(attempt.service_end)} 分；截止 {String(attempt.deadline)} 分</span>}
   {attempt.source!==null&&attempt.target!==null&&<span>路径：{attempt.source} → {attempt.target}</span>}
  </article>)}
  {explanation.suggestions.length>0&&<><strong>可检查的调整</strong><ul>{explanation.suggestions.map(s=><li key={s}>{s}</li>)}</ul></>}
  <p className="i-caption">这是实际尝试的代表性失败候选，不是全路网无解证明。调整后仍需重新规划和验证；运营参数试算仅适用于未执行的新场景。</p>
 </details>;
}

export function RejectionOverview({data}:{data:Snapshot}){
 const context=rejectionContext(data),rejected=context.source==='rejected_response'?data.rejected_proposal?.report:null;
 if(!context.items.length&&!rejected)return null;
 return <section className="i-impact" aria-label="未接纳原因说明"><h3>{context.stale?'上次尝试的未接纳说明':'未接纳原因说明'}</h3>
  {rejected?<p className="i-notice">失败提案，未应用。该响应绑定会话 {data.id}、输入 v{context.revision}；原有效计划和真实执行状态保持不变。</p>:<p>以下 {context.items.length} 张订单在{context.stale?'上次':'本次'}尝试中未被接纳，可展开查看实际候选证据。</p>}
  {rejected?.report.violations?.length?<p className="i-caption">验证结果：{rejected.report.violations.join('、')}</p>:null}
  {context.items.map(item=><RejectionDetails key={item.order_id} data={data} orderId={item.order_id}/>)}
 </section>;
}

export function ReplanImpactPanel({data}:{data:Snapshot}){
 const impact=data.planning_insights?.impact;
 if(!impact)return <section className="i-impact" aria-label="重规划影响摘要"><h3>重规划影响摘要</h3><p>首份计划没有前后基线；应用下一份计划后显示真实变化。</p></section>;
 const earlier=impact.orders.filter(o=>o.change==='earlier'),later=impact.orders.filter(o=>o.change==='later');
 const beforeCount=impact.orders.filter(o=>o.before!==null).length,afterCount=impact.orders.filter(o=>o.after!==null).length;
 const stale=data.planning_insights?.timeline.stale;
 return <section className="i-impact" aria-label="重规划影响摘要"><h3>{stale?'上次已应用计划的影响':'重规划影响摘要'}</h3>
  <p className="i-caption">检查点 {fmt(impact.at)} 分 · 计划 v{impact.baseline_revision} → v{impact.plan_revision} · 仅比较尚未执行的行程</p>
  {stale&&<p className="i-notice">当前变更尚未形成可用新计划，下面保留上次对照。</p>}
  <div className="i-impact-metrics">{metricLabels.map(([key,label,unit])=><div key={key}><small>{label}</small><b>{signedDifference(impact.delta[key])}<em>{impact.delta[key]!==0?' '+unit:''}</em></b><span>{fmt(impact.before[key])} → {fmt(impact.after[key])} {unit}</span></div>)}</div>
  <p>剩余计划服务 {beforeCount} → {afterCount} 单；共同订单中 <b>{earlier.length} 单提前</b>、<b>{later.length} 单延后</b>。</p>
  {(beforeCount!==afterCount||impact.newly_accepted.length>0||impact.no_longer_planned.length>0||impact.deferred.length>0)&&<p className="i-notice">服务订单集合存在变化或未接纳任务，距离与成本差额不能单独证明方案更优。</p>}
  <div className="i-partitions">{[['新接纳',impact.newly_accepted],['不再规划',impact.no_longer_planned],['取消 / 过期',impact.cancelled],['仍未接纳',impact.deferred]].map(([label,ids])=><p key={label as string}><b>{label}：</b>{(ids as string[]).join('、')||'无'}</p>)}</div>
  <details className="i-detail"><summary>逐车影响与订单提前 / 延后</summary>
   {impact.vehicles.map(car=><article className="i-vehicle" key={car.vehicle}><strong>{car.vehicle}{car.changed?' · 行程已调整':' · 行程未改变'}</strong>{metricLabels.map(([key,label,unit])=><div key={key}><span>{label}</span><b>{signedDifference(car.delta[key])} {car.delta[key]!==0?unit:''}</b><small>{fmt(car.before[key])} → {fmt(car.after[key])} {unit}</small></div>)}</article>)}
   {earlier.length+later.length===0?<p>共同订单的预计签收时刻未改变。</p>:<ul className="i-time-deltas">{[...earlier,...later].map(o=><li key={o.order_id}><b>{o.order_id}</b> · {o.change==='earlier'?'提前':'延后'} {fmt(Math.abs(o.delta!))} 分 <span>{fmt(o.before!)} → {fmt(o.after!)} 分</span></li>)}</ul>}
  </details>
  <p className="i-caption">旧路线是历史对照，未重新证明其在新路况下仍可行。费用使用真实路线的模拟道路成本，签收变化是预计值。</p>
 </section>;
}

function OrderTimeGraphic({row,domain,now}:{row:TimelineOrder;domain:{start:number;end:number};now:number}){
 const x=(v:number|null|undefined)=>timePosition(v,domain);
 const earliest=x(row.earliest)!,deadline=x(row.deadline)!,arrival=x(row.expected?.arrival),start=x(row.expected?.service_start),signoff=x(row.expected?.signoff),actual=x(row.actual?.signoff),current=x(now)!;
 return <svg viewBox="-3 0 106 28" preserveAspectRatio="none" role="img" aria-label={`${row.order_id}，窗口 ${fmt(row.earliest)} 至 ${fmt(row.deadline)} 分，${row.expected?`预计签收 ${fmt(row.expected.signoff)} 分`:'无当前签收预测'}，${row.actual?`实际签收 ${fmt(row.actual.signoff)} 分`:'尚无实际签收记录'}`}>
  <line x1="0" x2="100" y1="15" y2="15" className="i-axis"/>
  <rect x={earliest} y="9" width={Math.max(0,deadline-earliest)} height="12" rx="1" className="i-window-band"/>
  <line x1={earliest} x2={earliest} y1="7" y2="23" className="i-window-bound"/><line x1={deadline} x2={deadline} y1="7" y2="23" className="i-window-bound"/>
  <line x1={current} x2={current} y1="2" y2="26" className="i-now"/>
  {start!==null&&signoff!==null&&<line x1={start} x2={signoff} y1="15" y2="15" className="i-service-span"/>}
  {arrival!==null&&<circle cx={arrival} cy="15" r="1.5" className="i-arrival"/>}
  {start!==null&&<rect x={start-1} y="12" width="2" height="6" className="i-service-start"/>}
  {signoff!==null&&<path d={`M ${signoff} 5 L ${signoff-1.8} 10 L ${signoff+1.8} 10 Z`} className="i-signoff"/>}
  {actual!==null&&<circle cx={actual} cy="22" r="2" className="i-actual"/>}
 </svg>;
}

export function OrderTimeTimeline({data}:{data:Snapshot}){
 const [query,setQuery]=useState(''),[activeOnly,setActiveOnly]=useState(true),[riskOnly,setRiskOnly]=useState(false),[threshold,setThreshold]=useState(5);
 const timeline=data.planning_insights?.timeline;
 if(!timeline)return <section className="i-timeline"><h3>订单时间窗时间轴</h3><p>当前快照没有逐单时间证据。请连接新版后端或创建新场景。</p></section>;
 const rows=filterTimeline(timeline.orders,{query,activeOnly,riskOnly,threshold,forecastCurrent:!timeline.stale,nodes:data.nodes}),domain=timelineDomain(rows,timeline.now);
 const riskCount=filterTimeline(timeline.orders,{riskOnly:true,threshold,forecastCurrent:!timeline.stale}).length;
 return <section className="i-timeline" aria-label="订单时间窗时间轴"><div className="i-timeline-heading"><div><span className="i-eyebrow">ORDER TIME WINDOWS</span><h3>订单时间窗时间轴</h3></div><span className="i-clock">当前 {fmt(timeline.now)} 分</span></div>
  <p>窗口左端限制服务开始，右端限制签收完成。每张订单独立展示；全部时间均为模拟分钟。</p>
  {timeline.stale&&<p className="i-notice" role="status">{timeline.plan_revision===null?'尚无有效预测':'当前计划已过时'}：{timeline.stale_reason??'等待重规划'}。{timeline.plan_revision===null?'应用有效计划后显示预计时刻。':'已隐藏旧预测；实际签收记录仍然有效。'}</p>}
  <div className="i-timeline-controls"><label>搜索订单 / 地点 / 车辆<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="例如 O12、P27、EAST"/></label><label>余量提醒阈值（分钟）<input type="number" min="0" step="any" value={threshold} onChange={e=>{const value=Number(e.target.value);if(Number.isFinite(value)&&value>=0)setThreshold(value);}}/></label></div>
  <div className="i-timeline-filters"><label><input type="checkbox" checked={activeOnly} onChange={e=>setActiveOnly(e.target.checked)}/>只看待完成</label><label><input type="checkbox" checked={riskOnly} onChange={e=>setRiskOnly(e.target.checked)}/>只看余量 ≤ {threshold} 分（{riskCount} 单）</label></div>
  <p className="i-caption">提醒阈值只筛选展示，不放宽容量或签收截止。未规划订单没有可计算的计划余量。</p>
  <div className="i-timeline-legend"><span>浅色区间：服务窗口</span><span>○ 预计到达</span><span>▪ 服务开始</span><span>△ 预计签收</span><span>● 实际签收</span><span>竖虚线：当前时刻</span></div>
  <div className="i-timeline-scale"><span>{fmt(domain.start)} 分</span><span>{fmt(domain.end)} 分</span></div>
  <p className="i-caption">{rows.length} 张订单，共用同一时间刻度。</p>
  <div className="i-timeline-orders">{rows.map(row=>{
   const expected=timeline.stale?null:row.expected,actual=row.actual;
   return <article className={'i-timeline-order'+(expected&&expected.slack<=threshold?' is-tight':'')} key={row.order_id}>
    <header><div><b>{row.order_id}</b><span>{priorities.find(([key])=>key===row.priority)?.[1]??row.priority} · {labels[row.status]??row.status}</span></div><strong>{actual?'已签收':expected?`预计余量 ${fmt(expected.slack)} 分`:row.deferred_reason?'未接纳':'暂无预测'}</strong></header>
    <p className="i-order-place">{data.nodes.find(n=>n.id===row.destination)?.name??row.destination} · {actual?.vehicle??expected?.vehicle??'尚无配送车辆'}</p>
    <OrderTimeGraphic row={{...row,expected}} domain={domain} now={timeline.now}/>
    <div className="i-window-values"><span>服务开始 ≥ {fmt(row.earliest)}</span><span>签收完成 ≤ {fmt(row.deadline)}</span></div>
    <dl className="i-time-values"><div><dt>预计到达</dt><dd>{expected?.arrival===null||expected?.arrival===undefined?'—':fmt(expected.arrival)}</dd></div><div><dt>预计服务</dt><dd>{expected?fmt(expected.service_start):'—'}</dd></div><div><dt>预计签收</dt><dd>{expected?fmt(expected.signoff):'—'}</dd></div><div><dt>实际签收</dt><dd>{actual?fmt(actual.signoff):'未签收'}</dd></div></dl>
    {actual&&<p className="i-actual-note">实际服务 {fmt(actual.service_start)} → {fmt(actual.signoff)} 分，签收余量 {fmt(actual.slack)} 分。</p>}
    <RejectionDetails data={data} orderId={row.order_id}/>
   </article>;
  })}</div>
  {rows.length===0&&<p className="i-empty">没有符合筛选条件的订单；可取消“只看待完成”查看签收历史。</p>}
 </section>;
}
