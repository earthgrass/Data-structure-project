import {useEffect,useRef,useState,type FormEvent} from 'react';
import type {Snapshot,Command} from '../types';
import {Badge,type Confirmation} from './Common';
import {labels,priorities,fmt} from '../presentation';

function AddOrder({data,busy,command,close,error}:{data:Snapshot;busy:boolean;command:Command;close:()=>void;error:string}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [attempted,setAttempted]=useState(false);
  useEffect(()=>{dialog.current?.showModal();},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setAttempted(true);const f=new FormData(e.currentTarget);
    const success=await command('add',{id:f.get('id'),destination:f.get('destination'),demand:f.get('demand'),earliest:Number(f.get('earliest')),deadline:Number(f.get('deadline')),priority:f.get('priority')});
    if(success)close();
  }
  return <dialog ref={dialog} className="d-order-dialog" aria-labelledby="new-order-title" onCancel={close}><div className="d-card-head"><div><h2 id="new-order-title">新增配送订单</h2><p>先加入待处理队列，规划接纳后才参与配送</p></div><button onClick={close} aria-label="关闭新增订单">×</button></div>
    <form onSubmit={e=>void submit(e)}><label>订单 ID<input name="id" autoFocus required placeholder="全生命周期唯一"/></label><label>目的地<select aria-label="目的地" name="destination">{data.nodes.filter(n=>n.type==='customer').map(n=><option key={n.id}>{n.id}</option>)}</select></label><label>原始需求量<input name="demand" required defaultValue="1" inputMode="decimal" pattern="[0-9]+(\.[0-9]+)?"/></label><label>优先级<select aria-label="订单优先级" name="priority" defaultValue="normal">{priorities.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label>最早服务开始<input name="earliest" type="number" min="0" step="any" defaultValue={data.now} required/></label><label>签收完成截止<input name="deadline" type="number" min="0" step="any" defaultValue={data.now+data.settings.automatic_window_width} required/></label>
      <p className="d-form-note">特急：同车同批可用货物优先服务；紧急：可行分配优先。进行中动作不会被打断。</p>{attempted&&error&&<p role="alert" className="d-inline-error">{error}</p>}<div className="d-actions"><button type="button" onClick={close}>返回</button><button className="d-primary" disabled={busy}>{busy?'提交中…':'加入待处理队列'}</button></div>
    </form></dialog>;
}
export function OrderTable({data,busy,command,confirm,error,seed}:{data:Snapshot;busy:boolean;command:Command;confirm:(v:Confirmation)=>void;error:string;seed:string}){
  const [search,setSearch]=useState(''),[status,setStatus]=useState('all'),[priority,setPriority]=useState('all'),[adding,setAdding]=useState(false);
  const deferred=new Map(data.plan?.deferred??[]);
  const rows=data.orders.filter(o=>(status==='all'||status==='deferred'&&deferred.has(o.id)||o.status===status)&&(priority==='all'||o.priority===priority)&&`${o.id} ${o.destination} ${o.hub}`.toLowerCase().includes(search.toLowerCase()));
  function reason(o:Snapshot['orders'][number]){
    if(['delivered','cancelled','expired'].includes(o.status))return '订单为终态，保留身份记录。';
    if(o.location[0]!=='warehouse')return '货物已出仓；本阶段不支持退货撤销。';
    if(data.vehicles.some(v=>v.current?.kind==='load'&&v.current.ids.includes(o.id)))return '装货动作已进入，不能中断或改优先级。';
    return '';
  }
  return <section className="d-card d-orders-view"><div className="d-card-head"><div><h2>逐订单管理</h2><p>{data.orders.length} 张独立订单；同一目的地可有多张订单</p></div><div className="d-actions"><button disabled={busy} onClick={()=>void command('automatic',{count:1,seed:Number(seed||0),priority:'urgent'})}>自动生成紧急单</button><button className="d-primary" disabled={busy} onClick={()=>setAdding(true)}>＋ 新增订单</button></div></div>
    <div className="d-filters"><label>搜索<input placeholder="订单 ID / 客户 / 中转站" value={search} onChange={e=>setSearch(e.target.value)}/></label><label>状态<select aria-label="状态筛选" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">全部状态</option>{['pending','planned','in_transit','delivered','cancelled','expired'].map(s=><option value={s} key={s}>{labels[s]}</option>)}<option value="deferred">上次计划未接纳</option></select></label><label>优先级筛选<select aria-label="优先级筛选" value={priority} onChange={e=>setPriority(e.target.value)}><option value="all">全部优先级</option>{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label><span>筛选结果 {rows.length} 单</span></div>
    <p className="d-table-hint">窄屏可横向滚动查看完整订单及操作列。</p><div className="d-table-scroll" tabIndex={0} aria-label="订单表，可横向滚动"><table><thead><tr><th>订单 / 目的地</th><th>优先级</th><th>签收窗口</th><th>需求量</th><th>实际状态 / 位置</th><th>订单操作</th></tr></thead><tbody>{rows.map(o=>{const disabledReason=reason(o);return <tr key={o.id}><td><b>{o.id}</b><small>{o.destination} · {o.hub||'未分配中转站'}</small></td><td><Badge tone={o.priority==='critical'?'warn':o.priority==='urgent'?'info':'neutral'}>{priorities.find(([v])=>v===o.priority)?.[1]}</Badge></td><td>{fmt(o.earliest)} – {fmt(o.deadline)}<small>截止约束签收完成</small></td><td className="d-mono">{o.demand}</td><td><Badge tone={o.status==='delivered'?'good':o.status==='expired'?'danger':'neutral'}>{labels[o.status]}</Badge><small>{o.location.join(' · ')}</small>{deferred.has(o.id)&&<small className="d-warning-text">上次未接纳：{deferred.get(o.id)}</small>}</td><td>{disabledReason?<span className="d-muted">{disabledReason}</span>:<div className="d-row-actions"><select aria-label={`${o.id} 优先级`} disabled={busy} value={o.priority} onChange={e=>{const value=e.target.value;confirm({title:`更新 ${o.id} 优先级？`,description:'更新会请求暂停；原子动作结束后需重新规划。',confirm:'确认更新',action:()=>void command('priority',{id:o.id,priority:value})});}}>{priorities.map(([v,l])=><option value={v} key={v}>{l}</option>)}</select><button disabled={busy} onClick={()=>confirm({title:`取消订单 ${o.id}？`,description:'仅取消尚未进入装货的仓库订单。其余已接纳订单仍须保留并重新规划。',confirm:'确认取消',action:()=>void command('cancel',{id:o.id})})}>取消</button><button disabled={busy} onClick={()=>confirm({title:`显式过期 ${o.id}？`,description:'此操作将订单设为过期终态；不会触发自动计时，也不会回收该 ID。',confirm:'确认过期',action:()=>void command('expire',{id:o.id})})}>过期</button></div>}</td></tr>;})}</tbody></table>{rows.length===0&&<p className="d-pad d-muted">没有符合筛选条件的订单。</p>}</div>
    {adding&&<AddOrder data={data} busy={busy} command={command} close={()=>setAdding(false)} error={error}/>}
  </section>;
}
