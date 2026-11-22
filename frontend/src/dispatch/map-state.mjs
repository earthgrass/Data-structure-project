import {actionPhase} from './sync.mjs';

/** Render only the applied plan's unexecuted directed travel actions.
 * Time O(routes * actions * (vehicles + events)); space O(drive actions).
 * Completed actions remain in backend history, not in the live route layer.
 */
export function liveDriveActions(snapshot,selected,showAll){
 const routes=snapshot.plan?.routes??[],result=[];
 for(const route of routes){
  if(!showAll&&route.vehicle!==selected)continue;
  for(const action of route.actions){
   if(action.kind!=='drive')continue;
   const phase=actionPhase(snapshot,action);
   if(phase!=='completed')result.push({vehicle:route.vehicle,action,phase});
  }
 }
 return result;
}

/** A changed input is not a new route until the backend applies a matching plan. O(1). */
export function mapPlanIsStale(snapshot){
 const control=snapshot.order_control;
 return !!snapshot.plan&&(!!snapshot.needs_replan||snapshot.plan.traffic_version!==snapshot.traffic_version||
  control?.status==='waiting_checkpoint'||control?.status==='blocked'||
  control?.planned_order_version!=null&&control.planned_order_version!==control.order_version);
}

/** Directional congestion remains visible even when the neutral road layer is hidden. O(E). */
export function congestedMapRoads(edges){
 return edges.filter(road=>road.status!=='clear'&&['light','moderate','congested','blocked'].includes(road.status));
}

/** The latest actual road mutation, including a return to clear. O(events + edges). */
export function latestTrafficRoad(snapshot){
 for(let i=snapshot.events.length-1;i>=0;i--){
  const event=snapshot.events[i];
  if(event.kind!=='traffic')continue;
  const road=snapshot.edges.find(edge=>edge.source===event.source&&edge.target===event.target);
  return road?{road,event}:null;
 }
 return null;
}
