/** Local visual evidence only; never chooses routes or changes a backend snapshot. */
function planKey(plan){
 return plan?JSON.stringify([plan.fingerprint,plan.revision,plan.traffic_version,plan.objective]):null;
}
function actionKey(a){
 return JSON.stringify([a.vehicle,a.kind,a.source,a.target,a.start,a.end,a.ids,a.batch,a.traffic_version]);
}
function completedKeys(snapshot){
 return new Set(snapshot.events.filter(e=>e.kind==='action'&&e.action).map(e=>actionKey(e.action)));
}
function copyRemaining(plan,snapshot){
 if(!plan)return null;
 const done=completedKeys(snapshot);
 return {...plan,accepted:[...plan.accepted],deferred:plan.deferred.map(row=>[...row]),
  routes:plan.routes.map(r=>({...r,actions:r.actions.filter(a=>!done.has(actionKey(a))).map(a=>({...a,ids:[...a.ids]}))}))};
}
function orderFacts(snapshot){
 return snapshot.orders.map(o=>({id:o.id,priority:o.priority,status:o.status}));
}
function orderDelta(oldOrders,newOrders){
 const old=new Map(oldOrders.map(o=>[o.id,o])),current=new Map(newOrders.map(o=>[o.id,o]));
 const addedOrderIds=[],cancelledOrderIds=[],priorityOrderIds=[];
 for(const o of newOrders){
  const p=old.get(o.id);
  if(!p)addedOrderIds.push(o.id);
  if((o.status==='cancelled'||o.status==='expired')&&p?.status!==o.status)cancelledOrderIds.push(o.id);
  if(p&&p.priority!==o.priority)priorityOrderIds.push(o.id);
 }
 for(const o of oldOrders)if(!current.has(o.id))cancelledOrderIds.push(o.id);
 return {addedOrderIds,cancelledOrderIds,priorityOrderIds};
}
function hasMutation(before,after){
 const delta=orderDelta(before.orders,after.orders);
 return before.traffic_version!==after.traffic_version||Object.values(delta).some(ids=>ids.length);
}

/** Capture pre-change evidence, preserving it until a real new plan is applied.
 * Time/Space O(orders) to inspect each snapshot; O(orders + actions + events)
 * when copying plan evidence. Steps never replace a baseline.
 * Completion is proven by actual action events, never inferred from the clock.
 */
export function advanceRouteChanges(previous,before,after){
 if(!before||before.id!==after.id)return null;
 if(after.revision<before.revision||previous?.sessionId===after.id&&after.revision<previous.observedRevision)return previous;
 const oldKey=planKey(before.plan),newKey=planKey(after.plan),planChanged=!!after.plan&&oldKey!==newKey;
 const mutation=hasMutation(before,after);
 let next=previous?.sessionId===after.id?previous:null;
 if((mutation||planChanged&&before.plan)&&(!next||next.status==='compared')){
  next={sessionId:after.id,status:'pending',baselineRevision:before.revision,baselineNow:before.now,
   baselinePlan:copyRemaining(before.plan,before),baselinePlanKey:oldKey,baselineOrders:orderFacts(before),
   baselineTrafficVersion:before.traffic_version,observedRevision:after.revision,
   appliedRevision:null,appliedAt:null,appliedPlan:null,appliedOrders:null,appliedTrafficVersion:null};
 }
 if(!next)return null;
 if(next.status==='pending'&&planChanged){
  // Includes actions completed at the checkpoint before an automatic traffic replan.
  return {...next,status:'compared',baselinePlan:copyRemaining(next.baselinePlan,after),
   appliedPlan:copyRemaining(after.plan,after),appliedOrders:orderFacts(after),
   appliedTrafficVersion:after.traffic_version,appliedRevision:after.revision,appliedAt:after.now,
   observedRevision:after.revision};
 }
 return next.observedRevision===after.revision?next:{...next,observedRevision:after.revision};
}

function edges(actions){
 const result=[],seen=new Set();
 for(const a of actions)if(a.kind==='drive'){
  const key=JSON.stringify([a.source,a.target]);
  if(!seen.has(key)){seen.add(key);result.push({source:a.source,target:a.target});}
 }
 return result;
}
function services(actions){return actions.filter(a=>a.kind==='deliver').flatMap(a=>a.ids);}
function routeStructure(actions){
 return JSON.stringify(actions.filter(a=>a.kind!=='wait'&&a.kind!=='finish').map(a=>[a.kind,a.source,a.target,a.ids]));
}
function serviceTiming(actions){return JSON.stringify(actions.filter(a=>a.kind==='deliver').map(a=>[a.ids,a.start,a.end]));}

/** Per-vehicle directed-edge sets plus ordered service IDs; O(N+A+E), no sorting.
 * Compared evidence freezes at plan application, so ordinary animation progress
 * cannot manufacture removed roads. An initial plan without a baseline has no diff.
 */
export function summarizeRouteChanges(state,snapshot){
 if(!state||state.sessionId!==snapshot.id)return null;
 const compared=state.status==='compared',hasBaseline=!!state.baselinePlan;
 const baseline=compared?state.baselinePlan:copyRemaining(state.baselinePlan,snapshot);
 const current=compared?state.appliedPlan:null;
 const oldRoutes=new Map((baseline?.routes??[]).map(r=>[r.vehicle,r]));
 const newRoutes=new Map((current?.routes??[]).map(r=>[r.vehicle,r]));
 const vehicleIds=[...oldRoutes.keys()];
 for(const id of newRoutes.keys())if(!oldRoutes.has(id))vehicleIds.push(id);
 const vehicleChanges=vehicleIds.map(vehicle=>{
  const oldActions=oldRoutes.get(vehicle)?.actions??[],newActions=newRoutes.get(vehicle)?.actions??[];
  const beforeEdges=edges(oldActions),afterEdges=edges(newActions);
  const oldSet=new Set(beforeEdges.map(e=>JSON.stringify([e.source,e.target]))),newSet=new Set(afterEdges.map(e=>JSON.stringify([e.source,e.target])));
  const meaningful=compared&&hasBaseline;
  const addedEdges=meaningful?afterEdges.filter(e=>!oldSet.has(JSON.stringify([e.source,e.target]))):[];
  const removedEdges=meaningful?beforeEdges.filter(e=>!newSet.has(JSON.stringify([e.source,e.target]))):[];
  const unchangedEdges=meaningful?afterEdges.filter(e=>oldSet.has(JSON.stringify([e.source,e.target]))):afterEdges;
  const timingChanged=meaningful&&serviceTiming(oldActions)!==serviceTiming(newActions);
  return {vehicle,beforeEdges,afterEdges,addedEdges,removedEdges,unchangedEdges,
   beforeServiceIds:services(oldActions),afterServiceIds:services(newActions),timingChanged,
   changed:meaningful&&(routeStructure(oldActions)!==routeStructure(newActions)||timingChanged)};
 });
 const delta=orderDelta(state.baselineOrders,compared?state.appliedOrders:snapshot.orders);
 return {...delta,sessionId:state.sessionId,status:state.status,hasBaseline,
  baselineRevision:state.baselineRevision,baselineNow:state.baselineNow,
  appliedRevision:state.appliedRevision,appliedAt:state.appliedAt,
  trafficChanged:state.baselineTrafficVersion!==(compared?state.appliedTrafficVersion:snapshot.traffic_version),
  changedVehicleIds:vehicleChanges.filter(v=>v.changed).map(v=>v.vehicle),vehicleChanges};
}
