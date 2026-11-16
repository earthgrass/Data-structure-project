import type {Snapshot,Plan} from './types';
type OrderFact={id:string;priority:string;status:string};
export type RouteChangeState={sessionId:string;status:'pending'|'compared';baselineRevision:number;baselineNow:number;baselinePlan:Plan|null;baselinePlanKey:string|null;baselineOrders:OrderFact[];baselineTrafficVersion:number;observedRevision:number;appliedRevision:number|null;appliedAt:number|null;appliedPlan:Plan|null;appliedOrders:OrderFact[]|null;appliedTrafficVersion:number|null};
export type RouteEdge={source:string;target:string};
export type VehicleRouteChange={vehicle:string;beforeEdges:RouteEdge[];afterEdges:RouteEdge[];addedEdges:RouteEdge[];removedEdges:RouteEdge[];unchangedEdges:RouteEdge[];beforeServiceIds:string[];afterServiceIds:string[];changed:boolean;timingChanged:boolean};
export type RouteChangeSummary={sessionId:string;status:'pending'|'compared';hasBaseline:boolean;baselineRevision:number;baselineNow:number;appliedRevision:number|null;appliedAt:number|null;addedOrderIds:string[];cancelledOrderIds:string[];priorityOrderIds:string[];trafficChanged:boolean;changedVehicleIds:string[];vehicleChanges:VehicleRouteChange[]};
export function advanceRouteChanges(previous:RouteChangeState|null,before:Snapshot|null,after:Snapshot):RouteChangeState|null;
export function summarizeRouteChanges(state:RouteChangeState|null,snapshot:Snapshot):RouteChangeSummary|null;
