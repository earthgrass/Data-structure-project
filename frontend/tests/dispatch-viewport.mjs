import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {projectNodes,fitViewport} from '../src/dispatch/viewport.mjs';
import {mapProjection} from '../src/dispatch/geography.mjs';
const nodes=[{id:'left',x:-100,y:0},{id:'right',x:500,y:1000},{id:'middle',x:200,y:500}];
for(const [width,height] of [[991,396],[740,280],[1100,496],[356,330]]){
 const result=projectNodes(nodes,width,height);
 assert.equal(result.size,3);
 for(const [x,y] of result.values())assert.ok(x>=80&&x<=width-80&&y>=64&&y<=height-64);
 assert.deepEqual(result.get('middle'),[width/2,height/2]);
}
assert.deepEqual(projectNodes([{id:'one',x:2,y:3}],400,300).get('one'),[200,150]);
assert.equal(projectNodes([],400,300).size,0);
const outside=[[-180,-100],[200,200],[550,480]];
const fitted=fitViewport(outside,420,300,{left:36,right:24,top:44,bottom:30});
assert.ok(fitted.zoom<1);
for(const [x,y] of outside){
 const sx=210+(x-fitted.center[0])*fitted.zoom,sy=150+(y-fitted.center[1])*fitted.zoom;
 assert.ok(sx>=36-1e-9&&sx<=396+1e-9);
 assert.ok(sy>=44-1e-9&&sy<=270+1e-9);
}
assert.deepEqual(fitViewport([],420,300),{zoom:1,center:[210,150]});
assert.deepEqual(fitViewport([[25,40]],420,300),{zoom:1,center:[25,40]});
const campus=JSON.parse(readFileSync(new URL('../../data/bjut/campus-network.json',import.meta.url),'utf8'));
const stations=campus.nodes.filter(n=>!n.metadata.routing_only);
assert.equal(stations.length,37);
for(const [width,height,insets] of [[467,626,{left:35,right:35,top:210,bottom:85}],[1440,900,{left:45,right:45,top:245,bottom:245}]]){
 const project=mapProjection(campus.bounds,width,height,80);
 const fittedCampus=fitViewport(stations.map(n=>project([n.x,n.y])),width,height,insets);
 for(const station of stations){
  const [x,y]=project([station.x,station.y]);
  const sx=width/2+(x-fittedCampus.center[0])*fittedCampus.zoom;
  const sy=height/2+(y-fittedCampus.center[1])*fittedCampus.zoom;
  assert.ok(sx>=insets.left-1e-9&&sx<=width-insets.right+1e-9,station.id+' horizontal fit');
  assert.ok(sy>=insets.top-1e-9&&sy<=height-insets.bottom+1e-9,station.id+' vertical fit');
 }
}
console.log('Viewport boundaries and all 37 campus stations fit at mobile and desktop sizes');
