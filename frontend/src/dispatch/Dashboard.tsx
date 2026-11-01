import {useEffect,useRef,useState, type FormEvent} from 'react';
import type {Snapshot,Plan} from './types';
import {acceptSnapshot} from './sync.mjs';
import './dashboard.css';

const colors=['#ff8a24','#26d9e8','#a48cff','#69d7a3'];
const priorities=[['critical','特急 · 同批先送'],['urgent','紧急 · 可行优先'],['normal','普通']];
const labels:Record<string,string>={load:'装货',unload:'到站卸货',deliver:'客户签收',drive:'道路行驶',wait:'等待',finish:'返抵基地',pending:'待规划',planned:'已规划',in_transit:'运输中',delivered:'已签收',cancelled:'已取消',expired:'已过期'};
const fmt=(n:number)=>n.toFixed(2);

async function request(path:string,body?:unknown):Promise<Snapshot> {
  const response=await fetch('/api/v2'+path,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok) throw new Error(value.error?.message??`HTTP ${response.status}`);
  return value;
}

export function DispatchDashboard() {
  const [data,setData]=useState<Snapshot|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [seed,setSeed]=useState(''),[objective,setObjective]=useState('distance'),[selected,setSelected]=useState('');
  const [playing,setPlaying]=useState(false),[comparison,setComparison]=useState<Plan[]>([]);
  const [road,setRoad]=useState(''),[traffic,setTraffic]=useState('congested');
  const active=useRef(''),latest=useRef<Snapshot|null>(null),locked=useRef(false);
  function receive(incoming:Snapshot) {
    const accepted=acceptSnapshot(latest.current,incoming,active.current);
    if(accepted){latest.current=accepted;setData(accepted);}
  }
  async function create() {
    if(locked.current)return;locked.current=true;setBusy(true);setPlaying(false);setError('');
    try {const value=await request('/sessions',seed===''?{}:{seed:Number(seed)});active.current=value.id;sessionStorage.setItem('logiroute-session',value.id);latest.current=null;receive(value);setComparison([]);setSelected(value.vehicles[0]?.id??'');setRoad('');}
    catch(e){setError(String(e));}finally{locked.current=false;setBusy(false);}
  }
  async function command(command:string,fields:Record<string,unknown>={}) {
    if(locked.current||!latest.current)return;locked.current=true;setBusy(true);setError('');
    const id=active.current;
    try {const value=await request(`/sessions/${id}/commands`,{revision:latest.current.revision,command,...fields});receive(value);if(value.comparison)setComparison(value.comparison);}
    catch(e){setError(String(e));setPlaying(false);try{receive(await request(`/sessions/${id}`));}catch{/* Keep last valid snapshot and visible original error. */}}
    finally{locked.current=false;setBusy(false);}
  }
  useEffect(()=>{const id=sessionStorage.getItem('logiroute-session');if(id){active.current=id;void request(`/sessions/${id}`).then(value=>{receive(value);setSelected(value.vehicles[0]?.id??'');}).catch(e=>setError(String(e)));}const timer=setInterval(()=>{if(active.current&&!locked.current){const id=active.current;void request(`/sessions/${id}`).then(receive).catch(e=>{setError(String(e));setPlaying(false);});}},2000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{if(!playing||!data?.running)return;const timer=setTimeout(()=>void command('step'),350);return()=>clearTimeout(timer);},[playing,data]);
  useEffect(()=>{if(!data?.running)setPlaying(false);},[data?.running]);
  const selectedCar=data?.vehicles.find(v=>v.id===selected);
  const selectedRoute=data?.plan?.routes.find(r=>r.vehicle===selected);
  const complete=data?.orders.filter(o=>o.status==='delivered').length??0;
  const waiting=data?.orders.filter(o=>o.status==='pending').length??0;
  const activeOrders=data?.orders.filter(o=>!['cancelled','expired'].includes(o.status)).length??0;
  const hubOrders=data?.orders.filter(o=>o.location[0]==='hub').length??0;
  const customerNodes=data?.nodes.filter(n=>n.type==='customer')??[];
  const mapPoint=(id:string)=>{const n=data?.nodes.find(n=>n.id===id);if(!n||!data)return[0,0];const xs=data.nodes.map(n=>n.x),ys=data.nodes.map(n=>n.y);const minX=Math.min(...xs),minY=Math.min(...ys);return [45+(n.x-minX)/(Math.max(...xs)-minX||1)*750,40+(n.y-minY)/(Math.max(...ys)-minY||1)*470];};
  function orderSubmit(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);void command('add',{id:f.get('id'),destination:f.get('destination'),demand:f.get('demand'),earliest:Number(f.get('earliest')),deadline:Number(f.get('deadline')),priority:f.get('priority')});}
  return <div className="dispatch">
    <header><a className="brand" href="/">➜ <b>LogiRoute</b> <em>Dispatch</em></a><span className="nav-current">车队调度</span><span className="nav-note">两级配送 · 完成截止</span><a href="/legacy">旧版单车界面 ↗</a><span className="live">● 后端状态</span></header>
    <main>
      <div className="toolbar"><div><span className="eyebrow">OPERATIONS / LIVE WORKSPACE</span><h1>物流调度工作台</h1><p>仓库 → 中转站 → 客户 · 每次签收均保留订单身份</p></div>
        <label>场景 Seed<input aria-label="场景 Seed" type="number" value={seed} onChange={e=>setSeed(e.target.value)} placeholder="配置默认值"/></label>
        <button onClick={()=>void create()} disabled={busy}>新建双目标验收场景</button>
      </div>
      {error&&<div className="error" role="alert">{error}</div>}
      {!data?<section className="welcome"><span>◈</span><h2>从一份可复现场景开始</h2><p>系统先分别验证最短距离与最低成本的完整两级方案，再创建会话。</p><button className="primary" onClick={()=>void create()} disabled={busy}>{busy?'正在生成与验证…':'创建场景'}</button></section>:<>
        <div className="metrics"><article><small>客户签收</small><strong>{complete}<i> / {activeOrders}</i></strong><span>{complete===activeOrders?'本场景客户全部签收':'到站卸货不计为客户签收'}</span></article><article><small>待规划 / 中转库存</small><strong>{waiting}<i> / {hubOrders}</i></strong><span>库存按订单 ID 跟踪</span></article><article><small>计划距离</small><strong>{fmt(data.plan?.total_distance??0)}<i> km</i></strong><span>含干线、末端及实际返程</span></article><article><small>计划运输成本</small><strong>{fmt(data.plan?.total_cost??0)}<i> 元</i></strong><span>模拟拥堵延误成本已计入</span></article><article><small>模拟时刻 / 交通版本</small><strong>{fmt(data.now)}<i> / v{data.traffic_version}</i></strong><span>revision {data.revision} · {data.id}</span></article></div>
        <div className="commandbar"><select aria-label="规划目标" value={objective} onChange={e=>setObjective(e.target.value)}><option value="distance">最短距离</option><option value="cost">最低成本</option></select>
          <button className="primary" disabled={busy||data.running} onClick={()=>void command('plan',{objective})}>规划 / 重规划</button><button disabled={busy||data.running} onClick={()=>void command('compare')}>同输入双目标比较</button>
          <button disabled={busy||data.running||!data.ready||data.needs_replan} onClick={()=>void command('depart')}>出发</button><button disabled={busy||!data.running} onClick={()=>void command('step')}>推进一个动作</button><button disabled={busy||!data.running} onClick={()=>setPlaying(!playing)}>{playing?'停止自动推进':'自动推进'}</button><button disabled={busy||!data.running} onClick={()=>{setPlaying(false);void command('pause');}}>下一节点暂停</button>
          <span className="status">{data.needs_replan?'等待检查点重规划':data.running?'执行中':'已停靠'} · {data.audit.valid?'历史审计有效':'审计异常'}</span></div>
        {data.plan&&<div className={data.plan.report.complete_all?'notice':'notice partial'}>{data.plan.report.complete_all?'计划覆盖全部当前订单':'部分服务计划'} · 已接纳 {data.plan.accepted.length} 单 / 未接纳 {data.plan.deferred.length} 单{data.plan.deferred.map(([id,why])=>` · ${id}: ${why}`).join('')}</div>}
        <div className="workspace"><aside className="panel fleet"><div className="panel-title"><h2>车队路线</h2><span>{data.vehicles.length} 辆</span></div>{data.vehicles.map((v,i)=><button className={'car '+(v.id===selected?'selected':'')} style={{'--car':colors[i%colors.length]} as React.CSSProperties} key={v.id} onClick={()=>setSelected(v.id)}><b><span>●</span> {v.id}</b><small>{v.role==='trunk'?'干线补货':'站点末端配送'} · 配送员 {v.courier_id}</small><p>基地 {v.base} → 当前 {v.position}</p><div><span>载货 <strong>{v.load} / {v.capacity}</strong></span><span>{v.current?labels[v.current.kind]:'停靠'}</span></div><small>{v.cargo.length} 张在车订单 · {v.cargo.join(', ')||'空车'}</small></button>)}<div className="hub-stock"><h3>中转站库存</h3>{data.nodes.filter(n=>n.type==='transfer').map(h=><p key={h.id}><b>{h.id}</b><span>{data.orders.filter(o=>o.location[0]==='hub'&&o.location[1]===h.id).map(o=>o.id).join(', ')||'暂无库存'}</span></p>)}</div></aside>
          <section className="panel map"><div className="panel-title"><h2>道路与配送网络</h2><span>方向箭头 · 点击道路模拟拥堵</span></div><svg viewBox="0 0 840 550" role="img" aria-label="多车实际道路地图"><defs><marker id="road-arrow" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#3b657c"/></marker></defs>{data.edges.map(e=>{const [x1,y1]=mapPoint(e.source),[x2,y2]=mapPoint(e.target);return <line key={e.source+'-'+e.target} x1={x1} y1={y1} x2={x2} y2={y2} className={'road '+e.status} markerEnd="url(#road-arrow)" onClick={()=>setRoad(e.source+'|'+e.target)}><title>{e.source} → {e.target} · {e.status}</title></line>;})}{data.plan?.routes.map(r=>r.actions.filter(a=>a.kind==='drive').map((a,j)=>{const [x1,y1]=mapPoint(a.source),[x2,y2]=mapPoint(a.target);return <line className="route" key={r.vehicle+j} x1={x1} y1={y1} x2={x2} y2={y2} stroke={colors[data.vehicles.findIndex(v=>v.id===r.vehicle)%colors.length]} opacity={selected===r.vehicle?1:.15}/>;}))}{data.nodes.map(n=>{const [x,y]=mapPoint(n.id);return <g key={n.id} transform={`translate(${x},${y})`}><circle r={n.type==='customer'?5:13} fill={n.type==='warehouse'?'#ff8a24':n.type==='transfer'?'#26d9e8':'#52728b'} stroke="#d7f2ff" strokeWidth={n.type==='customer'?1:2}/><text y={n.type==='customer'?-10:-20} textAnchor="middle">{n.id}</text>{n.type!=='customer'&&<text y="4" textAnchor="middle" className="node-symbol">{n.type==='warehouse'?'仓':'站'}</text>}</g>;})}{data.vehicles.map((v,i)=>{const [x,y]=mapPoint(v.position);return <g key={v.id} transform={`translate(${x+10},${y+14})`}><rect width="31" height="16" rx="4" fill={colors[i%4]}/><text x="15" y="11" textAnchor="middle" className="car-symbol">{v.id}</text></g>;})}</svg><div className="legend"><span>● 仓库</span><span>● 中转站</span><span>● 客户</span><span>── 选中车辆实际道路</span><span>┄ 封路</span></div><p className="map-foot">车辆标记停留在最近真实节点；已进入道路在动作完成后更新位置。路线线条为上次已验证计划，交通变化后需重规划。</p></section>
          <aside className="panel timeline"><div className="panel-title"><h2>{selectedCar?.id} · 行程</h2><span>{selectedCar?.base} 闭环</span></div><div className="timeline-scroll">{selectedRoute?.actions.map((a,i)=><div className={'stop '+a.kind} key={i}><span className="stop-dot">{a.kind==='deliver'?'✓':a.kind==='drive'?'↗':'•'}</span><div><b>{labels[a.kind]}</b><small>{a.source}{a.target!==a.source?' → '+a.target:''} {a.ids.join(', ')}</small></div><time>{fmt(a.start)}<br/>– {fmt(a.end)}</time></div>)??<p>选择目标并生成路线。</p>}</div><div className="timeline-summary">{selectedRoute?`${fmt(selectedRoute.total_distance)} km · ${fmt(selectedRoute.total_cost)} 元 · 返仓 ${fmt(selectedRoute.end_time)}`:'尚未规划'}</div></aside></div>
        {comparison.length>0&&<section className="panel compare"><h2>同输入目标对照</h2><p>仅两边全覆盖且验证有效时，指标才具有完整方案对比意义。</p><table><thead><tr><th>目标</th><th>接纳 / 未接纳</th><th>距离 km</th><th>成本 元</th><th>验证 / 覆盖</th></tr></thead><tbody>{comparison.map(p=><tr key={p.objective}><td>{p.objective}</td><td>{p.accepted.length} / {p.deferred.length}</td><td>{fmt(p.total_distance)}</td><td>{fmt(p.total_cost)}</td><td>{p.report.valid?'有效':'无效'} / {p.report.complete_all?'完整':'部分'}</td></tr>)}</tbody></table></section>}
        <div className="forms"><section className="panel"><h2>动态插单</h2><form onSubmit={orderSubmit}><label>订单 ID<input name="id" required placeholder="全生命周期唯一"/></label><label>客户<select name="destination">{customerNodes.map(n=><option key={n.id}>{n.id}</option>)}</select></label><label>需求<input name="demand" required defaultValue="1" inputMode="decimal" pattern="[0-9]+(\.[0-9]+)?"/></label><label>最早开始<input key={'start'+data.id} name="earliest" type="number" defaultValue={data.now} step="any" required/></label><label>签收截止<input key={'end'+data.id} name="deadline" type="number" defaultValue={data.now+data.settings.automatic_window_width} step="any" required/></label><label>优先级<select name="priority" defaultValue="normal">{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label><button disabled={busy}>提交订单</button></form><button disabled={busy} onClick={()=>void command('automatic',{count:1,seed:Number(seed||0),priority:'urgent'})}>自动生成 1 张紧急订单</button><p>特急：同车同批可用货物先送；紧急：可行分配优先。已进入动作不被打断。新单先入队，再暂停和重规划。</p></section>
          <section className="panel"><h2>模拟交通</h2><label>有向道路<select aria-label="有向道路" value={road} onChange={e=>setRoad(e.target.value)}><option value="">选择一条道路</option>{data.edges.map(e=><option key={e.source+'|'+e.target} value={e.source+'|'+e.target}>{e.source} → {e.target} · {e.status}</option>)}</select></label><label>道路状态<select aria-label="道路状态" value={traffic} onChange={e=>setTraffic(e.target.value)}><option value="clear">畅通</option><option value="light">轻微拥堵</option><option value="moderate">一般拥堵</option><option value="congested">严重拥堵</option><option value="blocked">封路</option></select></label><button disabled={busy||!road} onClick={()=>{setPlaying(false);const [source,target]=road.split('|');void command('traffic',{source,target,status:traffic});}}>应用路况并请求暂停</button><p>仅改变所选方向。当前已进入道路按旧版本完成，之后停在真实节点；无可行续程时等待，不瞬移返仓。</p></section></div>
        <section className="panel orders"><div className="panel-title"><h2>逐订单追踪</h2><span>签收完成时间 ≤ 截止时间</span></div><div className="table-scroll"><table><thead><tr><th>订单</th><th>目的地 / 站点</th><th>需求</th><th>优先级</th><th>时间窗</th><th>状态 / 实际位置</th><th>操作</th></tr></thead><tbody>{data.orders.map(o=><tr key={o.id}><td>{o.id}</td><td>{o.destination} / {o.hub||'未分配'}</td><td>{o.demand}</td><td><span className={'priority '+o.priority}>{o.priority}</span></td><td>{fmt(o.earliest)} – {fmt(o.deadline)}</td><td>{labels[o.status]} · {o.location.join(':')}</td><td>{o.location[0]==='warehouse'&&!['cancelled','expired'].includes(o.status)&&<><button disabled={busy} onClick={()=>void command('cancel',{id:o.id})}>取消</button><button disabled={busy} onClick={()=>void command('expire',{id:o.id})}>显式过期</button><select aria-label={o.id+' 优先级'} disabled={busy} value={o.priority} onChange={e=>void command('priority',{id:o.id,priority:e.target.value})}>{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></>}</td></tr>)}</tbody></table></div></section>
        <section className="panel history"><h2>执行事件</h2><p>仅显式推进改变仿真状态 · {data.events.length} 条记录 · {data.audit.complete_all?'执行历史证明客户全部签收':data.audit.valid?'当前历史有效，配送尚未全部完成':data.audit.violations.join(', ')}</p>{data.events.slice(-12).reverse().map((e,i)=><div key={data.events.length-i}><time>{fmt(e.time)}</time> {e.action?`${e.action.vehicle} · ${labels[e.action.kind]} · ${e.action.source} → ${e.action.target} ${e.action.ids.join(', ')}`:`${e.kind} ${e.id??''}`}</div>)}</section>
      </>}
    </main><footer>LogiRoute V2 · 自主 Dijkstra / 可行插入 · 模拟路网与交通 · {data?.audit.valid?'独立库存与道路审计有效':'尚未创建会话'}</footer>
  </div>;
}
