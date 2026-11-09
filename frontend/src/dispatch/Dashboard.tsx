import {useEffect,useState} from 'react';
import type {Workspace,WindowMode} from './types';
import {windowEvidenceCurrent} from './windows.mjs';
import {useDispatchSession} from './hooks/useDispatchSession';
import {AppShell,workspaces} from './components/AppShell';
import {ConfirmDialog,Empty,type Confirmation} from './components/Common';
import {KPIStrip,DispatchToolbar,PlanCoverage} from './components/Operations';
import {NetworkCanvas} from './components/NetworkCanvas';
import {FleetList,VehicleInspector} from './components/Fleet';
import {DemoPlayback} from './components/DemoPlayback';
import {OrderTable,AddOrder} from './components/OrderTable';
import {MapWorkbench} from './components/MapWorkbench';
import {TimeWindowPanel} from './components/TimeWindows';
import {InventoryPanel,TrafficPanel,ObjectiveComparison,EventHistory} from './components/TaskPanels';
import './dashboard.css';

export function DispatchDashboard(){
  const session=useDispatchSession(),data=session.snapshot;
  const [workspace,setWorkspace]=useState<Workspace>('overview'),[seed,setSeed]=useState(''),[objective,setObjective]=useState('distance');
  const [selected,setSelected]=useState(''),[road,setRoad]=useState(''),[confirmation,setConfirmation]=useState<Confirmation|null>(null);
  const [destination,setDestination]=useState('');
  const [windowMode,setWindowMode]=useState<WindowMode>('strict'),[showRelaxed,setShowRelaxed]=useState(false);
  useEffect(()=>setShowRelaxed(false),[data?.id]);
  useEffect(()=>{
    const read=()=>{const value=window.location.hash.slice(1);if(workspaces.some(w=>w.id===value))setWorkspace(value as Workspace);};
    read();window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);
  },[]);
  useEffect(()=>{if(data&&!data.vehicles.some(v=>v.id===selected))setSelected(data.vehicles[0]?.id??'');},[data,selected]);
  function navigate(value:Workspace){setWorkspace(value);window.history.replaceState(null,'','#'+value);}
  function create(){
    const run=()=>{void session.create(seed,windowMode).then(success=>{if(success){navigate('overview');setRoad('');}});};
    if(!data)run();else setConfirmation({title:'切换到新场景？',description:'当前工作区将切换到新会话，自动推进会停止。当前会话在后端的物理记录不会被改写。',confirm:'创建并切换',action:run});
  }
  const disabled=!!session.busy||session.connection!=='connected';
  const createDisabled=!!session.busy||session.connection==='failed'||session.connection==='connecting';
  const car=data?.vehicles.find(v=>v.id===selected)??data?.vehicles[0];
  const map=data&&car?<NetworkCanvas key={data.id} data={data} selected={car.id} clock={session.motionClock} showRelaxed={showRelaxed&&windowEvidenceCurrent(data)} onVehicle={setSelected} onCandidate={id=>{session.setPlaying(false);setDestination(id);}} onRoad={r=>setRoad(r.source+'|'+r.target)}/>:null;
  const playback=data?<DemoPlayback data={data} playing={session.playing} busy={session.busy} clock={session.motionClock} speed={session.speed} setSpeed={session.setSpeed} toggle={session.togglePlayback}/>:null;
  const inspector=data&&car?<VehicleInspector data={data} car={car}/>:null;
  if(workspace==='overview'&&data)return <><MapWorkbench data={data} map={map} playback={playback}
    windows={<TimeWindowPanel data={data} showRelaxed={showRelaxed} setShowRelaxed={setShowRelaxed} onVehicle={setSelected} selected={car?.id??''}/>} windowMode={windowMode} setWindowMode={setWindowMode}
    toolbar={<DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/>}
    orders={<OrderTable seed={seed} data={data} busy={disabled} command={session.command} confirm={setConfirmation} error={session.error}/>}
    fleet={<FleetList data={data} selected={car?.id??''} onSelect={setSelected} compact/>} inspector={inspector}
    seed={seed} setSeed={setSeed} create={create} disabled={createDisabled} selected={car?.id??''} onVehicle={setSelected} navigate={navigate} error={session.error} message={session.message} reconnect={session.reconnect} pausePlayback={()=>session.setPlaying(false)}/>
    <div className="dispatch"><ConfirmDialog value={confirmation} close={()=>setConfirmation(null)}/>{destination&&<AddOrder data={data} busy={disabled} command={session.command} close={()=>setDestination('')} error={session.error} destination={destination}/>}</div></>;
  return <AppShell workspace={workspace} onWorkspace={navigate} connection={session.connection} data={data} reconnect={session.reconnect}
    headerActions={<div className="d-scene-controls"><label className="d-sr-only" htmlFor="scene-seed">场景 Seed</label><input id="scene-seed" type="number" step="1" placeholder="Seed · 默认配置" value={seed} onChange={e=>setSeed(e.target.value)}/><button disabled={createDisabled} onClick={create}>{session.busy==='create'?'创建中…':'新建场景'}</button></div>}>
    {session.error&&<div className="d-error-banner" role="alert"><b>操作未完成</b><span>{session.error}</span><button onClick={session.reconnect}>重试连接</button></div>}
    {session.connection==='missing'&&<p className="d-inline-warn">显示的是上次会话快照，当前会话已不存在；请使用“新建场景”恢复。</p>}
    {!data?<div className="d-card d-welcome"><Empty title="创建你的第一个配送场景">在一张地图上掌握干线补货、站点配送和逐单签收。系统将先验证两个目标的完整可行方案。</Empty><button className="d-primary" disabled={createDisabled} onClick={create}>{session.busy?'正在创建…':'创建配送场景'}</button><p className="d-muted">{session.connection==='connected'?'也可以在顶部指定 Seed，复现相同场景。':'请先连接后端，再创建场景。'}</p></div>:<>
      {workspace==='overview'&&<><KPIStrip data={data}/>{playback}<DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/><div className="d-overview-grid">{map}{inspector}</div><FleetList data={data} selected={car?.id??''} onSelect={setSelected} compact/><PlanCoverage data={data}/></>}
      {workspace==='fleet'&&<><FleetList data={data} selected={car?.id??''} onSelect={setSelected}/><div className="d-fleet-workspace">{map}{inspector}</div></>}
      {workspace==='orders'&&<OrderTable seed={seed} data={data} busy={disabled} command={session.command} confirm={setConfirmation} error={session.error}/>}
      {workspace==='inventory'&&<InventoryPanel data={data}/>}
      {workspace==='traffic'&&<><div className="d-traffic-workspace">{map}<TrafficPanel data={data} road={road} setRoad={setRoad} busy={disabled} command={session.command} confirm={setConfirmation}/></div><div className="d-lower-toolbar"><DispatchToolbar data={data} objective={objective} setObjective={setObjective} busy={session.busy} connection={session.connection} command={session.command} onCreate={create} onResults={()=>navigate('audit')} playing={session.playing} setPlaying={session.setPlaying}/></div></>}
      {workspace==='audit'&&<div className="d-audit-workspace"><ObjectiveComparison data={data} comparison={session.connection==='connected'?session.comparison:null} busy={disabled} command={session.command}/><EventHistory data={data}/></div>}
    </>}
    {session.message&&!session.error&&<div className="d-toast" role="status"><span>✓</span>{session.message}</div>}
    <ConfirmDialog value={confirmation} close={()=>setConfirmation(null)}/>
    {data&&destination&&<AddOrder data={data} busy={disabled} command={session.command} close={()=>setDestination('')} error={session.error} destination={destination}/>}
  </AppShell>;
}
