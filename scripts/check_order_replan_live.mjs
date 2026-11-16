/** Real checkpoint/order workflow acceptance. Never uses a browser-owned session.
 * node scripts/check_order_replan_live.mjs [base URL] [new evidence filename]
 * Full phase snapshots retain graph, orders, plans and events. Every request is
 * recorded; ordinary execution steps retain a compact response plus final history.
 */
import assert from 'node:assert/strict';
import {access,writeFile} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync,gunzipSync} from 'node:zlib';
import {advanceRouteChanges,summarizeRouteChanges} from '../frontend/src/dispatch/routeChanges.mjs';
import {groupMapOrders} from '../frontend/src/dispatch/order-map.mjs';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const base=(process.argv[2]??'http://127.0.0.1:8001').replace(/\/$/,'');
const output=resolve(root,'docs/experiments',process.argv[3]??'order-replan-live.json.gz');
try{await access(output);throw new Error('existing evidence preserved; choose a new filename');}
catch(error){if(error.code!=='ENOENT')throw error;}
let assertions=0;
const started=performance.now();
const evidence={scope:'real isolated HTTP sessions, original planner and independent history validator; no mock output',attempts:[]};
function check(value,message){assert.ok(value,message);assertions++;}
function same(a,b,message){assert.deepEqual(a,b,message);assertions++;}
function actionKey(a){return JSON.stringify([a.vehicle,a.kind,a.source,a.target,a.start,a.end,a.ids,a.batch,a.traffic_version]);}
function cargo(s){return s.vehicles.map(v=>({id:v.id,cargo:v.cargo,load:v.load}));}
function positions(s){return s.vehicles.map(v=>({id:v.id,position:v.position}));}
function compact(s){return {id:s.id,revision:s.revision,now:s.now,running:s.running,ready:s.ready,needs_replan:s.needs_replan,order_control:s.order_control,
 vehicles:s.vehicles,orders:s.orders,audit:s.audit,plan_report:s.plan?.report,plan_fingerprint:s.plan?.fingerprint,event_count:s.events?.length};}
function delta(summary){return {changed_vehicles:summary?.changedVehicleIds??[],
 added_directed_edges:summary?.vehicleChanges.reduce((sum,v)=>sum+v.addedEdges.length,0)??0,
 removed_directed_edges:summary?.vehicleChanges.reduce((sum,v)=>sum+v.removedEdges.length,0)??0};}

async function experiment(mode){
 const attempt={mode,requests:[],snapshots:{},comparisons:{},outcome:null};evidence.attempts.push(attempt);
 let current=null,comparisonState=null;
 async function api(label,path,body){
  const entry={label,path,method:body?'POST':'GET',request:body??null};attempt.requests.push(entry);
  const began=performance.now();
  try{
   const response=await fetch(base+'/api/v2'+path,{method:entry.method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(180000)});
   const result=await response.json();entry.status=response.status;entry.runtime_seconds=(performance.now()-began)/1000;
   entry.response=response.ok?compact(result):result;
   check(response.status===200,`${mode} ${label}: HTTP ${response.status} ${response.ok?'':JSON.stringify(result)}`);
   return result;
  }catch(error){entry.error={name:error.name,message:error.message};throw error;}
 }
 async function command(label,kind,fields={}){
  const before=current;
  current=await api(label,'/sessions/'+before.id+'/commands',{revision:before.revision,command:kind,...fields});
  comparisonState=advanceRouteChanges(comparisonState,before,current);
  return current;
 }
 function save(name){attempt.snapshots[name]=current;return current;}
 async function drain(label){
  const entered=new Set(current.vehicles.filter(v=>v.current).map(v=>actionKey(v.current)));
  let steps=0;
  while(current.order_control.status==='waiting_checkpoint'&&current.running){
   check(steps<entered.size+1,`${label}: checkpoint drain bounded by already-entered actions`);
   const before=current;await command(label+'-step-'+(++steps),'step');
   check(current.audit.valid,`${label}: real checkpoint history is valid`);
   for(const v of current.vehicles)if(v.current)check(entered.has(actionKey(v.current)),`${label}: no successor action entered while pausing`);
   if(current.order_control.status==='waiting_checkpoint')same(current.plan.fingerprint,before.plan.fingerprint,`${label}: old plan remains evidence while waiting`);
  }
  check(['applied','blocked'].includes(current.order_control.status),`${label}: explicit terminal workflow status`);
  check(!current.running,`${label}: no automatic departure`);
  attempt[label+'_checkpoint_steps']=steps;
 }
 try{
  current=await api('create','/sessions',{profile:'bjut-studio',seed:42,window_mode:mode,auto_replan:true});save('created');
  check(current.order_control.enabled,`${mode}: backend workflow enabled`);
  await command('initial-plan','plan',{objective:'distance'});const initial=save('initial_plan');
  check(initial.plan.report.valid&&initial.plan.report.safe_to_apply&&initial.plan.report.complete_all,`${mode}: independently complete initial plan`);
  await command('depart','depart');
  const bound=initial.plan.routes.reduce((sum,r)=>sum+r.actions.length,0)+initial.vehicles.length+1;
  let beforeDriveSteps=0;
  while(!current.vehicles.some(v=>v.current?.kind==='drive')){
   check(current.running&&beforeDriveSteps<bound,`${mode}: actual first drive reachable`);
   await command('to-first-drive-'+(++beforeDriveSteps),'step');
  }
  const moving=save('moving_before_add');attempt.steps_to_first_drive=beforeDriveSteps;
  const driven=new Set(initial.plan.routes.flatMap(r=>r.actions.filter(a=>a.kind==='drive').flatMap(a=>[a.source,a.target])));
  const candidates=initial.nodes.filter(n=>n.type==='customer'&&!driven.has(n.id));
  const candidate=candidates.find(n=>n.id==='P27')??candidates[0];
  check(!!candidate,`${mode}: genuine candidate outside initial driven geometry`);
  const urgent={id:'LIVE_MOVING_URGENT',destination:candidate.id,demand:'1',earliest:moving.now,deadline:moving.now+2000,priority:'urgent',auto_replan:true};
  attempt.urgent_input=urgent;
  await command('add-while-driving','add',urgent);save('add_waiting');
  same(positions(current),positions(moving),`${mode}: insertion does not teleport vehicles`);
  same(cargo(current),cargo(moving),`${mode}: insertion does not reset exact cargo strings`);
  same(current.order_control.order_version,moving.order_control.order_version+1,`${mode}: successful input version advances once`);
  same(current.order_control.status,'waiting_checkpoint',`${mode}: entered drive waits for checkpoint`);
  same(current.plan.fingerprint,moving.plan.fingerprint,`${mode}: insertion retains old plan until checkpoint`);
  const newOrder=current.orders.find(o=>o.id===urgent.id);
  same(newOrder.location,['warehouse','W1'],`${mode}: new cargo remains at its actual warehouse`);
  same(newOrder.status,'pending',`${mode}: mutation does not fake acceptance`);
  await drain('add');save('after_add_replan');
  same(cargo(current),cargo(moving),`${mode}: draining the first entered drive preserves carried orders`);
  attempt.comparisons.add=summarizeRouteChanges(comparisonState,current);
  attempt.add_result={status:current.order_control.status,accepted:!!current.plan?.accepted.includes(urgent.id),deferred:current.plan?.deferred.find(([id])=>id===urgent.id)??null,...delta(attempt.comparisons.add)};
  if(current.order_control.status==='applied'){
   check(current.ready&&current.plan.report.valid&&current.plan.report.safe_to_apply,`${mode}: applied auto plan independently safe and waiting`);
   same(current.order_control.planned_order_version,current.order_control.order_version,`${mode}: accepted plan binds latest order input`);
  }else{
   same(current.plan.fingerprint,moving.plan.fingerprint,`${mode}: blocked workflow preserves the old plan`);
   check(!current.ready,`${mode}: unsafe continuation cannot depart`);
  }
  const beforeCancel=current,unloaded=current.orders.find(o=>o.id===urgent.id);
  check(unloaded.location[0]==='warehouse',`${mode}: only unentered warehouse cargo is cancelled`);
  await command('cancel-unloaded-urgent','cancel',{id:urgent.id,auto_replan:true});
  if(current.order_control.status==='waiting_checkpoint')await drain('cancel');
  save('after_cancel_replan');
  same(positions(current),positions(beforeCancel),`${mode}: cancellation does not move vehicles`);
  same(cargo(current),cargo(beforeCancel),`${mode}: cancellation preserves carried orders`);
  same(current.orders.find(o=>o.id===urgent.id).status,'cancelled',`${mode}: cancelled identity remains in history`);
  check(![...groupMapOrders(current.orders,[],{activeOnly:true}).values()].some(g=>g.ids.includes(urgent.id)),`${mode}: cancelled order absent from active map groups`);
  attempt.comparisons.cancel=summarizeRouteChanges(comparisonState,current);
  attempt.cancel_result={status:current.order_control.status,...delta(attempt.comparisons.cancel)};
  if(current.order_control.status==='blocked'){
   attempt.outcome='blocked_after_cancellation';return attempt;
  }
  check(current.ready&&current.plan.report.valid&&current.plan.report.safe_to_apply,`${mode}: cancelled-input continuation safe`);
  check(!current.plan.accepted.includes(urgent.id),`${mode}: cancelled identity not reassigned`);
  await command('confirm-resume','depart');
  const finalBound=current.plan.routes.reduce((sum,r)=>sum+r.actions.length,0)+current.vehicles.length+1;
  let executionSteps=0;
  while(current.running){
   check(executionSteps<finalBound,`${mode}: physical execution bounded by real plan actions`);
   await command('execute-'+(++executionSteps),'step');
   check(current.audit.valid,`${mode}: every physical action has a valid independent audit`);
  }
  save('finished');attempt.execution_steps=executionSteps;
  check(current.audit.valid&&current.audit.complete_all,`${mode}: all remaining customer orders physically signed off`);
  check(current.orders.filter(o=>o.id!==urgent.id).every(o=>o.status==='delivered'),`${mode}: each original identity delivered`);
  same(groupMapOrders(current.orders,[],{activeOnly:true}).size,0,`${mode}: terminal-only map has no active order pins`);
  same(current.orders.length,initial.orders.length+1,`${mode}: terminal identities not deleted from history`);
  attempt.delivered_count=current.orders.filter(o=>o.status==='delivered').length;
  attempt.cancelled_count=current.orders.filter(o=>o.status==='cancelled').length;
  attempt.outcome='completed';return attempt;
 }catch(error){
  attempt.outcome='error';attempt.error={name:error.name,message:error.message,stack:error.stack};
  if(current)save('last_successful_snapshot');return attempt;
 }
}

try{
 const strict=await experiment('strict');
 // A teaching comparison must retain any real strict-window limitation as evidence.
 if(strict.outcome!=='completed'||!strict.add_result?.accepted||!strict.add_result?.added_directed_edges)await experiment('relaxed');
 evidence.assertions=assertions;evidence.runtime_seconds=(performance.now()-started)/1000;
 evidence.completed=evidence.attempts.every(a=>a.outcome==='completed');
}finally{
 evidence.assertions=assertions;evidence.runtime_seconds=(performance.now()-started)/1000;
 const raw=Buffer.from(JSON.stringify(evidence,null,2)+'\n','utf8');
 const bytes=output.endsWith('.gz')?gzipSync(raw):raw;
 if(output.endsWith('.gz'))assert.ok(gunzipSync(bytes).equals(raw),'gzip preserves every evidence byte');
 await writeFile(output,bytes,{flag:'wx'});
}
console.log(JSON.stringify({output,assertions,runtime_seconds:evidence.runtime_seconds,attempts:evidence.attempts.map(a=>({mode:a.mode,outcome:a.outcome,session:a.snapshots.created?.id,add:a.add_result,cancel:a.cancel_result,delivered:a.delivered_count,cancelled:a.cancelled_count,error:a.error?.message}))},null,2));
if(evidence.attempts.some(a=>a.outcome==='error'))process.exitCode=1;
