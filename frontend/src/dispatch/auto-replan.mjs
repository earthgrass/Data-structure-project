/** Only drain backend-confirmed entered actions. Time/Space O(1).
 * Stateless: the caller owns its request lock and uses the accepted revision.
 * The server plans at the final checkpoint; this never plans or departs itself.
 */
export function checkpointCommand(snapshot,{busy,connection}){
 const control=snapshot?.order_control;
 return !busy&&connection==='connected'&&snapshot?.running===true&&
  control?.enabled===true&&control.status==='waiting_checkpoint'?'step':null;
}

/** Dashboard planning-input mutations opt in atomically. Time/Space O(F). */
export function orderMutationFields(kind,fields={}){
 return kind==='add'||kind==='automatic'||kind==='cancel'||kind==='expire'||kind==='priority'||kind==='traffic'
  ?{...fields,auto_replan:true}:fields;
}
