"""Explicit event-clock execution; no wall-clock mutation or teleportation."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from typing import Any
from logiroute.core.enums import NodeType
from logiroute.core.quantities import exact_sum
from logiroute.dispatch.models import Parcel,Plan,Action,Report,json_value,SCHEMA
from logiroute.dispatch.scenario import State
from logiroute.dispatch.planner import plan_dispatch
from logiroute.dispatch.traffic import Network
from logiroute.dispatch.validation import validate_plan


class ConflictError(ValueError):
    """Stale revision or an operation requires a physical checkpoint."""


class Session:
    """Private command-owned state. Caller serializes access; API uses a lock.

    Step O(K+N), snapshot O(V+E+A+N). Plans validated independently on application.
    """
    def __init__(self,state: State) -> None:
        self.state=state; self.network=Network(state.graph,state.config['traffic'])
        self.state.graph=self.network.snapshot(); self.events=[]; self.plan=None
        self._programs={k:[] for k in state.vehicles}; self.current={k:None for k in state.vehicles}
        self._pausing=False; self._ready=False; self._auto_counter=0
        self._initial_positions=dict(state.positions); self._initial_locations=dict(state.locations)
        self._initial_orders=dict(state.orders)

    @property
    def running(self) -> bool:
        return any(a is not None for a in self.current.values())

    def prepare(self,objective: str) -> Plan:
        """Pure proposal at checkpoint; O(planner)."""
        if self.running: raise ConflictError('pause and finish entered atomic actions before replanning')
        return plan_dispatch(self.state,objective)

    def apply(self,plan: Plan) -> None:
        """Independent validation before all mutations; O(validator)."""
        if self.running or plan.fingerprint!=self.state.fingerprint(): raise ConflictError('stale plan/checkpoint required')
        report=validate_plan(self.state,plan)
        if not report.valid or not report.safe_to_apply: raise ValueError('unsafe plan: '+','.join(report.violations))
        self.plan=replace(plan,report=report); assigned=dict(plan.assignments)
        for key in plan.accepted:
            o=self.state.orders[key]
            self.state.orders[key]=replace(o,hub=assigned[key],status='planned' if o.status=='pending' else o.status)
        self.state.protected.update(plan.accepted)
        self._programs={r.vehicle:list(r.actions) for r in plan.routes}; self._ready=True; self._pausing=False
        self.events.append({'kind':'plan','time':self.state.now,'accepted':plan.accepted,'objective':plan.objective})
        self.state.revision+=1

    def _enter(self,key: str) -> None:
        if self._pausing or not self._programs[key]: self.current[key]=None; return
        action=self._programs[key].pop(0)
        if action.kind=='drive' and (action.traffic_version!=self.network.version or not self.network.validate_entered_edge(action)):
            self._pausing=True; self._programs={k:[] for k in self._programs}; self.current[key]=None; return
        self.current[key]=action

    def depart(self) -> None:
        if self.running or not self._ready: raise ConflictError('no applied plan ready to depart')
        self._ready=False
        for key in self.current: self._enter(key)
        self.state.revision+=1

    def pause(self) -> None:
        """Finish only entered drive/load/unload/service; waits can stop now. O(K)."""
        self._pausing=True; self._ready=False; self._programs={k:[] for k in self._programs}
        for key,a in self.current.items():
            if a is not None and a.kind in ('wait','finish'): self.current[key]=None
        self.state.revision+=1

    def step(self) -> None:
        """Complete earliest entered atomic action, then enter its successor. O(K+N)."""
        if not self.running: raise ConflictError('no active action')
        earliest=min(a.end for a in self.current.values() if a is not None)
        eligible=[]
        for k,a in self.current.items():
            if a is None or a.end!=earliest: continue
            car=self.state.vehicles[k]; source=('warehouse' if car.role=='trunk' else 'hub',car.base)
            if a.kind!='load' or all(self.state.locations[o]==source for o in a.ids): eligible.append(k)
        if not eligible: raise ConflictError('no causal action can release inventory at this timestamp')
        key=min(eligible)
        a=self.current[key]; self.state.now=max(self.state.now,a.end)
        if a.kind=='drive':
            if not self.network.validate_entered_edge(a): raise ValueError('entered edge evidence mismatch')
            self.state.positions[key]=a.target
        elif a.kind=='load':
            car=self.state.vehicles[key]; source=('warehouse' if car.role=='trunk' else 'hub',car.base)
            if any(self.state.locations[k]!=source for k in a.ids): raise ValueError('inventory conflict')
            for oid in a.ids:
                self.state.locations[oid]=('vehicle',key); self.state.orders[oid]=replace(self.state.orders[oid],status='in_transit')
        elif a.kind=='unload':
            for oid in a.ids:
                if self.state.locations[oid]!=('vehicle',key): raise ValueError('unload inventory conflict')
                self.state.locations[oid]=('hub',a.target)
        elif a.kind=='deliver':
            for oid in a.ids:
                if self.state.locations[oid]!=('vehicle',key) or a.end>self.state.orders[oid].deadline: raise ValueError('signoff conflict')
                self.state.locations[oid]=('delivered',oid); self.state.orders[oid]=replace(self.state.orders[oid],status='delivered'); self.state.protected.discard(oid)
        self.events.append({'kind':'action','time':a.end,'action':a})
        self.current[key]=None; self._enter(key); self.state.revision+=1

    def add_order(self,key: str,destination: str,demand: Decimal | int | float,earliest: float,deadline: float,priority: str) -> None:
        if key in self.state.orders: raise ValueError('order ID already used')
        if self.state.graph.get_node(destination).node_type is not NodeType.CUSTOMER: raise ValueError('customer destination required')
        if 'candidate_ids' in self.state.config and destination not in self.state.config['candidate_ids']: raise ValueError('destination must be a candidate stop')
        if any(isinstance(x,bool) or not isinstance(x,(int,float,Decimal)) for x in (earliest,deadline)): raise ValueError('numeric times required')
        order=Parcel(key,destination,demand,float(earliest),float(deadline),priority)
        if deadline<=self.state.now: raise ValueError('deadline is not in the future')
        self.state.orders[key]=order; location=('warehouse',self.state.config['warehouse_ids'][0]); self.state.locations[key]=location
        self.events.append({'kind':'create','time':self.state.now,'order':order,'location':location}); self.state.revision+=1

    def automatic(self,count: int,seed: int,priority: str = 'normal') -> None:
        from logiroute.scenario_generator.random_source import RandomSource
        from logiroute.algorithms.ordering import ordered_strings
        if isinstance(count,bool) or not isinstance(count,int) or count<1: raise ValueError('positive count required')
        if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('integer seed required')
        rng=RandomSource(seed); customers=ordered_strings(self.state.config.get('candidate_ids',[n.id for n in self.state.graph.nodes if n.node_type is NodeType.CUSTOMER]))
        # Validate before mutations; generated IDs never reuse cancelled identities.
        if priority not in ('critical','urgent','normal'): raise ValueError('invalid priority')
        for _ in range(count):
            while True:
                self._auto_counter+=1; key=self.state.config['dynamic_prefix']+str(self._auto_counter)
                if key not in self.state.orders: break
            self.add_order(key,rng.choice(customers),rng.choice(self.state.config['demand_choices']),self.state.now,
                           self.state.now+float(self.state.config['automatic_window_width']),priority)

    def cancel(self,key: str,*,expired: bool = False) -> None:
        order=self.state.orders[key]
        if order.status in ('delivered','cancelled','expired') or self.state.locations[key][0]!='warehouse' or any(a and a.kind=='load' and key in a.ids for a in self.current.values()): raise ConflictError('cannot cancel terminal or entered cargo')
        self.pause(); self.state.orders[key]=replace(order,status='expired' if expired else 'cancelled'); self.state.protected.discard(key)
        self.events.append({'kind':'cancel','time':self.state.now,'id':key,'status':self.state.orders[key].status})

    def priority(self,key: str,value: str) -> None:
        order=self.state.orders[key]
        if self.state.locations[key][0]!='warehouse' or order.status in ('cancelled','expired','delivered') or any(a and a.kind=='load' and key in a.ids for a in self.current.values()): raise ConflictError('priority update requires unentered warehouse order')
        changed=replace(order,priority=value); self.pause(); self.state.orders[key]=changed
        self.events.append({'kind':'priority','time':self.state.now,'id':key,'priority':value})

    def traffic(self,source: str,target: str,status: str) -> None:
        self.network.update(source,target,status); self.state.graph=self.network.snapshot(); self.state.traffic_version=self.network.version; self.pause()
        self.events.append({'kind':'traffic','time':self.state.now,'source':source,'target':target,'status':status,'version':self.network.version})

    def audit(self) -> Report:
        from logiroute.dispatch.audit import audit_session
        return audit_session(self)

    def snapshot(self) -> dict[str,Any]:
        """Versioned JSON boundary; quantities serialized only here. O(V+E+A+N)."""
        state=self.state
        nodes=[{'id':n.id,'type':'junction' if n.metadata.get('routing_only') else n.node_type.value,'x':n.x,'y':n.y,'name':n.name,**n.metadata} for n in state.graph.nodes]
        edges=[{'source':e.source_id,'target':e.target_id,'distance':e.distance,'travel_time':e.travel_time,'cost':e.cost,'status':e.traffic_status.value,**e.metadata} for e in state.graph.edges]
        cars=[]
        for k,v in state.vehicles.items():
            cargo=[oid for oid,loc in state.locations.items() if loc==('vehicle',k)]
            cars.append({**json_value(v),'position':state.positions[k],'current':json_value(self.current[k]),'cargo':cargo,'load':str(exact_sum(state.orders[o].demand for o in cargo))})
        return {'schema_version':SCHEMA,'revision':state.revision,'traffic_version':state.traffic_version,'now':state.now,
                'running':self.running,'ready':self._ready,'needs_replan':self._pausing,'nodes':nodes,'edges':edges,'vehicles':cars,
                'orders':[{**json_value(o),'location':list(state.locations[k])} for k,o in state.orders.items()],
                'events':json_value(self.events),'plan':None if self.plan is None else self.plan.to_dict(),
                'audit':json_value(self.audit()),'settings':{'automatic_window_width':float(state.config['automatic_window_width'])},
                **({'time_windows':state.config['window_evidence']} if 'window_evidence' in state.config else {}),
                **({'map':state.config['map']} if 'map' in state.config else {})}
