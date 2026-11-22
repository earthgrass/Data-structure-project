import type {Snapshot} from './types';
import type {InsightTiming} from './insight-types';
export function roadSummary(snapshot:Snapshot):{counts:Record<string,number>;used:Map<string,string[]>;total:number;affected:number};
export function dispatchQueue(snapshot:Snapshot):{order:Snapshot['orders'][number];expected:InsightTiming|null;actual:InsightTiming|null;delivery:'signed'|'late_signed'|'terminal'|'scheduled'|'late_expected'|'deferred'|'unknown';reason:string|null}[];
export function orderRoute(snapshot:Snapshot,orderId:string):{vehicle:string;kind:string;points:string[]}[];
