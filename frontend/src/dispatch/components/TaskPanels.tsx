import {useState} from 'react';
import type {Snapshot,Command,Comparison} from '../types';
import {Badge,Icon,type Confirmation} from './Common';
import {fmt,labels,trafficLabels} from '../presentation';

export function InventoryPanel({data}:{data:Snapshot}){
  return <><div className="d-section-note"><Icon name="inventory"/><p>到站卸货仅改变库存位置。只有客户签收动作完成，订单才记为已送达。数量按原始十进制字符串展示。</p></div><div className="d-inventory-grid">{data.nodes.filter(n=>n.type!=='customer').map(n=>{
    const orders=data.orders.filter(o=>o.location[1]===n.id&&o.location[0]===(n.type==='warehouse'?'warehouse':'hub'));
    const car=data.vehicles.find(v=>v.base===n.id);
    return <section className="d-card" key={n.id}><div className="d-card-head"><div><h2>{n.id} <small>{n.type==='warehouse'?'仓库':'中转站'}</small></h2><p>{car?`${car.id} · ${car.role==='trunk'?'干线补货':'末端配送'}`:'无绑定配送车辆'}</p></div><Badge>{orders.length} 张在库订单</Badge></div><div className="d-stock-list">{orders.map(o=><div key={o.id}><span><b>{o.id}</b><small>{o.destination} · {labels[o.status]}</small></span><span className="d-mono">{o.demand}</span></div>)}{!orders.length&&<p className="d-muted">暂无此位置的订单库存。</p>}</div></section>;
  })}</div></>;
}
export function TrafficPanel({data,road,setRoad,busy,command,confirm}:{data:Snapshot;road:string;setRoad:(v:string)=>void;busy:boolean;command:Command;confirm:(v:Confirmation)=>void}){
  const [status,setStatus]=useState('congested');
  const selected=data.edges.find(e=>e.source+'|'+e.target===road);
  const affected=data.plan?.routes.filter(r=>r.actions.some(a=>a.kind==='drive'&&a.source===selected?.source&&a.target===selected?.target)).map(r=>r.vehicle)??[];
  return <aside className="d-card d-traffic-panel"><div className="d-card-head"><div><h2>模拟交通控制</h2><p>只修改所选道路方向</p></div><Badge tone="info">v{data.traffic_version}</Badge></div><div className="d-pad"><label>有向道路<select value={road} onChange={e=>setRoad(e.target.value)}><option value="">选择或点击地图道路</option>{data.edges.map(e=><option key={e.source+e.target} value={e.source+'|'+e.target}>{e.source} → {e.target} · {trafficLabels[e.status]}</option>)}</select></label><label>道路状态<select value={status} onChange={e=>setStatus(e.target.value)}>{Object.entries(trafficLabels).map(([v,label])=><option value={v} key={v}>{label}</option>)}</select></label>
    {selected&&<dl><div><dt>当前通行时间</dt><dd>{fmt(selected.travel_time)} 分钟</dd></div><div><dt>距离 / 成本</dt><dd>{fmt(selected.distance)} km / {fmt(selected.cost)} 元</dd></div><div><dt>上次计划使用此路</dt><dd>{affected.join('、')||'无车辆'}</dd></div></dl>}
    <button className="d-primary" disabled={busy||!selected} title={!selected?'请先选择有向道路':''} onClick={()=>selected&&confirm({title:`更新 ${selected.source} → ${selected.target}？`,description:`将模拟状态设为${trafficLabels[status]}并请求暂停。已进入道路按旧版本完成，其余动作等待重规划。`,confirm:'应用路况',action:()=>void command('traffic',{source:selected.source,target:selected.target,status})})}>应用路况并请求暂停</button><p className="d-muted">{!selected?'先选择道路，才能应用路况。':'交通影响时间和成本，封路在所有目标下都排除。'} 已进入动作不会瞬移；当前路况不能追溯改写已发生历史。</p></div></aside>;
}
export function ObjectiveComparison({data,comparison,busy,command}:{data:Snapshot;comparison:Comparison|null;busy:boolean;command:Command}){
  return <section className="d-card"><div className="d-card-head"><div><h2>双目标比较</h2><p>同一业务输入，完整可行方案之间才比较指标</p></div><button className="d-primary" disabled={busy||data.running} title={data.running?'先暂停并完成进入中的动作，再比较':''} onClick={()=>void command('compare')}>运行 distance / cost 对比</button></div>
    {comparison?<><div className="d-comparison-source"><Badge tone="good">当前快照比较</Badge><span>{comparison.sessionId} · revision {comparison.revision} · 交通 v{comparison.trafficVersion}</span><code title={comparison.fingerprint}>{comparison.fingerprint.slice(0,16)}…</code></div><div className="d-table-scroll"><table><thead><tr><th>主目标</th><th>计划接纳 / 未接纳</th><th>距离</th><th>运输成本</th><th>独立验证 / 覆盖</th></tr></thead><tbody>{comparison.plans.map(p=><tr key={p.objective}><td><b>{p.objective==='distance'?'最短距离':'最低成本'}</b><small>{p.objective}</small></td><td>{p.accepted.length} / {p.deferred.length} 单</td><td>{fmt(p.total_distance)} km</td><td>{fmt(p.total_cost)} 元</td><td><Badge tone={p.report.valid?'good':'danger'}>{p.report.valid?'有效':'无效'}</Badge> {p.report.complete_all?'完整覆盖':'部分服务'}</td></tr>)}</tbody></table></div></>:<div className="d-comparison-empty"><Icon name="audit" size={32}/><h3>暂无当前版本的比较</h3><p>输入或版本变化后旧比较会失效；已应用计划继续保留。{data.running?'请先暂停并推进至检查点。':'点击上方按钮，在同一快照上比较两个目标。'}</p></div>}
  </section>;
}
export function EventHistory({data}:{data:Snapshot}){
  const [filter,setFilter]=useState('all'),[page,setPage]=useState(0);
  const events=data.events.filter(e=>filter==='all'||e.kind===filter).slice().reverse();
  return <section className="d-card"><div className="d-card-head"><div><h2>执行事件与独立审计</h2><p>{data.audit.complete_all?'客户全部签收已有历史证据':data.audit.valid?'当前执行历史有效；不表示配送已经完成':data.audit.violations.join(' · ')}</p></div><Badge tone={data.audit.valid?'good':'danger'}>{data.audit.valid?'历史有效':'审计异常'}</Badge></div>
    <div className="d-filters"><label>事件类别<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(0);}}><option value="all">全部事件</option>{['action','plan','create','traffic','cancel','priority'].map(k=><option key={k}>{k}</option>)}</select></label><span>{events.length} 条真实记录 · 最新优先</span><button disabled={page===0} onClick={()=>setPage(p=>p-1)}>上一页</button><button disabled={(page+1)*20>=events.length} onClick={()=>setPage(p=>p+1)}>下一页</button></div>
    <div className="d-event-list">{events.slice(page*20,page*20+20).map((e,i)=><div key={i}><time>{fmt(e.time)}</time><Badge>{e.action?labels[e.action.kind]:e.kind}</Badge><span>{e.action?`${e.action.vehicle} · ${e.action.source} → ${e.action.target}`:e.id??'系统事件'}</span><small>{e.action?.ids.join(' · ')}</small></div>)}{!events.length&&<p className="d-pad d-muted">暂无该类事件。</p>}</div>
  </section>;
}
