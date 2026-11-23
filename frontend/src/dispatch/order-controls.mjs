/** Mirror the backend's cancellation gate for affordances only; the command
 * remains authoritative and may still reject a concurrent state change. O(K).
 */
export function cancellationBlockReason(snapshot,order){
 if(['delivered','cancelled','expired'].includes(order.status))return '订单已终结，保留身份记录';
 if(order.location[0]!=='warehouse')return '货物已出仓，不能取消';
 if(snapshot.vehicles.some(vehicle=>vehicle.current?.kind==='load'&&vehicle.current.ids.includes(order.id)))return '装货动作已开始，不能取消';
 return '';
}

/** Select by order ID even when several orders share one destination. O(N*K). */
export function cancellableOrders(snapshot){
 return snapshot.orders.filter(order=>!cancellationBlockReason(snapshot,order));
}

/** New removal workflow: in-flight cargo is returned at its vehicle base. */
export function removalBlockReason(snapshot,order){
 if(['delivered','cancelled','expired'].includes(order.status))return '订单已终结，保留身份记录';
 if(snapshot.vehicles.some(vehicle=>vehicle.current?.kind==='deliver'&&vehicle.current.ids.includes(order.id)))return '签收动作已开始，无法撤销';
 return '';
}

export function removableOrders(snapshot){
 return snapshot.orders.filter(order=>!removalBlockReason(snapshot,order));
}
