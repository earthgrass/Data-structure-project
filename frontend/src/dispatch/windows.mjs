/** Bind initial counterfactual evidence to the unchanged input; O(N), no decisions. */
export function windowEvidenceCurrent(data){
  const e=data?.time_windows;
  if(!e||e.mode!=='strict'||!e.orders||data.running||data.now!==e.initial_time||data.traffic_version!==e.initial_traffic_version)return false;
  if(data.plan&&data.plan.objective!==e.comparison_objective)return false;
  if(e.orders.length!==data.orders.length)return false;
  const expected=new Map(e.orders.map(o=>[o.id,o]));
  return data.orders.every(o=>{
    const old=expected.get(o.id);
    return old&&['pending','planned'].includes(o.status)&&o.location[0]==='warehouse'&&o.destination===old.destination&&o.demand===old.demand&&o.priority===old.priority&&o.earliest===old.earliest&&o.deadline===old.deadline;
  });
}
