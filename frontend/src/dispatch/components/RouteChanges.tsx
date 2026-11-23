import type {Snapshot} from '../types';
import type {RouteChangeSummary} from '../routeChanges.mjs';
import {labels,priorities,vehicleColor} from '../presentation';
import {ReplanImpactPanel,RejectionOverview} from './PlanningInsights';

export type RouteView='before'|'after'|'changes';
export function RouteChangesPanel({data,changes,view,setView,busy,onPlan,onVehicle,onOrder}:{data:Snapshot;changes:RouteChangeSummary|null;view:RouteView;setView:(v:RouteView)=>void;busy:boolean;onOrder:(id:string)=>void;onPlan:()=>void;onVehicle:(id:string)=>void}){
 const control=data.order_control,waiting=control?.status==='waiting_checkpoint',blocked=control?.status==='blocked';
 const progress=control?.enabled&&control.change_kind?<section className={'r-auto-flow '+control.status} aria-label="自动重规划状态" aria-live="polite"><strong>{waiting?'正在停靠，随后自动重规划':blocked?'重规划受阻，配送保持暂停':data.running?'正在按新路线配送':'新路线已验证，等待继续配送'}</strong><ol><li>订单 / 路况变更已记录</li><li>{waiting?'正在完成已进入的动作':'已停靠在动作检查点'}</li><li>{control.status==='applied'?'新路线已独立验证':blocked?'无法安全应用新路线':'等待验证新路线'}</li></ol><p>{control.reason}</p>{control.status==='applied'&&!data.running&&<p>先查看地图上的路线变化，再点击“播放配送动画”继续。</p>}</section>:null;
 if(!changes)return <div className="r-change-panel"><span className="s-eyebrow">ROUTE MONITOR</span><h2>路线与订单状态</h2>{progress}<ReplanImpactPanel data={data}/><RejectionOverview data={data}/><p>{data.plan?'当前计划已应用；此页尚无路线变更前后对照。':'先规划路线，地图默认展示全部车辆。'}新增或取消订单会自动停靠并重新规划。</p><p>重规划确认后，可切换查看旧路线、新路线与变化叠加。对照记录从本页打开后开始；刷新不会丢失后端的待处理任务。</p></div>;
 const compared=changes.status==='compared',hasBaseline=changes.hasBaseline,added=new Set(changes.addedOrderIds),deferred=new Map(data.plan?.deferred??[]);
 const orders=data.orders.filter(o=>added.has(o.id));
 return <div className="r-change-panel"><span className="s-eyebrow">ROUTE MONITOR</span><h2>{compared?'路线已更新':'订单 / 路况已变化'}</h2>{progress}<ReplanImpactPanel data={data}/><RejectionOverview data={data}/><p role="status">{!hasBaseline?(compared?'已生成首份计划，当前没有旧路线可比较。':'订单有变化，等待生成首份计划。'):compared?`已对比 ${changes.changedVehicleIds.length} 辆车的行程变化。`:'旧计划已保留，等待后端重规划。订单变更尚不代表已安排新路线。'}</p>
  <div className="r-view-switch" aria-label="路线对照模式">{([['before','变更前'],['after','当前路线'],['changes','变化叠加']] as const).map(([v,label])=><button key={v} disabled={!hasBaseline&&v!=='after'} aria-pressed={view===v} onClick={()=>setView(v)}>{label}</button>)}</div>
  <div className="r-change-key"><span><i className="old"/>灰色虚线：移除路段</span><span><i className="new"/>橙色描边：新增路段</span><span>车辆颜色：保留 / 当前路线</span></div>
  <p className="r-version">原快照 v{changes.baselineRevision}{compared?` → 新计划 v${changes.appliedRevision}`:' → 待规划'} · 同一会话</p>
  {orders.length>0&&<section><h3>新增 {orders.length} 张订单</h3>{orders.map(o=><article key={o.id} className="r-new-order"><b>{o.id} <em>{priorities.find(([id])=>id===o.priority)?.[1]}</em></b><span>{data.nodes.find(n=>n.id===o.destination)?.name??o.destination}</span>{['pending','planned','in_transit'].includes(o.status)?<button onClick={()=>onOrder(o.destination)}>在地图定位 {o.id}</button>:<span>已从地图移除，身份记录保留</span>}<span>{labels[o.status]}{compared?(deferred.has(o.id)?` · 未接纳：${deferred.get(o.id)}`:data.plan?.accepted.includes(o.id)?' · 新计划已接纳':''):' · 待重新规划'}</span></article>)}</section>}
  {changes.cancelledOrderIds.length>0&&<p>已移出待配送路线（取消 / 过期）：{changes.cancelledOrderIds.join('、')}；历史订单仍保留。</p>}
  {changes.priorityOrderIds.length>0&&<p>优先级调整：{changes.priorityOrderIds.join('、')}</p>}
  {changes.trafficChanged&&<p>路况已更新，已进入的动作继续按原承诺完成。</p>}
  {!compared&&<button className="d-primary r-replan" disabled={busy||data.running||waiting} onClick={onPlan}>{waiting?'正在自动停靠与规划':data.running?'请先推进至检查点':blocked?'重试规划并展示变化':'重新规划并展示变化'}</button>}
  {compared&&hasBaseline&&<section><h3>逐车变化</h3>{changes.vehicleChanges.filter(v=>v.changed).map(v=><article className="r-vehicle-change" key={v.vehicle}><button style={{borderLeftColor:vehicleColor(data,v.vehicle)}} onClick={()=>onVehicle(v.vehicle)}>{v.vehicle} · 查看此车</button><p>新增 {v.addedEdges.length} / 移除 {v.removedEdges.length} 条方向路段</p><details><summary>服务顺序对照{v.timingChanged?' · 时刻有调整':''}</summary><p>原：{v.beforeServiceIds.join(' → ')||'无客户任务'}</p><p>现：{v.afterServiceIds.join(' → ')||'无客户任务'}</p></details></article>)}{changes.changedVehicleIds.length===0&&<p>路线与服务顺序未变化。请查看新增订单是否未被接纳；系统没有绘制虚构的新路线。</p>}</section>}
  <p className="r-version">对照仅切换路线，订单与车辆位置保持当前状态。道路按车辆与方向比较；服务顺序单独核对。共享路段可在关闭“全部路线”后逐车查看。已执行的历史路段不计作本轮移除。物理道路相同也可能有服务顺序变化。</p>
 </div>;
}
