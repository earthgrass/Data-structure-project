import {useMemo,useState} from 'react';
import type {Snapshot,Road} from '../types';
import {useNetworkViewport} from '../hooks/useNetworkViewport';
import {vehicleColor,trafficLabels,fmt} from '../presentation';
import {Badge,Icon} from './Common';
import {vehiclePoint,physicalRoads,driveFraction} from '../motion.mjs';
import {actionPhase} from '../sync.mjs';

export function NetworkCanvas({data,selected,onVehicle,onRoad,clock=null}:{data:Snapshot;selected:string;onVehicle:(id:string)=>void;onRoad?:(road:Road)=>void;clock?:number|null}){
  const view=useNetworkViewport(data.nodes),[node,setNode]=useState(''),[edge,setEdge]=useState('');
  const chosenNode=data.nodes.find(n=>n.id===node),chosenEdge=data.edges.find(r=>r.source+'|'+r.target===edge);
  const info=chosenNode?`${chosenNode.id} · 原始坐标 ${fmt(chosenNode.x)}, ${fmt(chosenNode.y)}`:chosenEdge?`${chosenEdge.source} → ${chosenEdge.target} · ${trafficLabels[chosenEdge.status]} · ${fmt(chosenEdge.distance)} km · ${fmt(chosenEdge.travel_time)} 分钟`:'';
  const serviceNodes=useMemo(()=>new Set(data.plan?.routes.find(r=>r.vehicle===selected)?.actions.filter(a=>a.kind==='deliver'||a.kind==='unload').map(a=>a.target)),[data.plan,selected]);
  const roads=useMemo(()=>physicalRoads(data.edges),[data.edges]);
  const [showRoads,setShowRoads]=useState(true);
  const visualClock=clock??data.now;
  const deliveries=useMemo(()=>{
    const result=new Map<string,{count:number;done:number}>();
    for(const order of data.orders){if(order.status==='cancelled'||order.status==='expired')continue;const item=result.get(order.destination)??{count:0,done:0};item.count++;if(order.status==='delivered')item.done++;result.set(order.destination,item);}
    return result;
  },[data.orders]);
  function chooseRoad(road:Road){setNode('');setEdge(road.source+'|'+road.target);onRoad?.(road);}
  return <section className="d-card d-network" aria-label="配送网络">
    <div className="d-card-head"><div><h2>配送网络</h2><p>{data.nodes.length} 节点 · {roads.length} 条物理道路 · {data.edges.length} 条方向边</p></div><Badge tone="info">{selected} 路线</Badge></div>
    <div className="d-map-frame" ref={view.frame}>
      <svg viewBox={`0 0 ${view.size.width} ${view.size.height}`} aria-label="真实场景配送地图" role="img">
        <defs><pattern id="map-grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#dae2ec"/></pattern><marker id="route-direction" markerUnits="userSpaceOnUse" markerWidth="8" markerHeight="8" refX="13" refY="4" orient="auto"><path d="M0 0 8 4 0 8" fill="context-stroke"/></marker></defs>
        <rect width="100%" height="100%" fill="url(#map-grid)"/>
        <g transform={view.transform}>
          {showRoads&&roads.map(group=>{const r=group.directions[0];const [x1,y1]=view.points.get(r.source)!,[x2,y2]=view.points.get(r.target)!;return <g key={r.source+r.target} onClick={()=>chooseRoad(r)}><line className={'d-road '+r.status+(edge===r.source+'|'+r.target?' chosen':'')} x1={x1} y1={y1} x2={x2} y2={y2}/><line className="d-road-hit" x1={x1} y1={y1} x2={x2} y2={y2}><title>{group.directions.map(d=>`${d.source} → ${d.target} · ${trafficLabels[d.status]}`).join(" / ")}</title></line></g>;})}
          {data.plan?.routes.map(r=>r.actions.filter(a=>a.kind==='drive').map((a,i)=>{const [x1,y1]=view.points.get(a.source)!,[x2,y2]=view.points.get(a.target)!;const phase=actionPhase(data,a);const progress=phase==='completed'?1:phase==='current'?driveFraction(a,visualClock):0;return <g key={r.vehicle+i}><line className={'d-route '+(r.vehicle===selected?'active planned':'')} style={{stroke:vehicleColor(data,r.vehicle)}} x1={x1} y1={y1} x2={x2} y2={y2}/>{progress>0&&<line className={'d-route '+(r.vehicle===selected?'active':'')} style={{stroke:vehicleColor(data,r.vehicle)}} x1={x1} y1={y1} x2={x1+(x2-x1)*progress} y2={y1+(y2-y1)*progress} markerEnd={r.vehicle===selected?'url(#route-direction)':undefined}/>}</g>;}))}
          {data.edges.filter(r=>r.status==='blocked'||r.status==='congested').map(r=>{const [x1,y1]=view.points.get(r.source)!,[x2,y2]=view.points.get(r.target)!;return <line key={'traffic'+r.source+r.target} className={'d-traffic-overlay '+r.status} x1={x1} y1={y1} x2={x2} y2={y2}/>;})}
          {data.nodes.map(n=>{const [x,y]=view.points.get(n.id)!;const key=n.id;const delivery=deliveries.get(key);return <g key={key} className={'d-map-node '+n.type+(node===key?' selected':'')+(delivery?.done===delivery?.count&&delivery?' served':'')} transform={`translate(${x} ${y})`} role="button" tabIndex={0} aria-label={`${n.id} ${n.type==='warehouse'?'仓库':n.type==='transfer'?'中转站':'客户'}`} onClick={()=>{setNode(key);setEdge('');}} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setNode(key);setEdge('');}}}>
            <title>{n.id} · ({n.x}, {n.y}){delivery?` · 有效订单签收 ${delivery.done}/${delivery.count}`:""}</title>
            {n.type==='warehouse'?<><rect x="-16" y="-16" width="32" height="32" rx="8"/><path d="m-8-3 8-6 8 6v10H-8zM-3 7V1h6v6"/></>:n.type==='transfer'?<><path className="hub-shape" d="M0-18 18 0 0 18-18 0Z"/><path d="M-7-5H7V5H-7zM-7-1H7M0-5V5"/></>:<circle r="8"/>}
            {(n.type!=='customer'||serviceNodes.has(key)||node===key)&&<text x={n.type==='warehouse'?-24:0} y={n.type==='warehouse'?4:n.type==='customer'?-16:-25} textAnchor={n.type==='warehouse'?'end':'middle'}>{key}</text>}
          </g>;})}
          {data.vehicles.map(v=>{const [x,y]=vehiclePoint(v,visualClock,view.points);return <g key={v.id} transform={`translate(${x+13} ${y+13})`} className={'d-map-car '+(v.current?.kind??'idle')+(clock!==null?' animating':'')} data-vehicle={v.id} data-progress={v.current?.kind==='drive'?driveFraction(v.current,visualClock):0} role="button" tabIndex={0} aria-label={`地图选择 ${v.id}`} onClick={()=>onVehicle(v.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onVehicle(v.id);}}}><circle className="d-car-halo" cx="8" cy="12" r="20" fill="none" stroke={vehicleColor(data,v.id)}/><rect width={v.id.length*8+20} height="24" rx="6" fill={vehicleColor(data,v.id)}/><text x="10" y="16">{v.id}</text><title>{v.id} · 最近到达 {v.position}{v.current?.kind==='drive'?` · 正在 ${v.current.source} → ${v.current.target} 行驶`:''}</title></g>;})}
        </g>
      </svg>
      <div className="d-map-tools" aria-label="地图视口控制"><button aria-label="放大地图" onClick={()=>view.zoomBy(.25)} disabled={view.zoom>=2.5}>＋</button><span>{Math.round(view.zoom*100)}%</span><button aria-label="缩小地图" onClick={()=>view.zoomBy(-.25)} disabled={view.zoom<=1}>−</button><button aria-label="重置地图视口" onClick={view.reset}>适配</button><button aria-label="定位选中车辆" onClick={()=>view.focus(data.vehicles.find(v=>v.id===selected)?.position??'')}><Icon name="pin" size={18}/></button></div>
      {info&&<div className="d-map-info" role="status">{info}<button aria-label="关闭地图详情" onClick={()=>{setNode('');setEdge('');}}>×</button></div>}
    </div>
    <div className="d-map-legend"><label className="d-road-toggle"><input type="checkbox" checked={showRoads} onChange={e=>setShowRoads(e.target.checked)}/>道路底图</label><span><i className="warehouse"/>仓库</span><span><i className="hub"/>中转站</span><span><i className="customer"/>客户</span><span>━ 已行驶 / ┄ 计划</span><span className="d-muted">示意坐标 · 动画按已确认动作插值，非 GPS</span></div>
  </section>;
}
