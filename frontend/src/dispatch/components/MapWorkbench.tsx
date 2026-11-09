import {useEffect,useState,type ReactNode} from 'react';
import type {Snapshot,Workspace} from '../types';
import {workspaces} from './AppShell';
import {vehicleColor,fmt} from '../presentation';

export function MapWorkbench({data,map,playback,toolbar,orders,fleet,inspector,seed,setSeed,create,disabled,selected,onVehicle,navigate,error,message,reconnect,pausePlayback}:{data:Snapshot;map:ReactNode;playback:ReactNode;toolbar:ReactNode;orders:ReactNode;fleet:ReactNode;inspector:ReactNode;seed:string;setSeed:(v:string)=>void;create:()=>void;disabled:boolean;selected:string;onVehicle:(id:string)=>void;navigate:(w:Workspace)=>void;error:string;message:string;reconnect:()=>void;pausePlayback:()=>void}){
  const [panel,setPanel]=useState<'orders'|'fleet'|'tools'|null>(null);
  useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setPanel(null);};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[]);
  const active=data.orders.filter(o=>!['cancelled','expired'].includes(o.status));
  const campusNodes=new Set(data.nodes.filter(n=>n.zone==='campus').map(n=>n.id));
  const campusOrders=active.filter(o=>campusNodes.has(o.destination)).length;
  return <div className="dispatch d-map-workbench">
    <div className="d-map-world">{map}</div>
    <header className="d-map-topbar"><a className="d-map-wordmark" href="#overview"><span>↗</span> LogiRoute</a><div className="d-map-title"><strong>{data.map?.campus_profile?'北工大校内配送':data.map?'北工大配送沙盘':'配送网络沙盘'}</strong><small>{data.map?.campus_profile?'校内快递站 · 四门外卖柜 · 校内订单':data.map?'真实道路 · 固定候选池 · 动态订单':'随机示意路网 · 新建场景切换真实地图'}</small></div><div className="d-map-top-actions"><button aria-expanded={panel==='orders'} onClick={()=>{pausePlayback();setPanel(panel==='orders'?null:'orders');}}>订单 <b>{active.length}</b></button><button aria-expanded={panel==='fleet'} onClick={()=>setPanel(panel==='fleet'?null:'fleet')}>车队</button><button aria-expanded={panel==='tools'} onClick={()=>setPanel(panel==='tools'?null:'tools')}>场景与管理</button></div></header>
    <div className="d-map-summary"><span><i className="d-live-dot"/> {data.map?.campus_profile?`校内 ${campusOrders}/${active.length} 单`:data.map?'离线真实路网':'示意路网'}</span><span><b>{data.orders.filter(o=>o.status==='delivered').length}/{active.length}</b> 已签收</span><span><b>{fmt(data.now)}</b> 模拟分钟</span><span>{data.map?.candidate_count??data.nodes.filter(n=>n.type==='customer').length} 个候选地点</span>{data.plan&&<span className={data.plan.deferred.length?'d-map-partial':''}>本轮接纳 {data.plan.accepted.length} · 未接纳 {data.plan.deferred.length}</span>}</div>
    {!data.map?.campus_profile&&<div className="d-map-migration"><b>{data.map?'当前为周边演示，可切换校内配送':'当前为历史随机场景'}</b><button disabled={disabled} onClick={create}>创建校内配送场景</button></div>}
    <nav className="d-map-fleet-switch" aria-label="地图车辆选择">{data.vehicles.map(v=><button key={v.id} aria-pressed={selected===v.id} style={{borderLeftColor:vehicleColor(data,v.id)}} onClick={()=>onVehicle(v.id)}><i style={{background:vehicleColor(data,v.id)}}/><b>{v.id}</b><span>{v.cargo.length} 单</span></button>)}</nav>
    {panel&&<aside className={'d-map-drawer '+panel} aria-label={panel==='orders'?'地图订单面板':panel==='fleet'?'地图车队面板':'场景管理面板'}><div className="d-map-drawer-head"><strong>{panel==='orders'?'订单与候选地点':panel==='fleet'?'车队与行程':'场景与管理'}</strong><button aria-label="收起地图面板" onClick={()=>setPanel(null)}>×</button></div>
      {panel==='orders'?<><p className="d-map-panel-note">支持新增订单；尚未装货的订单可取消。地图上点击候选点，也可直接在该地点下单。新增后需规划接纳。</p>{orders}</>:panel==='fleet'?<>{fleet}{inspector}</>:<div className="d-map-settings"><h3>固定地图，随机任务</h3><p>{data.map?.campus_profile?`固定 ${data.map.campus_candidate_count} 个校内地点和 8 个周边地点；初始 ${data.map.initial_orders} 单中，校内 ${data.map.initial_campus_orders} 单。更换 Seed 改变任务，地点和道路保持固定。`:'每次从同一候选池选择配送地点，仓库、中转站和道路保持固定。更换 Seed 改变初始订单。'}</p><label>场景 Seed<input aria-label="场景 Seed" type="number" step="1" placeholder="默认 42" value={seed} onChange={e=>setSeed(e.target.value)}/></label><button className="d-primary" disabled={disabled} onClick={create}>新建校内配送场景</button><p>{data.map?.campus_profile?'中转点对应游泳馆北侧快递站与东、西、北、南门外卖柜。位置按用户描述近似落点；楼栋订单使用附近道路服务点，支持继续校准。':'仓库、中转站及收货点是位于真实道路节点的模拟业务设施。'}</p><div className="d-map-workspace-links">{workspaces.filter(w=>w.id!=='overview').map(w=><button key={w.id} onClick={()=>navigate(w.id)}>{w.title} ↗</button>)}</div><button onClick={reconnect}>重新连接后端</button></div>}
    </aside>}
    <footer className="d-map-playback-dock">{playback}{toolbar}</footer>
    {error&&<div className="d-map-feedback error" role="alert">{error}<button onClick={reconnect}>重新连接</button></div>}
    {message&&!error&&<div className="d-map-feedback" role="status">{message}</div>}
  </div>;
}
