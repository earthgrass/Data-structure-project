export type Action = {vehicle:string; kind:string; start:number; end:number; source:string; target:string; ids:string[]; distance:number; cost:number};
export type Report = {valid:boolean;complete_all:boolean;safe_to_apply:boolean;violations:string[]};
export type Plan = {objective:string;fingerprint:string;accepted:string[];deferred:[string,string][];report:Report;total_distance:number;total_cost:number;routes:{vehicle:string;actions:Action[];total_distance:number;total_cost:number;end_time:number}[]};
export type Snapshot = {
  id:string;revision:number;traffic_version:number;now:number;running:boolean;ready:boolean;needs_replan:boolean;
  nodes:{id:string;type:string;x:number;y:number}[];
  edges:{source:string;target:string;distance:number;travel_time:number;cost:number;status:string}[];
  vehicles:{id:string;courier_id:string;role:string;base:string;capacity:string;position:string;current:Action|null;cargo:string[];load:string}[];
  orders:{id:string;destination:string;demand:string;earliest:number;deadline:number;priority:string;status:string;hub:string;location:[string,string]}[];
  plan:Plan|null;audit:Report;comparison?:Plan[];
  events:{kind:string;time:number;action?:Action;id?:string;status?:string;priority?:string}[];
  settings:{automatic_window_width:number};
};
