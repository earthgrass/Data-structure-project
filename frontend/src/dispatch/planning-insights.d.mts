import type {Snapshot} from './types';
import type {TimelineOrder,RejectionExplanation} from './insight-types';
export function signedDifference(value:number|null|undefined):string;
export function timePosition(value:number|null|undefined,domain:{start:number;end:number}):number|null;
export function timelineDomain(rows:TimelineOrder[],now:number):{start:number;end:number};
export function filterTimeline(rows:TimelineOrder[],options?:{query?:string;activeOnly?:boolean;riskOnly?:boolean;threshold?:number;forecastCurrent?:boolean}):TimelineOrder[];
export function explanationFor(snapshot:Snapshot,orderId:string):RejectionExplanation|null;
