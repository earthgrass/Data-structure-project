import assert from 'node:assert/strict';
import {autoTrafficChoice} from '../src/dispatch/auto-traffic.mjs';

const scene={edges:[
 {source:'A',target:'B',status:'clear'},
 {source:'B',target:'C',status:'moderate'},
 {source:'C',target:'A',status:'clear'},
 {source:'X',target:'Y',status:'clear'}],
 plan:{routes:[{actions:[
  {kind:'drive',source:'A',target:'B'},
  {kind:'drive',source:'B',target:'C'},
  {kind:'drive',source:'A',target:'B'}]}]}};
const original=JSON.stringify(scene);
const first=autoTrafficChoice(scene,42,0);
assert.deepEqual(first,autoTrafficChoice(scene,42,0));
assert.ok(['A|B','B|C'].includes(first.source+'|'+first.target));
assert.notEqual(first.status,scene.edges.find(e=>e.source===first.source&&e.target===first.target).status);
assert.deepEqual(Array.from({length:10},(_,i)=>autoTrafficChoice(scene,42,i)),
                 Array.from({length:10},(_,i)=>autoTrafficChoice(scene,42,i)));
assert.equal(autoTrafficChoice({...scene,plan:null},42,0),null);
assert.equal(autoTrafficChoice({...scene,now:10,plan:{routes:[{actions:[{kind:'drive',source:'A',target:'B',end:9}]}]}},42,0),null);
assert.equal(JSON.stringify(scene),original);
console.log('7 deterministic route-focused traffic draw assertions passed');
