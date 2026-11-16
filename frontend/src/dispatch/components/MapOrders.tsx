import type {Point} from '../geography.mjs';
import type {OrderGroup,OrderMapLabel} from '../order-map.mjs';

/** One shared geographic pin, all distinct order IDs retained in the selected detail. */
export function MapOrders({groups,points,zoom,labels,selected,onSelect}:{groups:Map<string,OrderGroup>;points:Map<string,Point>;zoom:number;labels:Map<string,OrderMapLabel>;selected:string;onSelect:(id:string)=>void}){
 return <g className="d-order-map-layer">{[...groups.values()].map(group=>{
  const p=points.get(group.destination);if(!p)return null;
  const label=labels.get(group.destination),priority=group.priority==='critical'?'特急':group.priority==='urgent'?'紧急':'普通';
  const description=`${group.newIds.length?'新增订单 · ':''}${priority} · ${group.ids.join('、')} · ${group.count}单，已签收${group.done}单，待规划${group.pending}单`;
  return <g key={group.destination} className={`d-order-pin ${group.priority}${group.allDelivered?' delivered':''}${group.newIds.length?' fresh':''}${selected===group.destination?' selected':''}`} transform={`translate(${p[0]} ${p[1]})`} data-order-ids={group.ids.join(',')} role="button" tabIndex={0} aria-label={`查看订单 ${group.ids.join('、')}，${priority}，${group.count}单`} onClick={()=>onSelect(group.destination)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(group.destination);}}}>
   <title>{description}</title><g transform={`scale(${1/zoom})`}>
    <circle className="d-order-pin-hit" r="23"/>
    {group.newIds.length>0&&<circle className="d-order-pin-new-ring" r="22"/>}
    <path className="d-order-pin-body" d="M-15-12Q-15-17-10-17H10Q15-17 15-12V8Q15 13 10 13H5L0 19-5 13H-10Q-15 13-15 8Z"/>
    {group.allDelivered?<path className="d-order-pin-symbol" d="m-7-2 5 5 9-10"/>:<><path className="d-order-pin-symbol" d="m-8-8 8-4 8 4v10L0 6-8 2Z M-8-8 0-4 8-8 M0-4V6"/>{group.priority!=='normal'&&<g><circle className="d-order-pin-alert" cx="14" cy="-16" r="8"/><text className="d-order-pin-alert-text" x="14" y="-13">!</text></g>}</>}
    {group.count>1&&<g><circle className="d-order-pin-count-bg" cx="-13" cy="-15" r="9"/><text className="d-order-pin-count" x="-13" y="-12">{group.count}</text></g>}
    {label&&<text className="d-order-pin-label" x={label.x} y={label.y} textAnchor={label.anchor}>{label.text}</text>}
   </g>
  </g>;
 })}</g>;
}
