import assert from 'node:assert/strict';
import {suggestOrderWindow,urgentWindowError} from '../src/dispatch/order-window-defaults.mjs';

assert.deepEqual(suggestOrderWindow('urgent',0,20),{earliest:5,deadline:15});
assert.deepEqual(suggestOrderWindow('urgent',12.5,20),{earliest:17.5,deadline:27.5});
assert.deepEqual(suggestOrderWindow('critical',10,20),{earliest:15,deadline:25});
assert.deepEqual(suggestOrderWindow('normal',0,20),{earliest:0,deadline:20});
assert.equal(urgentWindowError('urgent',0,5,15),'');
assert.match(urgentWindowError('urgent',0,15,25),/15/);
assert.match(urgentWindowError('urgent',0,5,25),/20/);
assert.equal(urgentWindowError('critical',0,5,15),'');
assert.match(urgentWindowError('critical',0,10,20),/10/);
assert.match(urgentWindowError('critical',0,5,20),/15/);
assert.match(urgentWindowError('urgent',0,15,10),/早于/);
assert.equal(urgentWindowError('normal',0,5,50),'');
console.log('12 urgent order window defaults and bounds assertions passed');
