import {useEffect,useRef,useState} from 'react';
import type {Workspace,WindowMode} from './types';
import {windowEvidenceCurrent} from './windows.mjs';
import {rejectionContext} from './planning-insights.mjs';
import {useDispatchSession} from './hooks/useDispatchSession';
import {useAutoTraffic} from './hooks/useAutoTraffic';
import {AppShell,workspaces} from './components/AppShell';
import {ConfirmDialog,Empty,type Confirmation} from './components/Common';
import {KPIStrip,DispatchToolbar,PlanCoverage} from './components/Operations';
import {NetworkCanvas} from './components/NetworkCanvas';
import {FleetList,VehicleInspector} from './components/Fleet';
import {DemoPlayback} from './components/DemoPlayback';
import {GlobalPlaybackControl,SimulationClock} from './components/GlobalPlaybackControl';
import {OrderTable,AddOrder} from './components/OrderTable';
import {MapWorkbench} from './components/MapWorkbench';
import {TimeWindowPanel} from './components/TimeWindows';
import {RouteChangesPanel} from './components/RouteChanges';
import {EconomicsPanel} from './components/Economics';
import {ControlledExperiment} from './components/ControlledExperiment';
import {InventoryPanel,TrafficPanel,ObjectiveComparison,EventHistory} from './components/TaskPanels';
import {RoadDashboard,FleetStage,OrderDispatchBoard} from './components/WorkspaceDashboards';
import './dashboard.css';
import {latestTrafficRoad} from './map-state.mjs';

export function DispatchDashboard({singleVehicle=false}:{singleVehicle?:boolean}){
  const session=useDispatchSession(singleVehicle),data=session.snapshot;
  const autoTraffic=useAutoTraffic(data,session.connection,session.busy,session.command);
  const [workspace,setWorkspace]=useState<Workspace>('overview'),[seed,setSeed]=useState(''),[objective,setObjective]=useState('cost');
  const lastWorkspace=useRef<Workspace>('fleet');
  const [selected,setSelected]=useState(''),[road,setRoad]=useState(''),[confirmation,setConfirmation]=useState<Confirmation|null>(null);
  const [mapView,setMapView]=useState('global');
  const [destination,setDestination]=useState('');
  const [orderFocus,setOrderFocus]=useState<{id:string;request:number;sessionId:string}|null>(null);
  const [mapFocusRequest,setMapFocusRequest]=useState(0);
  const [trafficFocusRequest,setTrafficFocusRequest]=useState(0);
  const focusOrder=(id:string)=>setOrderFocus(previous=>({id,request:(previous?.request??0)+1,sessionId:data?.id??''}));
  useEffect(()=>setOrderFocus(null),[data?.id]);
  useEffect(()=>setMapView('global'),[data?.id]);
  useEffect(()=>{const id=session.routeChanges?.addedOrderIds[0];const order=data?.orders.find(o=>o.id===id);if(order)focusOrder(order.destination);},[data?.id,session.routeChanges?.baselineRevision]);
  const [routeView,setRouteView]=useState<'before'|'after'|'changes'>('after');
  // Every applied plan opens on the live route. Historical overlays are opt-in.
  useEffect(()=>setRouteView('after'),[data?.id,session.routeChanges?.baselineRevision,session.routeChanges?.appliedRevision]);
  const [windowMode,setWindowMode]=useState<WindowMode>('rush'),[showRelaxed,setShowRelaxed]=useState(false);
  useEffect(()=>setShowRelaxed(false),[data?.id]);
  useEffect(()=>{
    const read=()=>{const value=window.location.hash.slice(1);if(workspaces.some(w=>w.id===value)){setWorkspace(value as Workspace);if(value!=='overview')lastWorkspace.current=value as Workspace;}};
    read();window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);
  },[]);
  useEffect(()=>{if(data&&!data.vehicles.some(v=>v.id===selected))setSelected(data.vehicles[0]?.id??'');},[data,selected]);
  function navigate(value:Workspace){if(value!=='overview')lastWorkspace.current=value;setWorkspace(value);window.history.replaceState(null,'','#'+value);}
  function create(){
    const run=()=>{void session.create(seed,windowMode).then(success=>{if(success){navigate('overview');setRoad('');}});};
    if(!data)run();else setConfirmation({title:'切换到新场景？',description:'当前工作区将切换到新会话，自动推进会停止。当前会话在后端的物理记录不会被改写。',confirm:'创建并切换',action:run});
  }
  const disabled=!!session.busy||session.connection!=='connected';
  const createDisabled=!!session.busy||session.connection==='failed'||session.connection==='connecting';
  const car=data?.vehicles.find(v=>v.id===selected)??data?.vehicles[0];
  const selectVehicleView=(id:string)=>{setSelected(id);setMapView(id);};
  const recentRoad=data?latestTrafficRoad(data)?.road:null;
  const mapTrafficRoad=road||(recentRoad?recentRoad.source+'|'+recentRoad.target:'');
  const map=data&&car?<NetworkCanvas key={data.id} data={data} orderFocus={orderFocus?.sessionId===data.id?orderFocus:null} changes={session.routeChanges} routeView={routeView} selected={car.id} viewMode={mapView} onViewMode={setMapView} clock={session.motionClock} showRelaxed={showRelaxed&&windowEvidenceCurrent(data)} onVehicle={selectVehicleView} onCandidate={id=>{session.setPlaying(false);setDestination(id);}} onRoad={r=>{setRoad(r.source+'|'+r.target);setTrafficFocusRequest(n=>n+1);}} onCancelOrder={id=>setConfirmation({title:`移除订单 ${id}？`,description:'已装车货物随车返回所属站点；已进入动作先完成，然后自动重规划。',confirm:'确认移除',action:()=>void session.command('remove',{id})})}/>:null;
  const playback=data?<DemoPlayback data={data} playing={session.playing} busy={session.busy} clock={session.motionClock} speed={session.speed} setSpeed={session.setSpeed} toggle={session.togglePlayback}/>:null;
  const transportControl=<GlobalPlaybackControl data={data} playing={session.playing} busy={session.busy} connected={session.connection==='connected'} objective={objective} toggle={session.togglePlayback} plan={()=>session.command('plan',{objective})}/>;
  const inspector=data&&car?<VehicleInspector data={data} car={car}/>:null;
  const changeNotice=data?.rejected_proposal?`${data.id}:rejected:${data.rejected_proposal.input_revision}`:session.routeChanges?`${data?.id}:${session.routeChanges.baselineRevision}:${session.routeChanges.appliedRevision}`:data&&rejectionContext(data).items.length?`${data.id}:rejections:${rejectionContext(data).revision}`:'';
  if(workspace==='overview'&&data)return <><MapWorkbench mapFocusRequest={mapFocusRequest} trafficFocusRequest={trafficFocusRequest} changeKey={changeNotice} changes={<RouteChangesPanel data={data} changes={session.routeChanges} view={routeView} setView={v=>{setRouteView(v);setMapFocusRequest(n=>n+1);}} busy={disabled} onOrder={id=>{focusOrder(id);setMapFocusRequest(n=>n+1);}} onPlan={()=>void session.command('plan',{objective})} onVehicle={setSelected}/>} data={data} simulationTime={session.motionClock??data.now} map={map} playback={playback} transportControl={transportControl}
    traffic={<TrafficPanel data={data} road={mapTrafficRoad} setRoad={setRoad} busy={disabled} command={session.command} confirm={setConfirmation} autoTraffic={autoTraffic}/>}
    economics={<EconomicsPanel key={data.id} data={data} busy={disabled} error={session.error} onTrial={async p=>{const ok=await session.trial(p);if(ok)setObjective('cost');return ok;}} onCreate={create}/>}
    windows={<TimeWindowPanel data={data} showRelaxed={showRelaxed} setShowRelaxed={setShowRelaxed} onVehicle={setSelected} selected={car?.id??''}/>} windowMode={windowMode} setWindowMode={setWindowMode}
    toolbar={<DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/>}
    orders={<OrderTable seed={seed} data={data} busy={disabled} command={session.command} confirm={setConfirmation} error={session.error}/>}
    fleet={<FleetList data={data} selected={car?.id??''} onSelect={selectVehicleView} compact/>} inspector={inspector}
    seed={seed} setSeed={setSeed} create={create} disabled={createDisabled} viewMode={mapView} onViewMode={setMapView} onVehicle={selectVehicleView} navigate={navigate} exitMap={()=>navigate(lastWorkspace.current)} error={session.error} message={session.message} reconnect={session.reconnect} pausePlayback={()=>session.setPlaying(false)}/>
    <div className="dispatch"><ConfirmDialog value={confirmation} close={()=>setConfirmation(null)}/>{destination&&<AddOrder data={data} busy={disabled} command={session.command} close={()=>setDestination('')} error={session.error} destination={destination}/>}</div></>;
  return <AppShell workspace={workspace} onWorkspace={navigate} connection={session.connection} data={data} reconnect={session.reconnect} singleVehicle={singleVehicle}
    headerActions={<>{data&&<SimulationClock minutes={session.motionClock??data.now}/>}{transportControl}<div className="d-scene-controls"><label className="d-sr-only" htmlFor="scene-seed">场景 Seed</label><input id="scene-seed" type="number" step="1" placeholder="Seed · 默认配置" value={seed} onChange={e=>setSeed(e.target.value)}/><button disabled={createDisabled} onClick={create}>{session.busy==='create'?'创建中…':'新建场景'}</button></div></>}>
    {session.error&&<div className="d-error-banner" role="alert"><b>操作未完成</b><span>{session.error}</span><button onClick={session.reconnect}>重试连接</button></div>}
    {session.connection==='missing'&&<p className="d-inline-warn">显示的是上次会话快照，当前会话已不存在；请使用“新建场景”恢复。</p>}
    {data?.studio&&data.studio.variant!=='heavy_slow_roads'&&<p className="d-inline-warn">当前会话使用旧重量和路速。新建场景后可体验 20/30 kg 大件订单和校内慢速路；原会话记录仍保留。</p>}
    {!data?<div className="d-card d-welcome"><Empty title={singleVehicle?'创建单车配送场景':'创建你的第一个配送场景'}>{singleVehicle?'一辆车从仓库装货，直接配送到客户，完成后返回仓库。':'在一张地图上掌握干线补货、站点配送和逐单签收。创建后可规划并查看逐单按时或超时结果。'}</Empty><button className="d-primary" disabled={createDisabled} onClick={create}>{session.busy?'正在创建…':singleVehicle?'创建单车场景':'创建配送场景'}</button><p className="d-muted">{session.connection==='connected'?'也可以在顶部指定 Seed，复现相同场景。':'请先连接后端，再创建场景。'}</p></div>:<>
      {workspace==='overview'&&<><KPIStrip data={data}/>{playback}<DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/><div className="d-overview-grid">{map}{inspector}</div><FleetList data={data} selected={car?.id??''} onSelect={setSelected} compact/><PlanCoverage data={data}/></>}
      {workspace==='fleet'&&<><FleetStage data={data} clock={session.motionClock??data.now} selected={car?.id??''} onSelect={setSelected}/>{playback}<DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/><FleetList data={data} selected={car?.id??''} onSelect={setSelected}/><div className="d-fleet-workspace">{map}{inspector}</div></>}
      {workspace==='orders'&&<><OrderDispatchBoard data={data}/><OrderTable seed={seed} data={data} busy={disabled} command={session.command} confirm={setConfirmation} error={session.error}/></>}
      {workspace==='inventory'&&<InventoryPanel data={data}/>}
      {workspace==='traffic'&&<><RoadDashboard data={data} onRoad={setRoad}/><div className="d-traffic-workspace">{map}<TrafficPanel data={data} road={road} setRoad={setRoad} busy={disabled} command={session.command} confirm={setConfirmation} autoTraffic={autoTraffic}/></div><div className="d-lower-toolbar"><DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/></div></>}
      {workspace==='audit'&&<div className="d-audit-workspace">{!data.single_vehicle&&<ControlledExperiment/>}<ObjectiveComparison data={data} comparison={session.connection==='connected'?session.comparison:null} busy={disabled} command={session.command}/><EventHistory data={data}/></div>}
    </>}
    {session.message&&!session.error&&<div className="d-toast" role="status"><span>✓</span>{session.message}</div>}
    <ConfirmDialog value={confirmation} close={()=>setConfirmation(null)}/>
    {data&&destination&&<AddOrder data={data} busy={disabled} command={session.command} close={()=>setDestination('')} error={session.error} destination={destination}/>}
  </AppShell>;
}
