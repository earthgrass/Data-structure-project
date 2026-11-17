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

/** Keep order identity and backend order; no inferred status. Time/Space O(N+V). */
export function filterTimeline(rows,{query='',activeOnly=false,riskOnly=false,threshold=5,forecastCurrent=true,nodes=[]}={}){
 const needle=query.trim().toLocaleLowerCase();
 const names=new Map(nodes.map(node=>[node.id,node.name??'']));
 return rows.filter(row=>{
  const active=['pending','planned','in_transit'].includes(row.status);
  if(activeOnly&&!active)return false;
  if(riskOnly&&(!active||!forecastCurrent||!row.expected||!Number.isFinite(row.expected.slack)||row.expected.slack>threshold))return false;
  return !needle||[row.order_id,row.destination,names.get(row.destination),row.expected?.vehicle,row.actual?.vehicle].some(value=>value?.toLocaleLowerCase().includes(needle));
 });
}

/** Prefer the backend's latest diagnosis, even if its list is intentionally empty. */
export function explanationFor(snapshot,orderId){
 return rejectionContext(snapshot).items.find(item=>item.order_id===orderId)??null;
}

/** Bind only the failed response to the exact input that produced it. O(1). */
export function bindRejectedPlan(status,snapshot,payload){
 const error=payload?.error,report=error?.report;
 if(status!==422||error?.kind!=='unsafe_plan'||!snapshot||!report||
    report.revision!==snapshot.revision||report.traffic_version!==snapshot.traffic_version||
    report.report?.safe_to_apply!==false||!Array.isArray(report.deferred))return null;
 return {session_id:snapshot.id,input_revision:snapshot.revision,traffic_version:snapshot.traffic_version,report};
}

/** Polls of the same input retain evidence; all changed inputs discard it. O(1). */
export function retainRejectedPlan(evidence,snapshot){
 return evidence&&snapshot&&evidence.session_id===snapshot.id&&evidence.input_revision===snapshot.revision&&
  evidence.traffic_version===snapshot.traffic_version?evidence:null;
}

/** Display-only attachment: never replace the applied plan or backend insights. */
export function withRejectedPlan(snapshot,evidence){
 const current=retainRejectedPlan(evidence,snapshot);
 return current?{...snapshot,rejected_proposal:current}:snapshot;
}

/** Explicit source provenance, including an unapplied HTTP error report. O(1). */
export function rejectionContext(snapshot){
 const rejected=retainRejectedPlan(snapshot.rejected_proposal,snapshot);
 if(rejected)return {source:'rejected_response',revision:rejected.input_revision,traffic_version:rejected.traffic_version,
  stale:false,items:rejected.report.explanations??[]};
 return snapshot.planning_insights?.explanations??{source:'applied_plan',revision:snapshot.plan?.revision??null,
  traffic_version:snapshot.plan?.traffic_version??null,stale:false,items:snapshot.plan?.explanations??[]};
}
