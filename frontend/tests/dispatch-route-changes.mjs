import assert from 'node:assert/strict';
import {advanceRouteChanges as advance,summarizeRouteChanges as summarize} from '../src/dispatch/routeChanges.mjs';

let assertions=0;
function equal(a,b){assert.deepEqual(a,b);assertions++;}
const order=(id,priority='normal',status='pending')=>({id,priority,status});
const drive=(source,target,start=0,end=1)=>({vehicle:'V1',kind:'drive',source,target,start,end,ids:[],batch:0,traffic_version:0});
const deliver=(id,at,start=1,end=2)=>({vehicle:'V1',kind:'deliver',source:at,target:at,start,end,ids:[id],batch:0,traffic_version:0});
const plan=(key,actions,revision=0)=>({fingerprint:key,revision,traffic_version:0,objective:'distance',accepted:['O1'],deferred:[],routes:[{vehicle:'V1',actions}]});
const first=plan('initial',[drive('D','A'),deliver('O1','A'),drive('A','D',2,3)]);
const scene=(revision,p=first,orders=[order('O1')],extra={})=>({id:'S1',revision,plan:p,orders,now:0,traffic_version:0,events:[],vehicles:[],...extra});

// Initial loads, initial planning and repeated polls create no artificial change.
equal(advance(null,null,scene(1)),null);
equal(advance(null,scene(0,null),scene(1)),null);
equal(advance(null,scene(1),scene(1)),null);
equal(advance(null,scene(1),scene(2,first,[order('O1','normal','planned')])),null);

// New urgent identity at the SAME destination must be tracked independently.
const added=scene(2,first,[order('O1'),order('URGENT','urgent')]);
const beforeBytes=JSON.stringify(scene(1)),afterBytes=JSON.stringify(added);
let state=advance(null,scene(1),added),summary=summarize(state,added);
equal(summary.status,'pending');equal(summary.addedOrderIds,['URGENT']);equal(summary.changedVehicleIds,[]);
equal(summary.vehicleChanges[0].removedEdges,[]); // Pending is not an applied route change.
equal(state.baselineRevision,1);
const extraOrder=scene(3,first,[...added.orders,order('URGENT2','critical')]);
state=advance(state,added,extraOrder);
equal(state.baselineRevision,1);equal(summarize(state,extraOrder).addedOrderIds,['URGENT','URGENT2']);
equal(JSON.stringify(scene(1)),beforeBytes);equal(JSON.stringify(added),afterBytes);

// Applied route changes include directed new/removed roads and preserved roads.
const replacement=plan('replanned',[drive('D','B'),deliver('URGENT','B'),drive('B','A',2,3),deliver('O1','A',3,4),drive('A','D',4,5)],3);
const applied=scene(4,replacement,extraOrder.orders);
state=advance(state,extraOrder,applied);summary=summarize(state,applied);
equal(summary.status,'compared');equal(summary.appliedRevision,4);equal(summary.baselineRevision,1);
equal(summary.changedVehicleIds,['V1']);equal(summary.vehicleChanges[0].addedEdges,[{source:'D',target:'B'},{source:'B',target:'A'}]);
equal(summary.vehicleChanges[0].removedEdges,[{source:'D',target:'A'}]);
equal(summary.vehicleChanges[0].unchangedEdges,[{source:'A',target:'D'}]);
equal(summary.vehicleChanges[0].beforeServiceIds,['O1']);equal(summary.vehicleChanges[0].afterServiceIds,['URGENT','O1']);

// Execution and delayed polling never reset or progressively delete the comparison.
const advanced=scene(5,replacement,extraOrder.orders,{now:1,events:[{kind:'action',action:replacement.routes[0].actions[0]}]});
const next=advance(state,applied,advanced);
equal(summarize(next,advanced),summary);
equal(advance(next,advanced,applied),next);
equal(advance(next,advanced,{...advanced,id:'S2'}),null);
equal(summarize(next,{...advanced,id:'S2'}),null);

// A fresh mutation after comparison starts at the latest plan, not original history.
const cancelled=scene(6,replacement,[order('O1'),order('URGENT','urgent','cancelled'),order('URGENT2','critical')],{now:1,events:advanced.events});
const again=advance(next,advanced,cancelled);
equal(again.baselineRevision,5);equal(summarize(again,cancelled).cancelledOrderIds,['URGENT']);
equal(summarize(again,cancelled).addedOrderIds,[]);

// A completed prefix before mutation and an entered action completed while waiting
// are physical history, never a removed road. Time alone cannot prove execution.
const prefix=drive('W','D',0,1),entered=drive('D','A',1,3),tail=drive('A','D',4,5);
const travelling=plan('travelling',[prefix,entered,deliver('O1','A',3,4),tail]);
const moving=scene(9,travelling,[order('O1')],{now:1,events:[{kind:'action',action:prefix}]});
const mutation=scene(10,travelling,[order('O1'),order('O2')],{now:1,events:moving.events});
let pending=advance(null,moving,mutation);
equal(pending.baselinePlan.routes[0].actions[0],entered);
const clockOnly={...mutation,revision:11,now:3};
pending=advance(pending,mutation,clockOnly);
equal(summarize(pending,clockOnly).vehicleChanges[0].beforeEdges,[{source:'D',target:'A'},{source:'A',target:'D'}]);
const checkpoint={...clockOnly,revision:12,events:[...moving.events,{kind:'action',action:entered}]};
pending=advance(pending,clockOnly,checkpoint);
const continuation=plan('continuation',[deliver('O1','A',3,4),tail],12);
const resumed={...checkpoint,revision:13,plan:continuation};
const result=summarize(advance(pending,checkpoint,resumed),resumed);
equal(result.vehicleChanges[0].removedEdges,[]);equal(result.changedVehicleIds,[]);equal(result.appliedAt,3);

// Same roads can still have changed service order (same-site order identities).
const sameRoadPlan=plan('same-road',[drive('D','A'),deliver('A','A',1,2),deliver('B','A',2,3),drive('A','D',3,4)]);
const swappedPlan=plan('swapped',[drive('D','A'),deliver('B','A',1,2),deliver('A','A',2,3),drive('A','D',3,4)],2);
const old=scene(2,sameRoadPlan,[order('A'),order('B')]),swapped=scene(3,swappedPlan,old.orders);
const swap=summarize(advance(null,old,swapped),swapped);
equal(swap.changedVehicleIds,['V1']);equal(swap.vehicleChanges[0].addedEdges,[]);equal(swap.vehicleChanges[0].removedEdges,[]);
equal(swap.vehicleChanges[0].beforeServiceIds,['A','B']);equal(swap.vehicleChanges[0].afterServiceIds,['B','A']);

// Automatic traffic replan can arrive in a single poll; reverse directions differ.
const reverse=plan('traffic',[drive('A','D')],2);
const traffic={...scene(3,reverse),traffic_version:1};
const trafficSummary=summarize(advance(null,scene(2,plan('old',[drive('D','A')])),traffic),traffic);
equal(trafficSummary.trafficChanged,true);equal(trafficSummary.status,'compared');
equal(trafficSummary.vehicleChanges[0].addedEdges,[{source:'A',target:'D'}]);
equal(trafficSummary.vehicleChanges[0].removedEdges,[{source:'D',target:'A'}]);

// Expiry and priority changes are observable, unlike routine status transitions.
const expiry=scene(2,first,[order('O1','normal','expired')]);
equal(summarize(advance(null,scene(1),expiry),expiry).cancelledOrderIds,['O1']);
const priority=scene(2,first,[order('O1','critical')]);
equal(summarize(advance(null,scene(1),priority),priority).priorityOrderIds,['O1']);

// An order added before the first plan gets a marker, not an invented old route.
const empty=scene(0,null),unplanned=scene(1,null,[order('O1'),order('NEW')]);
const unplannedState=advance(null,empty,unplanned),initial=scene(2,first,unplanned.orders);
const initialSummary=summarize(advance(unplannedState,unplanned,initial),initial);
equal(initialSummary.hasBaseline,false);equal(initialSummary.changedVehicleIds,[]);
equal(initialSummary.vehicleChanges[0].addedEdges,[]);equal(initialSummary.addedOrderIds,['NEW']);
console.log(`${assertions} route-change identity, checkpoint, polling and direction assertions passed`);
