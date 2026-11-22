/** Mirror the backend's cancellation gate for affordances only; the command
 * remains authoritative and may still reject a concurrent state change. O(K).
 */
export function cancellationBlockReason(snapshot,order){
 if(['delivered','cancelled','expired'].includes(order.status))return '订单已终结，保留身份记录';
 if(order.location[0]!=='warehouse')return '货物已出仓，不能取消';
 if(snapshot.vehicles.some(vehicle=>vehicle.current?.kind==='load'&&vehicle.current.ids.includes(order.id)))return '装货动作已开始，不能取消';
 return '';
}
