import type {Snapshot,Action,Road} from './types';
export function liveDriveActions(snapshot:Snapshot,selected:string,showAll:boolean):{vehicle:string;action:Action;phase:string}[];
export function mapPlanIsStale(snapshot:Snapshot):boolean;
export function congestedMapRoads(edges:Road[]):Road[];
