export function acceptSnapshot<T extends {id: string; revision: number}>(current: T | null, incoming: T, activeId: string): T | null;
import type {Snapshot,Plan,Action,Comparison} from './types';
export function bindComparison(snapshot:Snapshot,plans:Plan[]):Comparison|null;
export function reconcileSnapshot(current:Snapshot|null,comparison:Comparison|null,incoming:Snapshot,activeId:string):{snapshot:Snapshot|null;comparison:Comparison|null};
export function actionPhase(snapshot:Snapshot,action:Action):'current'|'completed'|'paused'|'pending'|'unknown';
