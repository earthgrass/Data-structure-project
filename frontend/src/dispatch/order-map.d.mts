import type {Snapshot} from './types';
import type {Point,LabelBox} from './geography.mjs';
export type OrderGroup={destination:string;orders:Snapshot['orders'];ids:string[];count:number;done:number;pending:number;inTransit:number;priority:string;allDelivered:boolean;newIds:string[];label:string};
export type OrderMapLabel={x:number;y:number;anchor:'start'|'middle'|'end';text:string;box:{left:number;right:number;top:number;bottom:number}};
export function groupMapOrders(orders:Snapshot['orders'],newIds?:string[],options?:{activeOnly?:boolean}):Map<string,OrderGroup>;
export function buildOrderMapLabels(groups:Map<string,OrderGroup>,points:Map<string,Point>,zoom:number,selected?:string,obstacles?:readonly LabelBox[]):Map<string,OrderMapLabel>;
