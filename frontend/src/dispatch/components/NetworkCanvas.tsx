import {useMemo,useRef,useState} from 'react';
import type {Snapshot,Road} from '../types';
import {useNetworkViewport} from '../hooks/useNetworkViewport';
import {vehicleColor,trafficLabels,fmt} from '../presentation';
import {Badge,Icon} from './Common';
import {vehiclePoint,physicalRoads,driveFraction} from '../motion.mjs';
import {polylinePrefix,pathData,polylinePoint,type Point} from '../geography.mjs';
import {actionPhase} from '../sync.mjs';

export function NetworkCanvas({data,selected,onVehicle,onRoad,onCandidate,clock=null}:{data:Snapshot;selected:string;onVehicle:(id:string)=>void;onRoad?:(road:Road)=>void;onCandidate?:(id:string)=>void;clock?:number|null}){
  const view=useNetworkViewport(data.nodes,data.map?.bounds),[node,setNode]=useState(''),[edge,setEdge]=useState('');
  const drag=useRef<{x:number;y:number}|null>(null);
  const chosenNode=data.nodes.find(n=>n.id===node),chosenEdge=data.edges.find(r=>r.source+'|'+r.target===edge);
  const info=chosenNode?`${chosenNode.id} · ${chosenNode.name??'配送点'}${chosenNode.lon?` · ${chosenNode.lon.toFixed(5)}, ${chosenNode.lat?.toFixed(5)}`:''}`:chosenEdge?`${chosenEdge.name??''} · ${chosenEdge.source} → ${chosenEdge.target} · ${trafficLabels[chosenEdge.status]} · ${fmt(chosenEdge.distance)} km`:'';
  const roads=useMemo(()=>physicalRoads(data.edges),[data.edges]);
  const geometry=useMemo(()=>new Map(data.edges.map(r=>[r.source+'|'+r.target,r.geometry&&view.project?r.geometry.map(view.project):[view.points.get(r.source)!,view.points.get(r.target)!]])),[data.edges,view.project,view.points]);
  const [showRoads,setShowRoads]=useState(true),[showPool,setShowPool]=useState(true);
  const visualClock=clock??data.now;
  const deliveries=useMemo(()=>{
    const result=new Map<string,{count:number;done:number}>();
    for(const order of data.orders){if(order.status==='cancelled'||order.status==='expired')continue;const item=result.get(order.destination)??{count:0,done:0};item.count++;if(order.status==='delivered')item.done++;result.set(order.destination,item);}
    return result;
  },[data.orders]);
  const background=useMemo(()=>{
    if(!data.map||!view.project)return null;
    const project=view.project,labels:{name:string;point:Point}[]=[],used=new Set<string>();
    for(const road of data.map.background_roads){
      if(!road.name||used.has(road.name)||!['primary','secondary','tertiary'].includes(road.kind))continue;
      const line=road.geometry.map(project),p=polylinePoint(line,.5);
      const length=line.reduce((sum,a,i)=>i?sum+Math.hypot(a[0]-line[i-1][0],a[1]-line[i-1][1]):0,0);
      if(length<90||labels.some(l=>Math.abs(l.point[0]-p[0])<100&&Math.abs(l.point[1]-p[1])<55))continue;
      labels.push({name:road.name,point:p});used.add(road.name);
    }
    const areas:{name:string;point:Point}[]=[];
    for(const f of data.map.features){
      if(!f.name||f.kind!=='land'||areas.some(a=>a.name===f.name))continue;
      const point=polylinePoint(f.geometry.map(project),.5);
      if(areas.some(a=>Math.abs(a.point[0]-point[0])*view.zoom<150&&Math.abs(a.point[1]-point[1])*view.zoom<65))continue;
      areas.push({name:f.name,point});
    }
    return <g className="d-geographic-base" pointerEvents="none">
      {data.map.features.map((f,i)=><path key={i} className={'d-geo-'+f.kind} d={pathData(f.geometry.map(project))+' Z'}/>)}
      {data.map.background_roads.map((r,i)=><path key={'case'+i} className={'d-geo-road-casing '+r.kind} d={pathData(r.geometry.map(project))}/>)}
      {data.map.background_roads.map((r,i)=><path key={'road'+i} className={'d-geo-road '+r.kind} d={pathData(r.geometry.map(project))}/>)}
      {labels.map(l=><text key={l.name} className="d-street-label" style={{fontSize:11/view.zoom,strokeWidth:3/view.zoom}} x={l.point[0]} y={l.point[1]}>{l.name}</text>)}
      {areas.map(a=><text key={a.name} className="d-area-label" style={{fontSize:14/view.zoom,strokeWidth:3/view.zoom}} x={a.point[0]} y={a.point[1]}>{a.name}</text>)}
    </g>;
  },[data.map,view.project,view.zoom]);
  function chooseRoad(road:Road){setNode('');setEdge(road.source+'|'+road.target);onRoad?.(road);}
  function chooseNode(id:string){setNode(id);setEdge('');}
  return <section className={'d-card d-network '+(data.map?'geographic':'')} aria-label="配送网络">
    <div className="d-card-head"><div><h2>{data.map?'北工大周边 · 真实道路':'配送网络'}</h2><p>{data.map?`${data.map.candidate_count} 个固定候选点 · ${data.orders.length} 张订单`:`${data.nodes.length} 节点 · ${roads.length} 条物理道路 · ${data.edges.length} 条方向边`}</p></div><Badge tone="info">{selected} 路线</Badge></div>
    <div className="d-map-frame" ref={view.frame}>
      <svg viewBox={`0 0 ${view.size.width} ${view.size.height}`} aria-label={data.map?'北工大周边真实道路配送地图':'真实场景配送地图'} role="img"
        onPointerDown={e=>{if((e.target as Element).closest('[role="button"]'))return;drag.current={x:e.clientX,y:e.clientY};e.currentTarget.setPointerCapture(e.pointerId);}}
        onPointerMove={e=>{if(!drag.current)return;view.panBy(e.clientX-drag.current.x,e.clientY-drag.current.y);drag.current={x:e.clientX,y:e.clientY};}}
        onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onWheel={e=>view.zoomBy(e.deltaY<0?.2:-.2)}>
        <defs><pattern id="map-grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#dae2ec"/></pattern><marker id="route-direction" markerUnits="userSpaceOnUse" markerWidth="8" markerHeight="8" refX="5" refY="4" orient="auto"><path d="M0 0 8 4 0 8" fill="context-stroke"/></marker></defs>
        <rect width="100%" height="100%" fill={data.map?'#f3f1ea':'url(#map-grid)'}/>
        <g transform={view.transform}>
          {showRoads&&background}
          {showRoads&&roads.map(group=>{const r=group.directions[0],d=pathData(geometry.get(r.source+'|'+r.target)!);return <g key={group.key} onClick={()=>chooseRoad(r)}><path className={'d-road '+r.status+(edge===r.source+'|'+r.target?' chosen':'')} d={d}/><path className="d-road-hit" d={d}><title>{r.name??''} · {group.directions.map(v=>`${v.source} → ${v.target} · ${trafficLabels[v.status]}`).join(' / ')}</title></path></g>;})}
          {data.plan?.routes.map(r=>r.actions.filter(a=>a.kind==='drive').map((a,i)=>{const line=geometry.get(a.source+'|'+a.target)!;const phase=actionPhase(data,a),progress=phase==='completed'?1:phase==='current'?driveFraction(a,visualClock):0;return <g key={r.vehicle+i}><path className={'d-route '+(r.vehicle===selected?'active planned':'')} style={{stroke:vehicleColor(data,r.vehicle)}} d={pathData(line)}/>{progress>0&&<path className={'d-route '+(r.vehicle===selected?'active':'')} style={{stroke:vehicleColor(data,r.vehicle)}} d={pathData(polylinePrefix(line,progress))} markerEnd={r.vehicle===selected?'url(#route-direction)':undefined}/>}</g>;}))}
          {data.edges.filter(r=>r.status==='blocked'||r.status==='congested').map(r=><path key={'traffic'+r.source+r.target} className={'d-traffic-overlay '+r.status} d={pathData(geometry.get(r.source+'|'+r.target)!)}/>)}
          {data.nodes.filter(n=>n.type!=='junction'&&(showPool||n.type!=='customer'||deliveries.has(n.id))).map(n=>{const [x,y]=view.points.get(n.id)!,delivery=deliveries.get(n.id);return <g key={n.id} className={'d-map-node '+n.type+(delivery?' assigned':' pool')+(node===n.id?' selected':'')+(delivery&&delivery.done===delivery.count?' served':'')} transform={`translate(${x} ${y})`} role="button" tabIndex={0} aria-label={`${n.id} ${n.type==='warehouse'?'仓库':n.type==='transfer'?'中转站':'候选配送点'}`} onClick={()=>chooseNode(n.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseNode(n.id);}}}>
            <title>{n.id} · {n.name??''}{delivery?` · 签收 ${delivery.done}/${delivery.count}`:' · 尚未分配订单'}</title>
            <g transform={`scale(${1/view.zoom})`}><circle r="18" style={{fill:"transparent",stroke:"none"}}/>{n.type==='warehouse'?<><rect x="-16" y="-16" width="32" height="32" rx="8"/><path d="m-8-3 8-6 8 6v10H-8zM-3 7V1h6v6"/></>:n.type==='transfer'?<><path className="hub-shape" d="M0-18 18 0 0 18-18 0Z"/><path d="M-7-5H7V5H-7zM-7-1H7M0-5V5"/></>:<><circle className="d-stop-dot" r={delivery?9:5}/>{delivery&&<circle className="d-stop-ring" r="14"/>}</>}
            {(n.type!=='customer'||delivery||node===n.id)&&<text x="0" y={n.type==='customer'?-21:-27} textAnchor="middle">{n.id}{delivery?` · ${delivery.count}单`:''}</text>}
            </g></g>;})}
          {data.vehicles.map((v,index)=>{const [x,y]=vehiclePoint(v,visualClock,view.points,v.current?.kind==='drive'?geometry.get(v.current.source+'|'+v.current.target):undefined);const offset=index%2===0?18:-18;return <g key={v.id} transform={`translate(${x} ${y})`} className={'d-map-car '+(v.current?.kind??'idle')+(clock!==null?' animating':'')} data-vehicle={v.id} data-progress={v.current?.kind==='drive'?driveFraction(v.current,visualClock):0} role="button" tabIndex={0} aria-label={`地图选择 ${v.id}`} onClick={()=>onVehicle(v.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onVehicle(v.id);}}}><g transform={`scale(${1/view.zoom})`}><circle className="d-car-halo" r="20" fill="none" stroke={vehicleColor(data,v.id)}/><circle r="6" fill={vehicleColor(data,v.id)} stroke="white" strokeWidth="2"/><path d={`M0,0 L12,${offset}`} stroke={vehicleColor(data,v.id)}/><rect x="12" y={offset-12} width={v.id.length*8+20} height="24" rx="6" fill={vehicleColor(data,v.id)}/><text x="22" y={offset+4}>{v.id}</text><title>{v.id} · 最近到达 {v.position}</title></g></g>;})}
        </g>
      </svg>
      <div className="d-map-tools" aria-label="地图视口控制"><button aria-label="放大地图" onClick={()=>view.zoomBy(.5)} disabled={view.zoom>=8}>＋</button><span>{Math.round(view.zoom*100)}%</span><button aria-label="缩小地图" onClick={()=>view.zoomBy(-.5)} disabled={view.zoom<=1}>−</button><button aria-label="重置地图视口" onClick={view.reset}>适配</button><button aria-label="定位选中车辆" onClick={()=>view.focus(data.vehicles.find(v=>v.id===selected)?.position??'')}><Icon name="pin" size={18}/></button></div>
      {info&&<div className="d-map-info" role="status"><span>{info}</span>{chosenNode?.type==='customer'&&onCandidate&&<button onClick={()=>onCandidate(chosenNode.id)}>在此新增订单</button>}<button aria-label="关闭地图详情" onClick={()=>{setNode('');setEdge('');}}>×</button></div>}
    </div>
    <div className="d-map-legend"><label className="d-road-toggle"><input type="checkbox" checked={showRoads} onChange={e=>setShowRoads(e.target.checked)}/>道路底图</label>{data.map&&<label className="d-road-toggle"><input type="checkbox" checked={showPool} onChange={e=>setShowPool(e.target.checked)}/>候选地点</label>}<span><i className="warehouse"/>模拟仓库</span><span><i className="hub"/>模拟中转站</span><span><i className="customer"/>候选点</span><span>━ 已行驶 / ┄ 计划</span><span className="d-muted">{data.map?<><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL</a> · 离线道路快照</>:'示意坐标 · 动画非 GPS'}</span></div>
  </section>;
}
