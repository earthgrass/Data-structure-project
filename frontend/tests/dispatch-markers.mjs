import assert from 'node:assert/strict';
import {layoutVehicleBadges} from '../src/dispatch/markers.mjs';
const input=Array.from({length:6},(_,i)=>({id:`V${i}`,point:[200,200],text:`V${i}`}));
const original=JSON.stringify(input),r=layoutVehicleBadges(input);
assert.equal(r.size,6);
for(let i=0;i<input.length;i++)for(let j=i+1;j<input.length;j++){
 const a=r.get(input[i].id),b=r.get(input[j].id);
 assert.ok(a.x+a.width+6<=b.x||b.x+b.width+6<=a.x||a.y+32+6<=b.y||b.y+32+6<=a.y);
}
assert.equal(JSON.stringify(input),original);
assert.deepEqual([...r],[...layoutVehicleBadges(input)]);
const bounded=layoutVehicleBadges(input.map(v=>({...v,point:[-20,370]})),[],{left:12,right:378,top:300,bottom:550});
assert.equal(bounded.size,6);
for(const b of bounded.values())assert.ok(b.x>=12&&b.x+b.width<=378&&b.y>=300&&b.y+32<=550);
assert.equal(layoutVehicleBadges(input,[],{left:0,right:20,top:0,bottom:20}).size,0);
console.log('26 deterministic vehicle badge separation and immutable-position assertions passed');
