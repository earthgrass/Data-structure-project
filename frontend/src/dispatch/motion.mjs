/** Pure visual interpolation. Never writes physical positions, load or order status. */
export function driveFraction(action,clock){
  if(action.end<=action.start)return 0;
  return Math.max(0,Math.min(1,(clock-action.start)/(action.end-action.start)));
}
export function vehiclePoint(car,clock,points,geometry){
  const base=points.get(car.position)??[0,0],a=car.current;
  if(!a||a.kind!=='drive'||a.source!==car.position||!points.has(a.target))return base;
  const target=points.get(a.target),p=driveFraction(a,clock);
  if(geometry?.length)return polylinePoint(geometry,p);
  return [base[0]+(target[0]-base[0])*p,base[1]+(target[1]-base[1])*p];
}
import {polylinePoint} from './geography.mjs';
export function segmentDuration(from,to,speed,reduced=false){
  return reduced?0:Math.max(400,Math.min(1600,Math.max(0,to-from)*20))/speed;
}
/** One base stroke per physical pair. Keep both real directional records. */
export function physicalRoads(edges){
  const groups=new Map();
  for(const e of edges){
    const key=JSON.stringify(e.source<e.target?[e.source,e.target]:[e.target,e.source]);
    if(!groups.has(key))groups.set(key,{key,directions:[]});
    groups.get(key).directions.push(e);
  }
  return [...groups.values()];
}
