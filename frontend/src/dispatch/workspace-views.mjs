/** Read-only views of the shared dispatch snapshot. No scheduling decisions. */
const rank={critical:0,urgent:1,normal:2};

export function roadSummary(snapshot){
 const counts={clear:0,light:0,moderate:0,congested:0,blocked:0};
 const used=new Map();
 for(const route of snapshot.plan?.routes??[]){
  for(const action of route.actions){
   if(action.kind!=='drive')continue;
   const key=action.source+'\0'+action.target;
   if(!used.has(key))used.set(key,[]);
   if(!used.get(key).includes(route.vehicle))used.get(key).push(route.vehicle);
  }
 }
 for(const road of snapshot.edges)if(road.status in counts)counts[road.status]++;
 return {counts,used,total:snapshot.edges.length,affected:[...used].filter(([key])=>snapshot.edges.some(e=>e.source+'\0'+e.target===key&&e.status!=='clear')).length};
}

export function dispatchQueue(snapshot){
 const timeline=new Map((snapshot.planning_insights?.timeline?.orders??[]).map(row=>[row.order_id,row]));
 const stale=snapshot.planning_insights?.timeline?.stale??true;
 const deferred=new Map(snapshot.plan?.deferred??[]);
 const rows=snapshot.orders.map(order=>{
  const time=timeline.get(order.id);
  const actual=time?.actual??null,expected=stale?null:time?.expected??null;
  const terminal=['cancelled','expired'].includes(order.status);
  const delivery=actual?'signed':terminal?'terminal':expected?'scheduled':deferred.has(order.id)?'deferred':'unknown';
  return {order,expected,actual,delivery,reason:deferred.get(order.id)??time?.deferred_reason??null};
 });
 // Hand insertion sort: priority, completion deadline, original ID. Terminal history last.
 for(let i=1;i<rows.length;i++){
  const item=rows[i];let j=i-1;
  const key=row=>[row.delivery==='signed'||row.delivery==='terminal'?1:0,rank[row.order.priority]??3,row.order.deadline,row.order.id];
  const less=(a,b)=>{const x=key(a),y=key(b);for(let k=0;k<x.length;k++){if(x[k]<y[k])return true;if(x[k]>y[k])return false;}return false;};
  while(j>=0&&less(item,rows[j])){rows[j+1]=rows[j];j--;}
  rows[j+1]=item;
 }
 return rows;
}

export function orderRoute(snapshot,orderId){
 const result=[];
 for(const route of snapshot.plan?.routes??[]){
  const index=route.actions.findIndex(a=>(a.kind==='deliver'||a.kind==='unload')&&a.ids.includes(orderId));
  if(index<0)continue;
  const segment=route.actions.slice(0,index+1);
  const points=[];
  for(const action of segment){
   if(points.length===0)points.push(action.source);
   if(action.kind==='drive'&&points[points.length-1]!==action.target)points.push(action.target);
  }
  result.push({vehicle:route.vehicle,kind:route.actions[index].kind,points});
 }
 // Freight reaches the hub before the local vehicle can sign the order.
 for(let i=1;i<result.length;i++){
  const leg=result[i];let j=i-1;
  while(j>=0&&leg.kind==='unload'&&result[j].kind!=='unload'){result[j+1]=result[j];j--;}
  result[j+1]=leg;
 }
 return result;
}
