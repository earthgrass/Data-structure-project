import {useState} from 'react';
import type {Snapshot} from '../types';
import {fmt,labels,priorities,trafficLabels,vehicleColor} from '../presentation';
import {dispatchQueue,orderRoute,roadSummary} from '../workspace-views.mjs';
import {RejectionDetails} from './PlanningInsights';

export function RoadDashboard({data,onRoad}:{data:Snapshot;onRoad:(key:string)=>void}){
 const summary=roadSummary(data),active=summary.counts.light+summary.counts.moderate+summary.counts.congested;
 const used=data.edges.filter(e=>e.status!=='clear'||summary.used.has(e.source+'\0'+e.target));
 const ordered=[...used];
 const severity:Record<string,number>={blocked:0,congested:1,moderate:2,light:3,clear:4};
 for(let i=1;i<ordered.length;i++){const road=ordered[i];let j=i-1;while(j>=0&&(severity[road.status]<severity[ordered[j].status]||severity[road.status]===severity[ordered[j].status]&&road.source+'\0'+road.target<ordered[j].source+'\0'+ordered[j].target)){ordered[j+1]=ordered[j];j--;}ordered[j+1]=road;}
 return <section className="w-dashboard" aria-label="道路拥堵仪表盘"><div className="w-heading"><div><span>ROAD CONDITIONS · 交通 v{data.traffic_version}</span><h2>道路拥堵概览</h2><p>每条有向边独立计数；成本目标考虑行驶工时、油耗和拥堵延误。校内慢速通行路参与规划，步行专用路不允许车辆通行。</p></div><strong>{summary.total} <small>条有向道路</small></strong></div>
  <div className="w-kpis"><article><small>拥堵道路</small><b>{active}</b><span>轻微／一般／严重</span></article><article><small>封闭方向</small><b>{summary.counts.blocked}</b><span>规划时不可通行</span></article><article><small>当前计划涉及异常路段</small><b>{summary.affected}</b><span>按方向统计，可能是待重规划旧计划</span></article><article><small>畅通方向</small><b>{summary.counts.clear}</b><span>距离权重保持不变</span></article></div>
  <div className="w-road-meter" role="img" aria-label={`畅通 ${summary.counts.clear}，轻微拥堵 ${summary.counts.light}，一般拥堵 ${summary.counts.moderate}，严重拥堵 ${summary.counts.congested}，封路 ${summary.counts.blocked}`}>
   {Object.entries(summary.counts).map(([status,count])=><span key={status} className={'w-'+status} style={{width:`${summary.total?count/summary.total*100:0}%`}}/>)}
  </div><div className="w-road-legend">{Object.entries(summary.counts).map(([status,count])=><span key={status}><i className={'w-'+status}/>{trafficLabels[status]} {count}</span>)}</div>
  <div className="w-road-list"><h3>异常路段与当前计划使用路段</h3>{ordered.length>80&&<p className="w-footnote">按异常程度优先显示前 80 / {ordered.length} 条，完整道路可在下方地图和道路选择器查看。</p>}{ordered.length===0?<p>暂无计划使用或异常道路。</p>:<div>{ordered.slice(0,80).map(e=>{const cars=summary.used.get(e.source+'\0'+e.target)??[];return <button key={e.source+'\0'+e.target} onClick={()=>onRoad(e.source+'|'+e.target)}><span className={'w-road-dot w-'+e.status}/><span><b>{e.name||e.source+' → '+e.target}</b><small>{e.source} → {e.target} · {e.highway??'道路'} · {e.travel_time>0?fmt(e.distance/e.travel_time*60)+' km/h':'不可通行'}</small></span><em>{trafficLabels[e.status]}</em><span>{fmt(e.travel_time)} 分 · {fmt(e.cost)} 元</span><small>{cars.length?cars.join('、'):'未用于当前计划'}</small></button>;})}</div>}</div>
 </section>;
}

export function FleetStage({data,clock,selected,onSelect}:{data:Snapshot;clock:number;selected:string;onSelect:(id:string)=>void}){
 return <section className="w-dashboard" aria-label="立体车队动画"><div className="w-heading"><div><span>FLEET STAGE · 真实快照驱动</span><h2>车辆载货与配送动作</h2><p>立体车辆为示意动画；位置、载荷和动作均取自同一后端会话，动画不改变模拟时钟。</p></div><strong>{data.vehicles.length} <small>辆车</small></strong></div>
  <div className="w-fleet-stage">{data.vehicles.map(car=>{
   const a=car.current,progress=a&&a.kind==='drive'&&a.end>a.start?Math.max(0,Math.min(1,(clock-a.start)/(a.end-a.start))):0;
   const loaded=Number(car.load),capacity=Number(car.capacity),ratio=capacity>0?Math.min(100,Math.max(0,loaded/capacity*100)):0;
   return <button key={car.id} className={'w-car-card'+(car.id===selected?' selected':'')} onClick={()=>onSelect(car.id)} aria-pressed={car.id===selected} style={{'--w-car':vehicleColor(data,car.id)} as React.CSSProperties}>
    <span className="w-car-header"><b>{car.id}</b><span>{car.role==='trunk'?'干线车':'末端车'} · {a?labels[a.kind]:'停靠'}</span></span>
    <span className="w-lane"><span className="w-lane-line"/><span className="w-truck" style={{left:`${7+progress*65}%`}}><svg viewBox="0 0 100 70" aria-hidden="true"><polygon points="8,17 53,17 68,8 23,8" fill="#e8f0ff" stroke="#193950" strokeWidth="2"/><polygon points="8,17 53,17 53,49 8,49" fill="var(--w-car)" stroke="#193950" strokeWidth="2"/><polygon points="53,17 68,8 68,41 53,49" fill="#294b6b" stroke="#193950" strokeWidth="2"/><polygon points="68,25 83,25 93,37 93,49 68,49" fill="var(--w-car)" stroke="#193950" strokeWidth="2"/><polygon points="71,28 82,28 88,36 71,36" fill="#dff5ff"/><circle cx="28" cy="51" r="7" fill="#1c344a" stroke="#8da6b8" strokeWidth="2"/><circle cx="78" cy="51" r="7" fill="#1c344a" stroke="#8da6b8" strokeWidth="2"/></svg></span></span>
    <span className="w-car-place">{a&&a.kind==='drive'?`${a.source} → ${a.target}`:car.position} · {car.cargo.length} 单在车</span>
    <span className="w-load"><span>实际载重</span><b>{car.load} / {car.capacity} kg</b></span><span className="w-load-meter"><i style={{width:`${ratio}%`}}/></span>
   </button>;
  })}</div><p className="w-footnote">行驶中的车仅沿示意轨道显示动作进度；真实地理位置和路径请以地图演示为准。减少动态效果的系统设置会停用车身动画。</p>
 </section>;
}

function OrderRouteMap({data,id}:{data:Snapshot;id:string}){
 const legs=orderRoute(data,id),nodes=new Map(data.nodes.map(n=>[n.id,n]));
 const points=legs.flatMap(leg=>leg.points.map(key=>nodes.get(key)).filter((n):n is Snapshot['nodes'][number]=>!!n));
 if(!points.length)return <p className="w-footnote">当前没有可显示的已应用路线；未接纳订单不能虚构配送路径。</p>;
 const xs=points.map(p=>p.x),ys=points.map(p=>p.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
 const x=(v:number)=>20+(v-minX)/(maxX-minX||1)*560,y=(v:number)=>15+(v-minY)/(maxY-minY||1)*170;
 return <div className="w-order-route"><svg viewBox="0 0 600 200" role="img" aria-label={`${id} 的已应用道路路径示意，含干线与末端方向`}>
  {legs.map((leg,index)=>{const color=index===0?'#dc7a24':'#168c9d';const p=leg.points.map(key=>nodes.get(key)).filter((n):n is Snapshot['nodes'][number]=>!!n);return <g key={leg.vehicle+leg.kind}><polyline points={p.map(n=>`${x(n.x)},${y(n.y)}`).join(' ')} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>{p.length>0&&<><circle cx={x(p[0].x)} cy={y(p[0].y)} r="6" fill={color}/><circle cx={x(p[p.length-1].x)} cy={y(p[p.length-1].y)} r="7" fill="white" stroke={color} strokeWidth="3"/></>}</g>;})}
 </svg><p>{legs.map(l=>`${l.vehicle} ${l.kind==='unload'?'仓库→中转站':'中转站→客户'}：${l.points.length-1} 段有向道路`).join(' · ')}</p></div>;
}

export function OrderDispatchBoard({data}:{data:Snapshot}){
 const [selected,setSelected]=useState('');const rows=dispatchQueue(data),chosen=rows.find(r=>r.order.id===selected)??rows[0];
 const stale=data.planning_insights?.timeline?.stale??true;
 return <section className="w-dashboard" aria-label="订单配送优先队列"><div className="w-heading"><div><span>ORDER PRIORITY · 逐单身份</span><h2>配送优先级与按时签收</h2><p>按特急、紧急、普通及签收截止排序；这是规划优先级，不代表不同车辆的全局签收先后。</p></div><strong>{rows.length} <small>张订单</small></strong></div>
  {stale&&<p className="d-inline-warn">输入或路况已变化，旧预计签收与路线可能过时；请等待新计划。实际签收历史仍保留。</p>}
  <div className="w-order-grid"><div className="w-order-queue">{rows.map((row,index)=><button key={row.order.id} className={chosen?.order.id===row.order.id?'selected':''} onClick={()=>setSelected(row.order.id)} aria-pressed={chosen?.order.id===row.order.id}><span className="w-queue-index">{index+1}</span><span><b>{row.order.id}</b><small>{data.nodes.find(n=>n.id===row.order.destination)?.name??row.order.destination}</small></span><span className={'w-priority '+row.order.priority}>{priorities.find(([key])=>key===row.order.priority)?.[1]}</span><span className="w-queue-time">≤ {fmt(row.order.deadline)} 分</span><em>{row.delivery==='signed'?'已签收':row.delivery==='scheduled'?'预计按时':row.delivery==='deferred'?'本轮未接纳':row.delivery==='terminal'?labels[row.order.status]:'待验证'}</em></button>)}</div>
   {chosen&&<article className="w-order-detail"><div className="w-order-detail-head"><div><span>ORDER DETAIL</span><h3>{chosen.order.id} · {data.nodes.find(n=>n.id===chosen.order.destination)?.name??chosen.order.destination}</h3></div><span className={'w-priority '+chosen.order.priority}>{priorities.find(([key])=>key===chosen.order.priority)?.[1]}</span></div>
    <dl><div><dt>签收时间窗</dt><dd>{fmt(chosen.order.earliest)} – {fmt(chosen.order.deadline)} 分</dd></div><div><dt>订单重量</dt><dd>{chosen.order.demand} kg</dd></div><div><dt>中转站</dt><dd>{chosen.order.hub||'未分配'}</dd></div><div><dt>负责末端车辆</dt><dd>{chosen.actual?.vehicle??chosen.expected?.vehicle??'尚未分配'}</dd></div><div><dt>预计签收</dt><dd>{chosen.expected?`${fmt(chosen.expected.signoff)} 分 · 余量 ${fmt(chosen.expected.slack)} 分`:'暂无有效预测'}</dd></div><div><dt>实际签收</dt><dd>{chosen.actual?`${fmt(chosen.actual.signoff)} 分`:'尚未签收'}</dd></div></dl>
    <p className={'w-delivery-state '+chosen.delivery}>{chosen.delivery==='signed'?'已实际签收；可核对执行历史。':chosen.delivery==='scheduled'?'当前已应用计划预计在截止前完成签收。':chosen.delivery==='deferred'?`当前计划未接纳：${chosen.reason??'请查看候选原因'}。不代表已证明全局无解。`:chosen.delivery==='terminal'?'订单已结束，不参与后续配送。':'尚无经验证的按时签收预测。'}</p>
    <h4>该订单的已应用路径</h4>{stale?<p className="w-footnote">当前路线证据已过时，等待重新规划。</p>:<OrderRouteMap data={data} id={chosen.order.id}/>}
    <RejectionDetails data={data} orderId={chosen.order.id}/>
   </article>}</div>
 </section>;
}
