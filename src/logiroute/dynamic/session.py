"""Explicit, single-owner dynamic session with depot-checkpoint replanning.

Planning is isolated from mutable execution. A complete independently validated
proposal replaces the old plan atomically; pending arrivals never teleport cars
or add cargo to a running trip. No background threads, timers or Web dependency.
"""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.algorithms.ordering import ordered_strings
from logiroute.algorithms.order_queue import OrderPriorityQueue
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Order,Vehicle,Courier
from logiroute.core.enums import OrderStatus,OrderPriority,VehicleStatus,CourierStatus,NodeType
from logiroute.core.quantities import Quantity,exact_sum,exact_difference
from logiroute.dynamic.config import DynamicConfig
from logiroute.dynamic.models import (OrderView,VehicleView,DynamicEvent,DynamicSnapshot,
    OrderReceipt,ReplanProposal,ReplanOutcome,DynamicValidationReport)
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.algorithms.dynamic_execution import compile_actions,next_action
from logiroute.scheduling.fleet_paths import freeze_scenario,fingerprint_scenario,finite_time
from logiroute.scheduling.fleet_validator import validate_fleet


class DynamicStateError(ValueError):
    """Invalid input, unsafe checkpoint, stale draft or inconsistent execution."""


def _copy(order: Order) -> Order:
    return Order(order.id,order.destination_id,order.demand_decimal,order.time_window_start,
                 order.time_window_end,order.priority,order.status)


class DynamicSession:
    """One owner; revision checks detect explicit interleaving, not arbitrary data races.

    Storage O(graph + all order/history records + current programs + saved plans).
    Initial input must be fresh: pending/created orders, empty cars at warehouses,
    IDLE/MAINTENANCE vehicles. In-flight reconstruction requires a future persisted
    execution format and is explicitly rejected instead of guessed.
    """
    def __init__(self, scenario: ScenarioBundle, config: DynamicConfig) -> None:
        if not isinstance(config,DynamicConfig): raise ValueError('expected DynamicConfig')
        data=freeze_scenario(scenario)
        self._base=data.bundle; self._config=config; self._config_id=config.fingerprint
        self._vehicles=data.vehicles; self._couriers=data.couriers
        self._homes={key:v.current_node_id for key,v in self._vehicles.items()}
        for v in self._vehicles.values():
            if (v.current_load_decimal!=0 or v.status not in (VehicleStatus.IDLE,VehicleStatus.MAINTENANCE)
                    or self._base.graph.get_node(v.current_node_id).node_type is not NodeType.WAREHOUSE):
                raise DynamicStateError('initial execution context must be empty at a warehouse')
        if any(c.status is CourierStatus.DELIVERING for c in self._couriers.values()):
            raise DynamicStateError('initial courier is already executing')
        self._clock=finite_time(data.initial_time,'initial_time',nonnegative=True)
        self._revision=0; self._next_id=1
        self._orders={}; self._sources={}; self._queue=OrderPriorityQueue()
        self._events=[]; self._history=[]; self._plan=None; self._committed_input=None
        self._programs={}; self._cursors={}; self._onboard={}; self._needs_replan=False
        customers={n.id for n in self._base.graph.nodes if n.node_type is NodeType.CUSTOMER}
        if any(key not in customers for key in config.automatic.destination_ids):
            raise ValueError('automatic destination is not a customer')
        for order in data.orders.values(): self.submit(order,source='initial')

    def _event(self, kind: str, **values) -> DynamicEvent:
        event=DynamicEvent(len(self._events)+1,self._clock,kind,**values)
        self._events.append(event)
        return event

    def _fresh_id(self) -> tuple[str,int]:
        index=self._next_id
        while f'{self._config.order_id_prefix}{index}' in self._orders: index+=1
        return f'{self._config.order_id_prefix}{index}',index

    def submit(self, order: Order, *, source: str = 'manual', source_seed: int | None = None) -> OrderReceipt:
        """Unified initial/manual/automatic admission.

        Time O(K²+K*(V+E)log V+Q+D); auxiliary Space O(V+E+K+D).

        Acceptance means QUEUED, not assigned or guaranteed jointly feasible.
        Original objects never become queue-owned references. Validation completes
        before publication; terminal IDs remain reserved for the entire session.
        """
        if source not in ('initial','manual','automatic') or not isinstance(order,Order):
            raise ValueError('invalid order/source')
        if ((source=='automatic' and (isinstance(source_seed,bool) or not isinstance(source_seed,int)))
                or (source!='automatic' and source_seed is not None)):
            raise ValueError('automatic admission requires its explicit integer seed')
        item=_copy(order)
        finite_time(item.time_window_start,'time_window_start')
        finite_time(item.time_window_end,'time_window_end')
        if item.id in self._orders: raise DynamicStateError('duplicate order id')
        if item.status is OrderStatus.CREATED: item.transition_to(OrderStatus.PENDING)
        if item.status is not OrderStatus.PENDING: raise DynamicStateError('intake requires pending/created')
        node=self._base.graph.try_get_node(item.destination_id)
        if node is None or node.node_type is not NodeType.CUSTOMER:
            raise DynamicStateError('destination must be an existing customer')
        if item.time_window_end<self._clock: raise DynamicStateError('deadline already passed')
        compatible=[]
        for key in ordered_strings(self._vehicles):
            vehicle=self._vehicles[key]
            if (vehicle.status is not VehicleStatus.MAINTENANCE
                    and self._couriers[key].status not in (CourierStatus.OFFLINE,CourierStatus.RESTING)
                    and item.demand_decimal<=vehicle.capacity_decimal):
                compatible.append(key)
        if not compatible: raise DynamicStateError('no eligible vehicle fits the individual demand')
        reachable=False
        for key in compatible:
            home=self._homes[key]
            if (shortest_path(self._base.graph,home,item.destination_id,'distance').reachable
                    and shortest_path(self._base.graph,item.destination_id,home,'distance').reachable):
                reachable=True; break
        if not reachable: raise DynamicStateError('no reachable round trip for individual order')
        self._queue.enqueue(item)
        self._orders[item.id]=item; self._sources[item.id]=source
        self._revision+=1; self._needs_replan=True
        self._event('accepted',order_id=item.id,quantity=item.demand_decimal,detail=source,seed=source_seed)
        return OrderReceipt(item.id,source)

    def submit_manual(self, destination_id: str, demand: Quantity, time_window_start: float,
                      time_window_end: float, *, priority: OrderPriority = OrderPriority.NORMAL,
                      order_id: str | None = None) -> OrderReceipt:
        """Build then use unified intake; ID counter advances only on success. Same cost as submit."""
        generated,index=self._fresh_id()
        receipt=self.submit(Order(generated if order_id is None else order_id,destination_id,
                                  demand,time_window_start,time_window_end,priority),source='manual')
        if order_id is None: self._next_id=index+1
        return receipt

    def submit_automatic(self, *, seed: int) -> OrderReceipt:
        """One seeded explicit event, never a background loop. Same cost as submit."""
        if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('seed must be an integer')
        rng=RandomSource(seed); a=self._config.automatic
        destinations=a.destination_ids or tuple(ordered_strings(
            n.id for n in self._base.graph.nodes if n.node_type is NodeType.CUSTOMER))
        if not destinations: raise ValueError('no automatic destinations')
        destination=rng.choice(destinations); demand=rng.choice(a.demand_choices)
        priority=OrderPriority.URGENT if rng.uniform(0,1)<a.urgent_fraction else OrderPriority.NORMAL
        start=finite_time(self._clock+rng.uniform(*a.window_delay_range),'window_start')
        end=finite_time(start+rng.uniform(*a.window_width_range),'window_end')
        oid,index=self._fresh_id()
        receipt=self.submit(Order(oid,destination,demand,start,end,priority),source='automatic',source_seed=seed)
        self._next_id=index+1
        return receipt

    def order(self, order_id: str) -> OrderView:
        """Immutable single-order observation. O(1), excluding scalar digits."""
        if order_id not in self._orders: raise DynamicStateError('unknown order')
        o=self._orders[order_id]
        return OrderView(o.id,o.destination_id,o.demand_decimal,o.time_window_start,
                         o.time_window_end,o.priority,o.status,self._sources[o.id])

    def next_pending(self) -> OrderView | None:
        """No invalid-head cleanup or lifecycle side effects; O(1)."""
        return None if self._queue.is_empty() else self.order(self._queue.peek_next().id)

    def update_pending(self, order_id: str, *, priority: OrderPriority | None = None,
                       time_window_end: float | None = None) -> None:
        """Validate copy, remove original, replace and re-enqueue; O(Q), no stale keys."""
        old=self._orders.get(order_id)
        if old is None or old.status is not OrderStatus.PENDING:
            raise DynamicStateError('only pending orders can be updated')
        if priority is None and time_window_end is None: raise ValueError('no update supplied')
        new=Order(old.id,old.destination_id,old.demand_decimal,old.time_window_start,
                  old.time_window_end if time_window_end is None else time_window_end,
                  old.priority if priority is None else priority)
        finite_time(new.time_window_end,'time_window_end')
        if new.time_window_end<self._clock: raise ValueError('updated deadline already passed')
        self._queue.remove(order_id)
        self._orders[order_id]=new; self._queue.enqueue(new)
        self._revision+=1; self._needs_replan=True; self._event('updated',order_id=order_id)

    def _terminal(self, order_id: str, status: OrderStatus) -> None:
        old=self._orders.get(order_id)
        if old is None or old.status not in (OrderStatus.PENDING,OrderStatus.PLANNED):
            raise DynamicStateError('cannot cancel/expire this order state')
        if status is OrderStatus.EXPIRED and self._clock<=old.time_window_end:
            raise DynamicStateError('expiry is explicit and requires a passed deadline')
        updated=dict(self._orders); item=_copy(old); item.transition_to(status); updated[order_id]=item
        withdraw=old.status is OrderStatus.PLANNED
        if withdraw:
            for key,value in updated.items():
                if value.status is OrderStatus.PLANNED:
                    value=_copy(value); value.transition_to(OrderStatus.PENDING); updated[key]=value
        queue=OrderPriorityQueue()
        for value in updated.values():
            if value.status is OrderStatus.PENDING: queue.enqueue(value)
        self._orders=updated; self._queue=queue
        if withdraw: self._plan=None; self._committed_input=None
        self._needs_replan=(not queue.is_empty() or (self._plan is not None
                            and any(r.departure_time!=self._clock for r in self._plan.routes)))
        self._revision+=1
        self._event(status.value,order_id=order_id,detail='plan_withdrawn' if withdraw else '')

    def cancel(self, order_id: str) -> None:
        """Explicit cancellation; Time O(N+M*D+Q²), Space O(N+Q+M*D)."""
        self._terminal(order_id,OrderStatus.CANCELLED)

    def expire(self, order_id: str) -> None:
        """Explicit expiry; Time O(N+M*D+Q²), Space O(N+Q+M*D); no timer."""
        self._terminal(order_id,OrderStatus.EXPIRED)

    def _candidate(self) -> ScenarioBundle:
        if self._programs: raise DynamicStateError('unsafe checkpoint: execution in progress')
        for key,v in self._vehicles.items():
            if (v.current_node_id!=self._homes[key] or v.current_load_decimal!=0
                    or v.status not in (VehicleStatus.IDLE,VehicleStatus.MAINTENANCE)):
                raise DynamicStateError('unsafe checkpoint: vehicle is not empty at its home')
        orders=[]
        for old in self._orders.values():
            if old.status in (OrderStatus.PENDING,OrderStatus.PLANNED):
                item=_copy(old)
                if item.status is OrderStatus.PLANNED: item.transition_to(OrderStatus.PENDING)
                orders.append(item)
        source=ScenarioBundle(f'{self._base.name}.{self._config.name}.revision{self._revision}',
            'fixed',self._base.random_seed,self._base.graph,list(self._vehicles.values()),
            list(self._couriers.values()),orders,
            {'initial_time':self._clock,'service_time':self._base.simulation['service_time']})
        return freeze_scenario(source).bundle

    def prepare_replan(self, objective: str | None = None) -> ReplanProposal:
        """Isolated draft; no state changes. Cost: static planner + snapshots."""
        revision=self._revision; candidate=self._candidate(); before=fingerprint_scenario(candidate)
        mode=self._config.default_objective if objective is None else objective
        answer=plan_fleet(candidate,mode)
        if fingerprint_scenario(candidate)!=before or self._revision!=revision:
            raise DynamicStateError('input changed during planning')
        return ReplanProposal(revision,before,mode,answer)

    def commit_replan(self, proposal: ReplanProposal) -> ReplanOutcome:
        """Independent full verification and atomic publish; partial drafts preserve old plan.

        Time: independent fleet validation + O(N+Q²); Space: draft/current records.
        A revision mismatch rejects a previously computed draft without changing state.
        """
        if not isinstance(proposal,ReplanProposal) or proposal.base_revision!=self._revision:
            raise DynamicStateError('stale or invalid proposal')
        candidate=self._candidate()
        if fingerprint_scenario(candidate)!=proposal.input_fingerprint:
            raise DynamicStateError('proposal input mismatch')
        report=validate_fleet(candidate,proposal.result,objective=proposal.objective)
        if not report.valid: raise DynamicStateError('independent replan validation failed: '+str(report.violations))
        if not report.complete:
            self._event('replan_incomplete')
            return ReplanOutcome('incomplete',replace(proposal.result,validation=report))
        updated=dict(self._orders)
        for old in candidate.orders:
            item=_copy(self._orders[old.id])
            if item.status is OrderStatus.PLANNED: item.transition_to(OrderStatus.PENDING)
            item.transition_to(OrderStatus.PLANNED); updated[item.id]=item
        self._orders=updated; self._queue=OrderPriorityQueue()
        self._plan=replace(proposal.result,validation=report); self._committed_input=candidate
        self._history.append(self._plan); self._needs_replan=False; self._revision+=1
        self._event('plan_applied',detail=self._plan.objective,
                    order_ids=tuple(o.id for o in candidate.orders))
        return ReplanOutcome('applied',self._plan)

    def replan(self, objective: str | None = None) -> ReplanOutcome:
        """Explicit request; active trips defer and retain pending jobs. Planner cost otherwise."""
        mode=self._config.default_objective if objective is None else objective
        if mode not in ('distance','cost'): raise ValueError('objective must be distance or cost')
        if self._programs:
            self._event('replan_deferred',detail=mode)
            return ReplanOutcome('deferred')
        return self.commit_replan(self.prepare_replan(mode))

    def depart(self) -> int:
        """Load committed tasks at depot and launch together; O(validation+program records).

        Queued arrivals not in the old plan remain pending. The caller may execute
        that retained valid plan after a failed replan; no new cargo is invented.
        """
        if self._programs or self._plan is None: raise DynamicStateError('no dispatchable committed plan')
        plan=self._plan
        if any(r.departure_time!=self._clock for r in plan.routes):
            raise DynamicStateError('departure time changed; replan required')
        report=validate_fleet(self._committed_input,plan)
        if not report.valid or not report.complete: raise DynamicStateError('invalid departure plan')
        vehicles=dict(self._vehicles); couriers=dict(self._couriers); orders=dict(self._orders)
        programs={}; onboard={}
        for route in plan.routes:
            if not route.services: continue
            key=route.vehicle_id; v=vehicles[key]; c=couriers[key]
            if (v.current_node_id!=route.depot_id or v.current_load_decimal!=0
                    or v.status is not VehicleStatus.IDLE or c.status is not CourierStatus.IDLE):
                raise DynamicStateError('vehicle/courier cannot depart')
            ids=route.served_order_ids
            for oid in ids:
                item=_copy(orders[oid]); item.transition_to(OrderStatus.IN_TRANSIT); orders[oid]=item
            load=exact_sum(orders[oid].demand_decimal for oid in ids)
            vehicles[key]=Vehicle(v.id,v.capacity_decimal,load,v.current_node_id,VehicleStatus.DELIVERING)
            couriers[key]=Courier(c.id,c.name,key,CourierStatus.DELIVERING)
            programs[key]=compile_actions(route); onboard[key]=ids
        self._orders=orders; self._vehicles=vehicles; self._couriers=couriers
        self._programs=programs; self._cursors={key:0 for key in programs}; self._onboard=onboard
        self._plan=None; self._committed_input=None; self._revision+=1
        for key in ordered_strings(programs):
            self._event('depart',vehicle_id=key,quantity=vehicles[key].current_load_decimal,
                        source_node=self._homes[key],target_node=self._homes[key],order_ids=onboard[key])
        self._needs_replan=not self._queue.is_empty()
        return len(programs)

    def step(self) -> DynamicEvent | None:
        """Execute one earliest scheduled arrival/wait/service/return. O(K+N+D).

        Business time only advances by real route actions; no sleep or elapsed-wall
        clock. Per-car route cursor fixes its prefix, and IDs unload exactly once.
        """
        upcoming=next_action(self._programs,self._cursors)
        if upcoming is None: return None
        key,action=upcoming; v=self._vehicles[key]; c=self._couriers[key]
        if action.time<self._clock or v.current_node_id!=action.source_node:
            raise DynamicStateError('execution cursor/time/location invariant violated')
        vehicle=v; courier=c; item=None; remaining=self._onboard[key]; quantity=Decimal(0)
        if action.kind=='travel':
            vehicle=Vehicle(v.id,v.capacity_decimal,v.current_load_decimal,action.target_node,v.status)
        elif action.kind=='service':
            old=self._orders[action.order_id]
            if (old.status is not OrderStatus.IN_TRANSIT or old.id not in remaining
                    or old.destination_id!=v.current_node_id
                    or not old.time_window_start<=action.start_time<=old.time_window_end):
                raise DynamicStateError('invalid service identity/window/cargo')
            quantity=old.demand_decimal; load=exact_difference(v.current_load_decimal,quantity)
            remaining=tuple(oid for oid in remaining if oid!=old.id)
            item=_copy(old); item.transition_to(OrderStatus.DELIVERED)
            vehicle=Vehicle(v.id,v.capacity_decimal,load,v.current_node_id,
                            VehicleStatus.DELIVERING if remaining else VehicleStatus.RETURNING)
        elif action.kind=='finish':
            if remaining or v.current_load_decimal!=0 or v.current_node_id!=self._homes[key]:
                raise DynamicStateError('return is not empty at home')
            vehicle=Vehicle(v.id,v.capacity_decimal,Decimal(0),v.current_node_id,VehicleStatus.IDLE)
            courier=Courier(c.id,c.name,key,CourierStatus.IDLE)
        self._clock=action.time; self._vehicles[key]=vehicle; self._couriers[key]=courier
        if item is not None: self._orders[item.id]=item
        self._onboard[key]=remaining; self._cursors[key]+=1; self._revision+=1
        if action.kind=='finish':
            del self._programs[key]; del self._cursors[key]
        self._needs_replan=not self._queue.is_empty()
        return self._event(action.kind,order_id=action.order_id,vehicle_id=key,
                           start_time=action.start_time,source_node=action.source_node,
                           target_node=action.target_node,path=action.path,distance=action.distance,
                           travel_time=action.travel_time,cost=action.cost,quantity=quantity)

    def advance_to(self, time: float) -> None:
        """Process all due events then advance business time. O(events*(K+N+D))."""
        target=finite_time(time,'time',nonnegative=True)
        if target<self._clock: raise ValueError('time cannot go backwards')
        while True:
            upcoming=next_action(self._programs,self._cursors)
            if upcoming is None or upcoming[1].time>target: break
            self.step()
        if target>self._clock:
            self._clock=target; self._revision+=1; self._event('clock_advanced')
            self._needs_replan=(not self._queue.is_empty() or (self._plan is not None
                                and any(r.departure_time!=self._clock for r in self._plan.routes)))

    def snapshot(self) -> DynamicSnapshot:
        """Immutable observation including last confirmed node and in-flight path.

        O(N²+K²+events+plan records) including handwritten ordering; no dispatch.
        """
        vehicles=[]
        for key in ordered_strings(self._vehicles):
            v=self._vehicles[key]; c=self._couriers[key]
            action=self._programs[key][self._cursors[key]] if key in self._programs else None
            vehicles.append(VehicleView(v.id,c.id,self._homes[key],v.current_node_id,
                v.capacity_decimal,v.current_load_decimal,v.status,c.status,
                self._onboard.get(key,()),'' if action is None else action.kind,
                self._clock if action is None else action.start_time,
                self._clock if action is None else action.time,
                action.path if action is not None and action.kind=='travel' else ()))
        return DynamicSnapshot(self._clock,self._base.simulation['service_time'],self._revision,self._config_id,
            tuple(self.order(key) for key in ordered_strings(self._orders)),tuple(vehicles),
            self._queue.snapshot_ids(),tuple(self._events),self._plan,tuple(self._history),self._needs_replan)

    def validate(self) -> DynamicValidationReport:
        """Run the separate observation/event auditor. Cost documented in validator."""
        from logiroute.dynamic.validator import validate_dynamic_snapshot
        return validate_dynamic_snapshot(self._base.graph,self.snapshot())
