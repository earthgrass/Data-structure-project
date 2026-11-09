/** Presentation only: names enrich search; original IDs/quantities remain intact. O(nodes). */
export function matchesOrder(order,nodes,query){
  const names=nodes.filter(n=>n.id===order.destination||n.id===order.hub).map(n=>n.name??'');
  return [order.id,order.destination,order.hub,...names].join(' ').toLowerCase().includes(query.trim().toLowerCase());
}
export function locationText(order,nodes){
  const [kind,id]=order.location;
  const label={warehouse:'仓库',hub:'中转站',vehicle:'车辆载货',delivered:'已签收'}[kind]??kind;
  const name=nodes.find(n=>n.id===id)?.name;
  return `${label} · ${name?`${name} (${id})`:id}`;
}
/** Junctions are routing geometry, not warehouses or inventory transfer sites. O(nodes). */
export function inventoryNodes(nodes){return nodes.filter(n=>n.type==='warehouse'||n.type==='transfer');}
