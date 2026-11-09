import type {Snapshot} from './types';
export function matchesOrder(order:Snapshot['orders'][number],nodes:Snapshot['nodes'],query:string):boolean;
export function locationText(order:Snapshot['orders'][number],nodes:Snapshot['nodes']):string;
export function inventoryNodes(nodes:Snapshot['nodes']):Snapshot['nodes'];
