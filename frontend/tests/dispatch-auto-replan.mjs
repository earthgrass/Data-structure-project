import assert from 'node:assert/strict';
import {checkpointCommand,orderMutationFields} from '../src/dispatch/auto-replan.mjs';

let assertions=0;
const equal=(actual,expected)=>{assert.deepEqual(actual,expected);assertions++;};
const available={busy:'',connection:'connected'};
const waiting={running:true,order_control:{enabled:true,status:'waiting_checkpoint',order_version:2,planned_order_version:1}};
const before=JSON.stringify(waiting);
equal(checkpointCommand(waiting,available),'step');
equal(checkpointCommand(null,available),null);
equal(checkpointCommand(undefined,available),null);
equal(checkpointCommand({running:true},available),null);
equal(checkpointCommand({...waiting,order_control:null},available),null);
equal(checkpointCommand({...waiting,running:false},available),null);
equal(checkpointCommand({...waiting,running:'true'},available),null);
equal(checkpointCommand({...waiting,order_control:{...waiting.order_control,enabled:false}},available),null);
equal(checkpointCommand({...waiting,order_control:{...waiting.order_control,enabled:'true'}},available),null);
for(const connection of ['connecting','failed','missing','unexpected']){
 equal(checkpointCommand(waiting,{busy:'',connection}),null);
}
for(const busy of ['step','add','plan',true])equal(checkpointCommand(waiting,{busy,connection:'connected'}),null);
// A repeated poll of a terminal workflow never restarts planning or departs.
for(const status of ['idle','applied','blocked','unknown']){
 const snapshot={...waiting,ready:true,order_control:{...waiting.order_control,status}};
 equal([checkpointCommand(snapshot,available),checkpointCommand({...snapshot},available)],[null,null]);
}
equal(JSON.stringify(waiting),before);

const fields=Object.freeze({id:'URGENT',demand:'0.10000000000000000000001',auto_replan:false});
for(const kind of ['add','automatic','cancel','expire','priority','traffic']){
 equal(orderMutationFields(kind,fields),{...fields,auto_replan:true});
}
equal(fields.auto_replan,false);
equal(orderMutationFields('add'),{auto_replan:true});
for(const kind of ['step','depart','pause','plan','compare','unknown']){
 equal(orderMutationFields(kind,fields),fields);
}
equal(orderMutationFields('step'),{});
console.log(`${assertions} automatic checkpoint gating, terminal workflow and immutable mutation-field assertions passed`);
