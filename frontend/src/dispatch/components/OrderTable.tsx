import {useEffect,useRef,useState,type FormEvent} from 'react';
import type {Snapshot,Command} from '../types';
import {Badge,type Confirmation} from './Common';
import {labels,priorities,fmt} from '../presentation';
import {matchesOrder,locationText} from '../product.mjs';
import {RejectionDetails} from './PlanningInsights';
import {rejectionContext} from '../planning-insights.mjs';
import {cancellationBlockReason} from '../order-controls.mjs';

export function AddOrder({data,busy,command,close,error,destination}:{data:Snapshot;busy:boolean;command:Command;close:()=>void;error:string;destination?:string}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [attempted,setAttempted]=useState(false);
  const [selectedPriority,setSelectedPriority]=useState('normal');
  const errorBox=useRef<HTMLParagraphElement>(null);
  useEffect(()=>{if(attempted&&error)errorBox.current?.focus();},[attempted,error,busy]);
  useEffect(()=>{dialog.current?.showModal();},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setAttempted(true);const f=new FormData(e.currentTarget);
    const success=await command('add',{id:f.get('id'),destination:f.get('destination'),demand:f.get('demand'),earliest:Number(f.get('earliest')),deadline:Number(f.get('deadline')),priority:f.get('priority'),...(f.get('priority')==='critical'?{protect_critical:true,allow_late:f.get('allow_late')==='on'}:{})});
    if(success)close();
  }
  return <dialog ref={dialog} className="d-order-dialog" aria-labelledby="new-order-title" onCancel={close}><div className="d-card-head"><div><h2 id="new-order-title">新增配送订单</h2><p>特急单优先安排最快可验证车辆，允许明确记录迟到</p></div><button onClick={close} aria-label="关闭新增订单">×</button></div>
    <form onSubmit={e=>void submit(e)}><label>订单 ID<input name="id" autoFocus required placeholder="全生命周期唯一"/></label><label>目的地<select aria-label="目的地" name="destination" defaultValue={destination}>{data.nodes.filter(n=>n.type==='customer').map(n=><option key={n.id} value={n.id}>{n.id} · {n.name??'配送点'}</option>)}</select></label><label>原始需求量<input name="demand" required defaultValue="1" inputMode="decimal" pattern="[0-9]+(\.[0-9]+)?"/></label><label>优先级<select aria-label="订单优先级" name="priority" value={selectedPriority} onChange={e=>setSelectedPriority(e.target.value)}>{priorities.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label>最早服务开始<input name="earliest" type="number" min="0" step="any" defaultValue={data.now} required/></label><label>签收完成截止<input name="deadline" type="number" min="0" step="any" defaultValue={data.now+data.settings.automatic_window_width} required/></label>
      {selectedPriority==='critical'&&<label className="d-late-critical-option"><input type="checkbox" name="allow_late" defaultChecked/>允许迟到签收；仍优先安排最快可行车辆并显示预计迟到</label>}
      <p className="d-form-note">特急优先：冲突时尚未装车的普通／紧急订单可退回待规划；既有特急与已进入动作的货物保持保护。允许迟到时，可填写已过截止的有效时间窗；载重不足或道路不可达仍可能无法接纳。</p>{attempted&&error&&<p ref={errorBox} tabIndex={-1} role="alert" className="d-inline-error">{error}</p>}<div className="d-actions"><button type="button" onClick={close}>返回</button><button className="d-primary" disabled={busy}>{busy?'提交中…':'加入待处理队列'}</button></div>
    </form></dialog>;
}
export function OrderTable({data,busy,command,confirm,error,seed}:{data:Snapshot;busy:boolean;command:Command;confirm:(v:Confirmation)=>void;error:string;seed:string}){
  const [search,setSearch]=useState(''),[status,setStatus]=useState('all'),[priority,setPriority]=useState('all'),[adding,setAdding]=useState(false);
  const deferred=new Map(data.plan?.deferred??[]);
  for(const item of rejectionContext(data).items)deferred.set(item.order_id,item.reason);
  const rows=data.orders.filter(o=>(status==='all'||status==='deferred'&&deferred.has(o.id)||o.status===status)&&(priority==='all'||o.priority===priority)&&matchesOrder(o,data.nodes,search));
  function reason(o:Snapshot['orders'][number]){return cancellationBlockReason(data,o);}
  return <section className="d-card d-orders-view"><div className="d-card-head"><div><h2>逐订单管理</h2><p>{data.orders.length} 张独立订单；同一目的地可有多张订单</p></div><div className="d-actions"><button disabled={busy} onClick={()=>void command('automatic',{count:1,seed:Number(seed||0),priority:'urgent'})}>自动生成紧急单</button><button className="d-primary" disabled={busy} onClick={()=>setAdding(true)}>＋ 新增订单</button></div></div>
    <div className="d-filters"><label>搜索<input placeholder="订单 ID / 客户 / 中转站" value={search} onChange={e=>setSearch(e.target.value)}/></label><label>状态<select aria-label="状态筛选" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">全部状态</option>{['pending','planned','in_transit','delivered','cancelled','expired'].map(s=><option value={s} key={s}>{labels[s]}</option>)}<option value="deferred">上次计划未接纳</option></select></label><label>优先级筛选<select aria-label="优先级筛选" value={priority} onChange={e=>setPriority(e.target.value)}><option value="all">全部优先级</option>{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label><span>筛选结果 {rows.length} 单</span></div>
    <p className="d-table-hint">窄屏可横向滚动查看完整订单及操作列；地图上点击待完成订单也可直接取消尚未装车的订单。</p><div className="d-table-scroll" tabIndex={0} aria-label="订单表，可横向滚动"><table><thead><tr><th>订单 / 目的地</th><th>优先级</th><th>签收窗口</th><th>需求量</th><th>实际状态 / 位置</th><th>订单操作</th></tr></thead><tbody>{rows.map(o=>{const disabledReason=reason(o);return <tr key={o.id}><td><b>{o.id}</b><small>{data.nodes.find(n=>n.id===o.destination)?.name??o.destination} · {o.destination} · {o.hub||'未分配中转站'}</small></td><td><Badge tone={o.priority==='critical'?'warn':o.priority==='urgent'?'info':'neutral'}>{priorities.find(([v])=>v===o.priority)?.[1]}</Badge></td><td>{fmt(o.earliest)} – {fmt(o.deadline)}<small>{o.allow_late?'允许迟到，优先最快可行车辆':'截止约束签收完成'}</small></td><td className="d-mono">{o.demand}</td><td><Badge tone={o.status==='delivered'?'good':o.status==='expired'?'danger':'neutral'}>{labels[o.status]}</Badge><small>{locationText(o,data.nodes)}</small>{deferred.has(o.id)&&<small className="d-warning-text">上次未接纳：{deferred.get(o.id)}</small>}<RejectionDetails data={data} orderId={o.id}/></td><td>{disabledReason?<span className="d-muted">{disabledReason}</span>:<div className="d-row-actions"><select aria-label={`${o.id} 优先级`} disabled={busy} value={o.priority} onChange={e=>{const value=e.target.value;confirm({title:`更新 ${o.id} 优先级？`,description:'更新后自动停靠并重新规划；进行中的动作会先完成。',confirm:'确认更新',action:()=>void command('priority',{id:o.id,priority:value})});}}>{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select><button disabled={busy} onClick={()=>confirm({title:`取消订单 ${o.id}？`,description:'仅取消尚未进入装货的仓库订单。确认后从地图移除，并自动停靠重规划其余任务。',confirm:'确认取消',action:()=>void command('cancel',{id:o.id})})}>取消</button><button disabled={busy} onClick={()=>confirm({title:`显式过期 ${o.id}？`,description:'此操作将订单设为过期终态；不会触发自动计时，也不会回收该 ID。',confirm:'确认过期',action:()=>void command('expire',{id:o.id})})}>过期</button></div>}</td></tr>;})}</tbody></table>{rows.length===0&&<p className="d-pad d-muted">没有符合筛选条件的订单。</p>}</div>
    {adding&&<AddOrder data={data} busy={busy} command={command} close={()=>setAdding(false)} error={error}/>}
  </section>;
}
