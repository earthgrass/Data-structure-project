import {layoutMapLabels} from './geography.mjs';

const rank={normal:0,urgent:1,critical:2};

/** Preserve identities while sharing a destination pin. Time/Space O(N+K).
 * activeOnly restricts the live map to outstanding tasks; historical callers
 * retain delivered records by default. Identity validation always includes all IDs.
 */
export function groupMapOrders(orders,newIds=[],{activeOnly=false}={}){
 const groups=new Map(),seen=new Set(),fresh=new Set(newIds);
 for(const order of orders){
  if(seen.has(order.id))throw new Error('duplicate order ID: '+order.id);
  seen.add(order.id);
  if(order.status==='cancelled'||order.status==='expired')continue;
  if(activeOnly&&!['pending','planned','in_transit'].includes(order.status))continue;
  let group=groups.get(order.destination);
  if(!group){group={destination:order.destination,orders:[],ids:[],count:0,done:0,pending:0,inTransit:0,priority:'normal',allDelivered:false,newIds:[],label:''};groups.set(order.destination,group);}
  group.orders.push(order);group.ids.push(order.id);group.count++;
  if(order.status==='delivered')group.done++;
  if(order.status==='pending')group.pending++;
  if(order.status==='in_transit')group.inTransit++;
  if(order.status!=='delivered'&&(rank[order.priority]??0)>rank[group.priority])group.priority=order.priority;
  if(fresh.has(order.id))group.newIds.push(order.id);
 }
 for(const group of groups.values()){
  group.allDelivered=group.done===group.count;
  const id=group.newIds[0]??group.ids[0],priority=group.priority==='critical'?'特急':group.priority==='urgent'?'紧急':'';
  group.label=(group.newIds.length?'新 · ':'')+id+(group.count>1?` +${group.count-1}`:'')+(group.allDelivered?' · 已签收':priority?' · '+priority:'');
 }
 return groups;
}

/** Selected/new/urgent labels win screen space. O(N*(N+B)), B input label obstacles. */
export function buildOrderMapLabels(groups,points,zoom,selected='',obstacles=[]){
 const arranged=[],used=new Set();
 const add=group=>{const p=points.get(group.destination);if(!p||used.has(group.destination))return;used.add(group.destination);arranged.push({id:group.destination,point:[p[0]*zoom,p[1]*zoom],text:group.label});};
 if(groups.has(selected))add(groups.get(selected));
 for(const group of groups.values())if(group.newIds.length)add(group);
 for(const priority of ['critical','urgent','normal'])for(const group of groups.values())if(!group.allDelivered&&group.priority===priority)add(group);
 for(const group of groups.values())add(group);
 return layoutMapLabels(arranged,obstacles);
}
