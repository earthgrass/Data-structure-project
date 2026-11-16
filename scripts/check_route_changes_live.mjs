/** Optional running-API acceptance, deliberately outside the offline test suite.
 * node scripts/check_route_changes_live.mjs [base URL] [new evidence filename]
 * Creates its own session; never modifies the dashboard's existing session.
 */
import assert from 'node:assert/strict';
import {writeFile,access} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {advanceRouteChanges,summarizeRouteChanges} from '../frontend/src/dispatch/routeChanges.mjs';

const base=(process.argv[2]??'http://127.0.0.1:8001').replace(/\/$/,'');
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const target=resolve(root,'docs/experiments',process.argv[3]??'route-changes-live.json');
try{await access(target);throw new Error('existing evidence preserved; select a new filename');}
catch(error){if(error.code!=='ENOENT')throw error;}
const started=performance.now();let assertions=0;
function check(value,message){assert.ok(value,message);assertions++;}
async function api(path,body){
 const response=await fetch(base+'/api/v2'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},
  ...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(180000)});
 const result=await response.json();assert.equal(response.status,200,JSON.stringify(result));assertions++;
 return result;
}
const created=await api('/sessions',{profile:'bjut-studio',seed:42,window_mode:'relaxed'});
const commands='/sessions/'+created.id+'/commands';
const initial=await api(commands,{revision:created.revision,command:'plan',objective:'distance'});
check(initial.plan.report.valid&&initial.plan.report.complete_all,'initial independent plan report');
check(advanceRouteChanges(null,created,initial)===null,'first planning has no invented baseline');
const existingDestinations=new Set(initial.orders.map(o=>o.destination));
const drivenNodes=new Set(initial.plan.routes.flatMap(r=>r.actions.filter(a=>a.kind==='drive').flatMap(a=>[a.source,a.target])));
// An unused order destination may already be passed through by an existing route.
// Select an actually unvisited candidate to exercise geometric added-edge styling.
const destination=initial.nodes.find(n=>n.type==='customer'&&!existingDestinations.has(n.id)&&!drivenNodes.has(n.id));
check(!!destination,'real candidate outside initial driven nodes exists');
let deadline=0;for(const o of initial.orders)if(o.deadline>deadline)deadline=o.deadline;
const urgent={id:'LIVE_URGENT_01',destination:destination.id,demand:'1',earliest:initial.now,deadline,priority:'urgent'};
const added=await api(commands,{revision:initial.revision,command:'add',...urgent});
let changes=advanceRouteChanges(null,initial,added);
const pending=summarizeRouteChanges(changes,added);
check(pending.status==='pending','added order waits for real plan');
check(pending.addedOrderIds.length===1&&pending.addedOrderIds[0]===urgent.id,'exact new order identity');
check(added.orders.length===initial.orders.length+1,'no existing order replaced');
check(added.orders.find(o=>o.id===urgent.id).status==='pending','new order is not prematurely accepted');
check(added.plan.fingerprint===initial.plan.fingerprint,'add does not invent a new route');
const applied=await api(commands,{revision:added.revision,command:'plan',objective:'distance'});
changes=advanceRouteChanges(changes,added,applied);
const compared=summarizeRouteChanges(changes,applied);
check(applied.plan.report.valid&&applied.plan.report.safe_to_apply,'independent replanning report valid and safe');
check(applied.plan.report.complete_all,'actual replanning covers all 25 orders');
check(applied.plan.accepted.includes(urgent.id),'urgent order actually accepted by backend');
check(compared.status==='compared'&&compared.baselineRevision===initial.revision,'pre-add baseline retained');
check(compared.changedVehicleIds.length>0,'real changed vehicle detected');
check(compared.vehicleChanges.some(v=>v.afterServiceIds.includes(urgent.id)),'new order appears in real service order');
check(compared.vehicleChanges.some(v=>v.addedEdges.length>0),'unused destination creates real new directed edges');
const actualEdges=new Set(applied.edges.map(e=>JSON.stringify([e.source,e.target])));
for(const v of compared.vehicleChanges)for(const e of [...v.beforeEdges,...v.afterEdges]){
 check(actualEdges.has(JSON.stringify([e.source,e.target])),'every drawn comparison edge exists in real directed graph');
}
const polled=await api('/sessions/'+created.id);
check(JSON.stringify(summarizeRouteChanges(advanceRouteChanges(changes,applied,polled),polled))===JSON.stringify(compared),'poll preserves exact comparison');
const departed=await api(commands,{revision:polled.revision,command:'depart'});
const stepped=await api(commands,{revision:departed.revision,command:'step'});
check(JSON.stringify(summarizeRouteChanges(advanceRouteChanges(changes,departed,stepped),stepped))===JSON.stringify(compared),'real physical step preserves historical comparison');
check(stepped.audit.valid,'first physical step passes independent history audit');
const snapshot=s=>({id:s.id,revision:s.revision,now:s.now,traffic_version:s.traffic_version,orders:s.orders,vehicles:s.vehicles,plan:s.plan,audit:s.audit});
const evidence={scope:'isolated live API session; real generator, original planner and independent validator; no mock responses',
 request:{profile:'bjut-studio',seed:42,window_mode:'relaxed',objective:'distance',urgent},
 initial:snapshot(initial),added:snapshot(added),applied:snapshot(applied),stepped:snapshot(stepped),pending,compared,
 assertions,runtime_seconds:(performance.now()-started)/1000};
await writeFile(target,JSON.stringify(evidence,null,2)+'\n',{encoding:'utf8',flag:'wx'});
console.log(JSON.stringify({session:created.id,assertions,accepted:applied.plan.accepted.length,changedVehicles:compared.changedVehicleIds,
 addedDirectionEdges:compared.vehicleChanges.reduce((sum,v)=>sum+v.addedEdges.length,0),
 removedDirectionEdges:compared.vehicleChanges.reduce((sum,v)=>sum+v.removedEdges.length,0),runtime_seconds:evidence.runtime_seconds,output:target}));
