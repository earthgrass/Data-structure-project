import type {Action,Vehicle,Road} from './types';
export function driveFraction(action:Action,clock:number):number;
export function vehiclePoint(car:Vehicle,clock:number,points:Map<string,[number,number]>):[number,number];
export function segmentDuration(from:number,to:number,speed:number,reduced?:boolean):number;
export function physicalRoads(edges:Road[]):{key:string;directions:Road[]}[];
