/** One deterministic simulated update on a road used by the current plan.
 * The backend remains authoritative for traffic weights and replanning. O(A+E).
 */
export function autoTrafficChoice(snapshot,seed,tick){
 if(!snapshot.plan||!Number.isInteger(seed)||!Number.isInteger(tick)||tick<0)return null;
 const byDirection=new Map(snapshot.edges.map(edge=>[edge.source+'|'+edge.target,edge]));
 const seen=new Set(),candidates=[];
 for(const route of snapshot.plan.routes)for(const action of route.actions){
  if(action.kind!=='drive'||typeof action.end==='number'&&action.end<=snapshot.now)continue;
  const key=action.source+'|'+action.target,edge=byDirection.get(key);
  if(edge&&!seen.has(key)){seen.add(key);candidates.push(edge);}
 }
 if(!candidates.length)return null;
 const draw=(Math.imul((seed|0)^(tick+1),1664525)+1013904223)>>>0;
 const edge=candidates[draw%candidates.length],states=['clear','light','moderate','congested'];
 let status=states[(draw>>>16)%states.length];
 if(status===edge.status)status=states[(states.indexOf(status)+1)%states.length];
 return {source:edge.source,target:edge.target,status};
}
