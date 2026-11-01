import type {ReactNode} from 'react';
import type {Connection,Snapshot,Workspace} from '../types';
import {Badge,Icon} from './Common';
export const workspaces:{id:Workspace;title:string;sub:string}[]=[
  {id:'overview',title:'调度总览',sub:'地图、车队与下一步操作'},
  {id:'fleet',title:'车队管理',sub:'车辆、载货与完整行程'},
  {id:'orders',title:'订单中心',sub:'逐订单身份与签收截止'},
  {id:'inventory',title:'库存与中转',sub:'仓库库存与两级配送流转'},
  {id:'traffic',title:'交通与路线',sub:'方向性路况与路线重规划'},
  {id:'audit',title:'实验与审计',sub:'同输入目标对比与真实执行证据'},
];
export function AppShell({workspace,onWorkspace,connection,data,reconnect,headerActions,children}:{workspace:Workspace;onWorkspace:(w:Workspace)=>void;connection:Connection;data:Snapshot|null;reconnect:()=>void;headerActions:ReactNode;children:ReactNode}){
  const status={connected:'已连接',connecting:'连接中',failed:'连接失败',missing:'当前会话不存在'}[connection];
  return <div className="dispatch d-shell"><a className="d-skip" href="#dispatch-main">跳至工作区</a>
    <aside className="d-sidebar"><a className="d-brand" href="/"><span>↗</span><div>LogiRoute<small>LOGISTICS COMMAND</small></div></a>
      <p className="d-nav-label">运营工作区</p><nav aria-label="工作区导航">{workspaces.map(w=><button key={w.id} onClick={()=>onWorkspace(w.id)} aria-current={workspace===w.id?'page':undefined}><Icon name={w.id}/><span>{w.title}</span>{workspace===w.id&&<i/>}</button>)}</nav>
      <div className="d-sidebar-bottom"><div><Icon name="audit"/><span>两级配送 · 完成截止<small>逐订单追踪 · 独立验证</small></span></div><a href="/legacy">旧版单车工作台 <span>↗</span></a></div>
    </aside>
    <div className="d-shell-body"><header className="d-topbar"><span className="d-breadcrumb">运营指挥中心 <i>/</i> {workspaces.find(w=>w.id===workspace)?.title}</span>{headerActions}<div className="d-connection"><Badge tone={connection==='connected'?'good':connection==='failed'||connection==='missing'?'danger':'neutral'}><i/> {status}</Badge><button onClick={reconnect}>重新连接</button><span className="d-avatar">LR</span></div></header>
      <main id="dispatch-main" className="d-main"><div className="d-page-heading"><div><h1>{workspaces.find(w=>w.id===workspace)?.title}</h1><p>{workspaces.find(w=>w.id===workspace)?.sub}</p></div><div className="d-session-version">{data?<><b>{data.id}</b><span>revision {data.revision} · 交通 v{data.traffic_version}</span></>:<span>尚未创建调度场景</span>}</div></div>{children}</main>
    </div>
  </div>;
}
