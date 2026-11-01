import assert from 'node:assert/strict';
import { acceptSnapshot } from '../src/dispatch/sync.mjs';
const current={id:'a',revision:12};
assert.equal(acceptSnapshot(current,{id:'a',revision:11},'a'),current);
assert.equal(acceptSnapshot(current,{id:'b',revision:100},'a'),current);
assert.equal(acceptSnapshot(current,{id:'a',revision:13},'a').revision,13);
assert.equal(acceptSnapshot(null,{id:'b',revision:0},'a'),null);
assert.equal(acceptSnapshot(null,{id:'a',revision:0},'a').revision,0);
console.log('5 snapshot ordering assertions passed');
