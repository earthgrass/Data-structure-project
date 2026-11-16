/** Read-only display helpers; never decide feasibility or recalculate routes. */
export function signedDifference(value){
 if(typeof value!=='number'||!Number.isFinite(value))return '暂无对照';
 if(value===0)return '不变';
 const magnitude=Math.abs(value);
 return (value>0?'增加 ':'减少 ')+(magnitude<.01?'<0.01':magnitude.toFixed(2));
}

/** Time/Space O(1). Clamping changes the drawing only, never underlying times. */
export function timePosition(value,domain){
 if(typeof value!=='number'||!Number.isFinite(value))return null;
 if(domain.end<=domain.start)return 0;
 return Math.max(0,Math.min(100,(value-domain.start)/(domain.end-domain.start)*100));
}

/** One shared axis for every visible order. Time O(N), Space O(1). */
export function timelineDomain(rows,now){
 let start=Number.isFinite(now)?now:0,end=start;
 for(const row of rows){
  const values=[row.earliest,row.deadline,row.expected?.arrival,row.expected?.service_start,row.expected?.signoff,row.actual?.arrival,row.actual?.service_start,row.actual?.signoff];
  for(const value of values)if(typeof value==='number'&&Number.isFinite(value)){start=Math.min(start,value);end=Math.max(end,value);}
 }
 return {start,end:end>start?end:start+1};
}

/** Keep order identity and backend order; no inferred status. Time/Space O(N). */
export function filterTimeline(rows,{query='',activeOnly=false,riskOnly=false,threshold=5,forecastCurrent=true}={}){
 const needle=query.trim().toLocaleLowerCase();
 return rows.filter(row=>{
  const active=['pending','planned','in_transit'].includes(row.status);
  if(activeOnly&&!active)return false;
  if(riskOnly&&(!active||!forecastCurrent||!row.expected||!Number.isFinite(row.expected.slack)||row.expected.slack>threshold))return false;
  return !needle||[row.order_id,row.destination,row.expected?.vehicle,row.actual?.vehicle].some(value=>value?.toLocaleLowerCase().includes(needle));
 });
}

/** Prefer the backend's latest diagnosis, even if its list is intentionally empty. */
export function explanationFor(snapshot,orderId){
 const items=snapshot.planning_insights?.explanations?.items??snapshot.plan?.explanations??[];
 return items.find(item=>item.order_id===orderId)??null;
}
