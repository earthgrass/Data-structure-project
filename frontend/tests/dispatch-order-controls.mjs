import assert from 'node:assert/strict';
import {cancellationBlockReason,cancellableOrders} from '../src/dispatch/order-controls.mjs';

const order={id:'O1',status:'planned',location:['warehouse','W1']};
const scene={vehicles:[{current:null}]};
assert.equal(cancellationBlockReason(scene,order),'');
assert.match(cancellationBlockReason(scene,{...order,status:'delivered'}),/终结/);
assert.match(cancellationBlockReason(scene,{...order,status:'cancelled'}),/终结/);
assert.match(cancellationBlockReason(scene,{...order,status:'expired'}),/终结/);
assert.match(cancellationBlockReason(scene,{...order,location:['hub','H1']}),/出仓/);
assert.match(cancellationBlockReason(scene,{...order,location:['vehicle','V1']}),/出仓/);
assert.match(cancellationBlockReason({vehicles:[{current:{kind:'load',ids:['O1']}}]},order),/装货/);
assert.equal(cancellationBlockReason({vehicles:[{current:{kind:'load',ids:['O2']}}]},order),'');
const sameSite=[{...order,destination:'P1'},{...order,id:'O2',destination:'P1'},{...order,id:'O3',destination:'P1',status:'delivered'},{...order,id:'O4',destination:'P1',location:['vehicle','V1']}];
const untouched=JSON.stringify(sameSite);
assert.deepEqual(cancellableOrders({orders:sameSite,vehicles:[{current:null}]}).map(item=>item.id),['O1','O2']);
assert.deepEqual(cancellableOrders({orders:sameSite,vehicles:[{current:{kind:'load',ids:['O1']}}]}).map(item=>item.id),['O2']);
assert.equal(JSON.stringify(sameSite),untouched);
console.log('11 map cancellation eligibility assertions passed');
