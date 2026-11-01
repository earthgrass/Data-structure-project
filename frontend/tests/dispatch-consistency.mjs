import assert from 'node:assert/strict';
import { bindComparison, reconcileSnapshot, actionPhase } from '../src/dispatch/sync.mjs';
const plan={fingerprint:'same-input',revision:7,traffic_version:2};
const s={id:'a',revision:7,traffic_version:2,plan,events:[],vehicles:[],ready:true};
const comparison=bindComparison(s,[plan,plan]);
assert.equal(comparison.sessionId,'a');
assert.equal(reconcileSnapshot(s,comparison,{...s},'a').comparison,comparison);
for(const command of ['add','cancel','priority','traffic','plan','step','pause','depart']){
  const next={...s,revision:8,traffic_version:command==='traffic'?3:2};
  const result=reconcileSnapshot(s,comparison,next,'a');
  assert.equal(result.comparison,null,command);
  assert.equal(result.snapshot.plan,plan,'keep backend plan after '+command);
}
assert.equal(reconcileSnapshot(s,comparison,{...s,revision:6},'a').snapshot,s);
assert.equal(reconcileSnapshot(s,comparison,{...s,id:'b',revision:100},'a').comparison,comparison);
assert.equal(bindComparison(s,[plan,{...plan,fingerprint:'different'}]),null);
assert.equal(bindComparison(s,[{...plan,revision:6},plan]),null);
const action={vehicle:'truck',kind:'drive',start:0,end:5,source:'W',target:'C',ids:[],batch:1,traffic_version:2};
const event={kind:'action',action};
assert.equal(actionPhase({...s,events:[event,{kind:'plan'}]},action),'pending');
assert.equal(actionPhase({...s,events:[{kind:'plan'},event]},action),'completed');
assert.equal(actionPhase({...s,vehicles:[{id:'truck',current:action}]},action),'current');
assert.equal(actionPhase({...s,needs_replan:true},action),'paused');
assert.equal(actionPhase({...s,ready:false},action),'unknown');
console.log('27 comparison/snapshot/timeline assertions passed');
