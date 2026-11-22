import assert from 'node:assert/strict';
import {cancellationBlockReason} from '../src/dispatch/order-controls.mjs';

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
console.log('8 map cancellation eligibility assertions passed');
