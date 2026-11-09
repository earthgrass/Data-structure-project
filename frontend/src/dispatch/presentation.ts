import type {Snapshot} from './types';
export const labels:Record<string,string>={load:'装货',unload:'到站卸货',deliver:'客户签收',drive:'道路行驶',wait:'等待',finish:'返抵基地',pending:'待规划',planned:'已规划',in_transit:'运输中',delivered:'已签收',cancelled:'已取消',expired:'已过期'};
export const priorities=[['critical','特急'],['urgent','紧急'],['normal','普通']];
export const trafficLabels:Record<string,string>={clear:'畅通',light:'轻微拥堵',moderate:'一般拥堵',congested:'严重拥堵',blocked:'封路'};
export const fmt=(value:number)=>value.toLocaleString('zh-CN',{maximumFractionDigits:2,minimumFractionDigits:2});
export const vehicleColor=(s:Snapshot,id:string)=>`var(--vehicle-${s.vehicles.findIndex(v=>v.id===id)%6+1})`;
