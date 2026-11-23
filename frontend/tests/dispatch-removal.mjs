import assert from 'node:assert/strict';
import {removalBlockReason,removableOrders} from '../src/dispatch/order-controls.mjs';
import {orderMutationFields} from '../src/dispatch/auto-replan.mjs';

const order={id:'O1',status:'in_transit',location:['vehicle','V1']};
const scene={orders:[order,{...order,id:'O2',location:['hub','H1']}],vehicles:[{current:null}]};
assert.equal(removalBlockReason(scene,order),'');
assert.deepEqual(removableOrders(scene).map(item=>item.id),['O1','O2']);
assert.match(removalBlockReason({...scene,vehicles:[{current:{kind:'deliver',ids:['O1']}}]},order),/签收/);
assert.match(removalBlockReason(scene,{...order,status:'delivered'}),/终结/);
assert.deepEqual(orderMutationFields('remove',{id:'O1'}),{id:'O1',auto_replan:true});
console.log('5 in-transit removal affordance assertions passed');
