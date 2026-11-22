import assert from 'node:assert/strict';
import {dispatchQueue,orderRoute,roadSummary} from '../src/dispatch/workspace-views.mjs';
const orders=[
 {id:'N',priority:'normal',deadline:10,status:'planned'},
 {id:'C2',priority:'critical',deadline:9,status:'planned'},
 {id:'C1',priority:'critical',deadline:8,status:'planned'},
 {id:'U',priority:'urgent',deadline:2,status:'pending'},
 {id:'DONE',priority:'critical',deadline:1,status:'delivered'}];
const timeline={stale:false,orders:[
 {order_id:'C1',expected:{vehicle:'V',signoff:7,slack:1},actual:null},
 {order_id:'DONE',expected:null,actual:{vehicle:'V',signoff:1}}]};
const snapshot={orders,planning_insights:{timeline},plan:{deferred:[['U','capacity']],routes:[{vehicle:'V',actions:[
 {kind:'drive',source:'H',target:'P'},
 {kind:'deliver',source:'P',target:'P',ids:['C1']}]},{vehicle:'TRUNK',actions:[
 {kind:'drive',source:'W',target:'H'},
 {kind:'unload',source:'H',target:'H',ids:['C1']}]}]},edges:[{source:'W',target:'H',status:'congested'},{source:'H',target:'P',status:'blocked'},{source:'P',target:'H',status:'clear'}]};
assert.deepEqual(dispatchQueue(snapshot).map(r=>r.order.id),['C1','C2','U','N','DONE']);
assert.equal(dispatchQueue(snapshot)[0].delivery,'scheduled');
assert.equal(dispatchQueue(snapshot)[2].delivery,'deferred');
assert.equal(dispatchQueue(snapshot)[2].reason,'capacity');
assert.equal(dispatchQueue(snapshot)[4].delivery,'signed');
assert.equal(dispatchQueue({...snapshot,planning_insights:{timeline:{...timeline,stale:true}}})[0].delivery,'unknown');
const lateSnapshot={...snapshot,planning_insights:{timeline:{...timeline,orders:[
 ...timeline.orders,{order_id:'N',expected:{vehicle:'V',signoff:13,slack:-3},actual:null},
 {order_id:'DONE',expected:null,actual:{vehicle:'V',signoff:2,slack:-1}}]}}};
assert.equal(dispatchQueue(lateSnapshot).find(row=>row.order.id==='N').delivery,'late_expected');
assert.equal(dispatchQueue(lateSnapshot).find(row=>row.order.id==='DONE').delivery,'late_signed');
assert.deepEqual(orderRoute(snapshot,'C1'),[{vehicle:'TRUNK',kind:'unload',points:['W','H']},{vehicle:'V',kind:'deliver',points:['H','P']}]);
assert.equal(roadSummary(snapshot).counts.blocked,1);
assert.equal(roadSummary(snapshot).affected,2);
assert.deepEqual(roadSummary(snapshot).used.get('W\0H'),['TRUNK']);
console.log('12 shared-snapshot road, order, timing, lateness and route view assertions passed');
