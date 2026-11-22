import assert from 'node:assert/strict';
import {liveDriveActions,mapPlanIsStale,congestedMapRoads} from '../src/dispatch/map-state.mjs';

const drive=(source,target)=>({vehicle:'V',kind:'drive',source,target,start:0,end:1,ids:[],batch:0,traffic_version:0});
const old=drive('A','B'),next=drive('A','C');
const scene={plan:{revision:2,traffic_version:0,routes:[{vehicle:'V',actions:[next]},{vehicle:'W',actions:[{...next,vehicle:'W',source:'D'}]}]},vehicles:[],events:[{kind:'plan'}],traffic_version:0,needs_replan:false,ready:true,running:false};
assert.deepEqual(liveDriveActions(scene,'V',false).map(item=>[item.vehicle,item.action.source,item.action.target]),[['V','A','C']]);
assert.equal(liveDriveActions(scene,'V',true).length,2);
assert.equal(liveDriveActions({...scene,events:[{kind:'plan'},{kind:'action',action:next}]},'V',false).length,0);
assert.equal(liveDriveActions({...scene,vehicles:[{current:next}]},'V',false)[0].phase,'current');
assert.equal(liveDriveActions({...scene,plan:{...scene.plan,routes:[{vehicle:'V',actions:[old]}]}},'V',false)[0].action.target,'B');
assert.equal(mapPlanIsStale(scene),false);
assert.equal(mapPlanIsStale({...scene,traffic_version:1}),true);
assert.equal(mapPlanIsStale({...scene,order_control:{status:'waiting_checkpoint'}}),true);
assert.equal(mapPlanIsStale({...scene,order_control:{status:'applied',order_version:2,planned_order_version:1}}),true);
assert.equal(mapPlanIsStale({...scene,order_control:{status:'applied',order_version:2,planned_order_version:2}}),false);
assert.deepEqual(congestedMapRoads(['clear','light','moderate','congested','blocked'].map(status=>({status}))).map(road=>road.status),['light','moderate','congested','blocked']);
console.log('11 live-map plan, checkpoint and directional congestion assertions passed');
