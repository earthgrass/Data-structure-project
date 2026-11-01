import assert from 'node:assert/strict';
import {projectNodes} from '../src/dispatch/viewport.mjs';
const nodes=[{id:'left',x:-100,y:0},{id:'right',x:500,y:1000},{id:'middle',x:200,y:500}];
for(const [width,height] of [[991,396],[740,280],[1100,496],[356,330]]){
 const result=projectNodes(nodes,width,height);
 assert.equal(result.size,3);
 for(const [x,y] of result.values())assert.ok(x>=80&&x<=width-80&&y>=64&&y<=height-64);
 assert.deepEqual(result.get('middle'),[width/2,height/2]);
}
assert.deepEqual(projectNodes([{id:'one',x:2,y:3}],400,300).get('one'),[200,150]);
assert.equal(projectNodes([],400,300).size,0);
console.log('22 viewport boundary, affine midpoint and degenerate-scene assertions passed');
