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
from logiroute.dispatch.deadlines import hard_deadline


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
        self._order_control_enabled=False; self._order_version=0; self._planned_order_version=None
        self._order_control_status='idle'; self._order_control_reason=None; self._order_change_kind=None
        self._planning_impact=None; self._plan_arrivals={}; self._applied_order_statuses={}
        self._last_attempt=None; self._last_attempt_order_version=None; self._last_attempt_at=None
        self._initial_positions=dict(state.positions); self._initial_locations=dict(state.locations)
        self._initial_orders=dict(state.orders)

    @property
    def running(self) -> bool:
        return any(a is not None for a in self.current.values())

    @property
    def auto_replan_enabled(self) -> bool:
        return self._order_control_enabled

    def enable_auto_replan(self) -> None:
        """Opt in without changing physical state or a pending plan. Time/Space O(1)."""
        self._order_control_enabled=True

    def _request_auto_replan(self,kind: str) -> None:
        """Stop successors, retaining entered atomic actions. Time/Space O(K)."""
        if not self._order_control_enabled:return
        if not self._pausing:self.pause()
        self._order_control_status='waiting_checkpoint';self._order_change_kind=kind
        self._order_control_reason='订单或路况已变化，等待已进入动作完成后自动重规划'
        if 'studio' in self.state.config:self._studio_auto_replan_status=self._order_control_reason

    def _order_changed(self,kind: str) -> None:
        """Version input changes, not delivery progress. Time/Space O(K) when enabled."""
        self._order_version+=1
        self._request_auto_replan(kind)

    def process_auto_replan(self) -> None:
        """Try once at a checkpoint, never depart or discard an unsafe mutation.

        Time O(planner + validator); Space O(plan). Only actual action completion
        can make running false. A blocked attempt waits for a new mutation/manual plan.
        """
        if not self._order_control_enabled or self._order_control_status!='waiting_checkpoint' or self.running:return
        proposal=self.prepare(self.plan.objective if self.plan else 'distance')
        self._last_attempt=proposal; self._last_attempt_order_version=self._order_version; self._last_attempt_at=self.state.now
        if proposal.report.valid and proposal.report.safe_to_apply:
            self.apply(proposal)
            self._order_control_reason='已自动独立验证并应用续程；等待确认继续配送'
        else:
            self._order_control_status='blocked'
            details=','.join(proposal.report.violations)
            self._order_control_reason='无法安全应用自动续程，车辆保持停靠，订单与载货已保留'+('：'+details if details else '')
        if 'studio' in self.state.config:self._studio_auto_replan_status=self._order_control_reason

    def prepare(self,objective: str) -> Plan:
        """Pure proposal at checkpoint; O(planner)."""
        if self.running: raise ConflictError('pause and finish entered atomic actions before replanning')
        return plan_dispatch(self.state,objective)

    def apply(self,plan: Plan) -> None:
        """Independent validation before all mutations; O(validator)."""
        if self.running or plan.fingerprint!=self.state.fingerprint(): raise ConflictError('stale plan/checkpoint required')
        report=validate_plan(self.state,plan)
        if not report.valid or not report.safe_to_apply: raise ValueError('unsafe plan: '+','.join(report.violations))
        from logiroute.dispatch.insights import actual_arrivals,build_impact
        self._planning_impact=build_impact(self.state,self.plan,plan,self.events,self._applied_order_statuses)
        self._plan_arrivals=actual_arrivals(self)
        self.plan=replace(plan,report=report); assigned=dict(plan.assignments)
        self._last_attempt=self.plan; self._last_attempt_order_version=self._order_version; self._last_attempt_at=self.state.now
        for key in plan.accepted:
            o=self.state.orders[key]
            hub = '' if self.state.config.get('single_vehicle') else assigned[key]
            self.state.orders[key]=replace(o,hub=hub,status='planned' if o.status=='pending' else o.status)
        self.state.protected.update(plan.accepted)
        self._applied_order_statuses={key:order.status for key,order in self.state.orders.items()}
        self._programs={r.vehicle:list(r.actions) for r in plan.routes}; self._ready=True; self._pausing=False
        self._planned_order_version=self._order_version
        if self._order_control_enabled:self._order_control_status='applied';self._order_control_reason=None
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
                self.state.locations[oid]=('vehicle',key)
                if self.state.orders[oid].status not in ('cancelled','expired'):
                    self.state.orders[oid]=replace(self.state.orders[oid],status='in_transit')
        elif a.kind=='unload':
            for oid in a.ids:
                if self.state.locations[oid]!=('vehicle',key): raise ValueError('unload inventory conflict')
                self.state.locations[oid]=('hub',a.target)
        elif a.kind=='deliver':
            for oid in a.ids:
                if self.state.locations[oid]!=('vehicle',key) or (a.end>self.state.orders[oid].deadline and hard_deadline(self.state.config,self.state.orders[oid].priority,self.state.orders[oid].allow_late)): raise ValueError('signoff conflict')
                self.state.locations[oid]=('delivered',oid); self.state.orders[oid]=replace(self.state.orders[oid],status='delivered'); self.state.protected.discard(oid)
        elif a.kind=='return_cancelled':
            for oid in a.ids:
                if self.state.locations[oid]!=('vehicle',key) or self.state.orders[oid].status not in ('cancelled','expired'):
                    raise ValueError('cancelled return inventory conflict')
                self.state.locations[oid]=('returned',a.target)
        self.events.append({'kind':'action','time':a.end,'action':a})
        self.current[key]=None; self._enter(key); self.state.revision+=1

    def add_order(self,key: str,destination: str,demand: Decimal | int | float,earliest: float,deadline: float,priority: str,*,allow_late: bool = False) -> None:
        if key in self.state.orders: raise ValueError('order ID already used')
        if self.state.graph.get_node(destination).node_type is not NodeType.CUSTOMER: raise ValueError('customer destination required')
        if 'candidate_ids' in self.state.config and destination not in self.state.config['candidate_ids']: raise ValueError('destination must be a candidate stop')
        if any(isinstance(x,bool) or not isinstance(x,(int,float,Decimal)) for x in (earliest,deadline)): raise ValueError('numeric times required')
        if priority == 'critical' and self.state.config.get('single_vehicle'):
            allow_late = False
        order=Parcel(key,destination,demand,float(earliest),float(deadline),priority,allow_late=allow_late)
        if self.state.config.get('operational_window_mode')=='rush' and priority in ('critical','urgent'):
            start_limit=10 if priority=='critical' else 15
            length_limit=15 if priority=='critical' else 20
            if earliest<self.state.now or earliest-self.state.now>=start_limit or deadline-earliest>=length_limit:
                raise ValueError('rush order window opening or length exceeds priority limit')
        if deadline<=self.state.now and not allow_late: raise ValueError('deadline is not in the future')
        self.state.orders[key]=order; location=('warehouse',self.state.config['warehouse_ids'][0]); self.state.locations[key]=location
        self.events.append({'kind':'create','time':self.state.now,'order':order,'location':location}); self.state.revision+=1
        self._order_changed('add')

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
            earliest=self.state.now;deadline=earliest+float(self.state.config['automatic_window_width'])
            if self.state.config.get('operational_window_mode')=='rush':
                length=self.state.config['rush_window_lengths_minutes'][priority]
                start=self.state.config['rush_earliest_offsets_minutes'][priority]
                earliest=self.state.now+rng.randint(*start);deadline=earliest+rng.randint(*length)
            self.add_order(key,rng.choice(customers),rng.choice(self.state.config['demand_choices']),earliest,
                           deadline,priority,allow_late=priority=='critical' and self.state.config.get('operational_window_mode')=='rush')
        if self._order_control_enabled:self._order_change_kind='automatic'

    def cancel(self,key: str,*,expired: bool = False) -> None:
        order=self.state.orders[key]
        if order.status in ('delivered','cancelled','expired') or self.state.locations[key][0]!='warehouse' or any(a and a.kind=='load' and key in a.ids for a in self.current.values()): raise ConflictError('cannot cancel terminal or entered cargo')
        self.pause(); self.state.orders[key]=replace(order,status='expired' if expired else 'cancelled'); self.state.protected.discard(key)
        self.events.append({'kind':'cancel','time':self.state.now,'id':key,'status':self.state.orders[key].status})
        self._order_changed('expire' if expired else 'cancel')

    def remove_order(self,key: str) -> None:
        """Cancel an unfinished order; loaded goods return to the vehicle base.

        Entered delivery is irreversible. Other entered actions complete before
        replanning; the return action keeps physical load in the Decimal model.
        Time O(K), Space O(1), excluding the subsequent planner.
        """
        order=self.state.orders[key]
        if order.status in ('delivered','cancelled','expired'):
            raise ConflictError('cannot remove a terminal order')
        if any(a and a.kind=='deliver' and key in a.ids for a in self.current.values()):
            raise ConflictError('signoff has already started; this order cannot be removed')
        self.pause();self.state.orders[key]=replace(order,status='cancelled');self.state.protected.discard(key)
        self.events.append({'kind':'cancel','time':self.state.now,'id':key,'status':'cancelled'})
        self._order_changed('cancel')

    def priority(self,key: str,value: str) -> None:
        order=self.state.orders[key]
        if self.state.locations[key][0]!='warehouse' or order.status in ('cancelled','expired','delivered') or any(a and a.kind=='load' and key in a.ids for a in self.current.values()): raise ConflictError('priority update requires unentered warehouse order')
        changed=replace(order,priority=value,allow_late=order.allow_late if value=='critical' else False); self.pause(); self.state.orders[key]=changed
        self.events.append({'kind':'priority','time':self.state.now,'id':key,'priority':value})
        self._order_changed('priority')

    def traffic(self,source: str,target: str,status: str) -> None:
        self.network.update(source,target,status); self.state.graph=self.network.snapshot(); self.state.traffic_version=self.network.version; self.pause()
        self.events.append({'kind':'traffic','time':self.state.now,'source':source,'target':target,'status':status,'version':self.network.version})
        self._request_auto_replan('traffic')

    def audit(self) -> Report:
        from logiroute.dispatch.audit import audit_session
        return audit_session(self)

    def snapshot(self) -> dict[str,Any]:
        """Versioned JSON boundary; quantities serialized only here. O(V+E+A+N)."""
        state=self.state
        from logiroute.dispatch.insights import planning_insights
        nodes=[{'id':n.id,'type':'junction' if n.metadata.get('routing_only') else n.node_type.value,'x':n.x,'y':n.y,'name':n.name,**n.metadata} for n in state.graph.nodes]
        edges=[{'source':e.source_id,'target':e.target_id,'distance':e.distance,'travel_time':e.travel_time,'cost':e.cost,'status':e.traffic_status.value,**e.metadata} for e in state.graph.edges]
        cars=[]
        for k,v in state.vehicles.items():
            cargo=[oid for oid,loc in state.locations.items() if loc==('vehicle',k)]
            cars.append({**json_value(v),'position':state.positions[k],'current':json_value(self.current[k]),'cargo':cargo,'load':str(exact_sum(state.orders[o].demand for o in cargo))})
        studio={}
        if 'studio' in state.config:
            from logiroute.dispatch.studio import metrics
            studio={'studio':metrics(self)}
        return {**studio,'schema_version':SCHEMA,'revision':state.revision,'traffic_version':state.traffic_version,'now':state.now,
                **({'single_vehicle':True} if state.config.get('single_vehicle') else {}),
                'planning_insights':planning_insights(self),
                'order_control':{'enabled':self._order_control_enabled,'order_version':self._order_version,
                                 'planned_order_version':self._planned_order_version,'status':self._order_control_status,
                                 'reason':self._order_control_reason,'change_kind':self._order_change_kind},
                'running':self.running,'ready':self._ready,'needs_replan':self._pausing,'nodes':nodes,'edges':edges,'vehicles':cars,
                'orders':[{**json_value(o),'location':list(state.locations[k])} for k,o in state.orders.items()],
                'events':json_value(self.events),'plan':None if self.plan is None else self.plan.to_dict(),
                'audit':json_value(self.audit()),'settings':{'automatic_window_width':float(state.config['automatic_window_width']),
                                                             **({'simulated_traffic':state.config['simulated_traffic']} if 'simulated_traffic' in state.config else {})},
                **({'time_windows':state.config['window_evidence']} if 'window_evidence' in state.config else {}),
                **({'map':state.config['map']} if 'map' in state.config else {})}
