import type {Connection} from './types';
export type CheckpointSnapshot={running:boolean;order_control?:{enabled:boolean;status:string}|null};
export function checkpointCommand(snapshot:CheckpointSnapshot|null|undefined,state:{busy:string|boolean;connection:Connection}):'step'|null;
export function orderMutationFields(kind:string,fields?:Record<string,unknown>):Record<string,unknown>;
