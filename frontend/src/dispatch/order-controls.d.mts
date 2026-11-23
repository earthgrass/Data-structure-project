import type {Snapshot} from './types';
export function cancellationBlockReason(snapshot:Snapshot,order:Snapshot['orders'][number]):string;
export function cancellableOrders(snapshot:Snapshot):Snapshot['orders'];
