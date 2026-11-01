"""Independent executed-history evidence, separate from session action application."""
from __future__ import annotations
from typing import TYPE_CHECKING
from logiroute.core.quantities import exact_sum
from logiroute.dispatch.models import Report,RANK
if TYPE_CHECKING:
    from logiroute.dispatch.session import Session


def audit_session(session: Session) -> Report:
    """Replay completed actions only, independently of program cursors. O(A*N), Space O(N+K)."""
    state=session.state; orders=dict(session._initial_orders); loc=dict(session._initial_locations)
    pos=dict(session._initial_positions); clock={k:0.0 for k in pos}; released={k:0.0 for k in loc}; lower={k:False for k in pos}
    errors=[]; delivered=set(); cancelled=set()
    for event in session.events:
        kind=event['kind']
        if kind=='create':
            o=event['order']
            if o.id in orders: errors.append('reused_order_id')
            orders[o.id]=o; loc[o.id]=event['location']; released[o.id]=event['time']
        elif kind=='cancel': cancelled.add(event['id'])
        elif kind=='priority':
            from dataclasses import replace
            orders[event['id']]=replace(orders[event['id']],priority=event['priority'])
        elif kind=='action':
            a=event['action']; car=state.vehicles[a.vehicle]; key=car.id
            if a.source!=pos[key] or a.start<clock[key] or a.end<a.start: errors.append('history_time_position')
            if a.kind=='drive':
                if not session.network.validate_entered_edge(a): errors.append('history_road')
                pos[key]=a.target
            elif a.kind=='load':
                source=('warehouse' if car.role=='trunk' else 'hub',car.base)
                if pos[key]!=car.base or a.end!=a.start+state.config['timing']['loading'] or len(set(a.ids))!=len(a.ids): errors.append('history_load')
                for oid in a.ids:
                    if loc[oid]!=source or released[oid]>a.start or oid in cancelled: errors.append('history_inventory')
                    loc[oid]=('vehicle',key)
                lower[key]=False
            elif a.kind in ('deliver','unload'):
                priority=min((RANK[orders[o].priority] for o in a.ids),default=2)
                if priority==0 and lower[key]: errors.append('history_priority')
                if priority!=0: lower[key]=True
                for oid in a.ids:
                    if loc[oid]!=('vehicle',key): errors.append('history_service_inventory')
                    if a.kind=='unload':
                        if car.role!='trunk' or pos[key] not in state.config['hub_ids'] or a.end!=a.start+state.config['timing']['unloading']: errors.append('history_unload')
                        loc[oid]=('hub',pos[key]); released[oid]=a.end
                    else:
                        o=orders[oid]
                        if car.role!='delivery' or pos[key]!=o.destination or a.start<o.earliest or a.end>o.deadline or a.end!=a.start+state.config['timing']['service'] or oid in delivered: errors.append('history_signoff')
                        loc[oid]=('delivered',oid); delivered.add(oid)
            elif a.kind=='finish' and (pos[key]!=car.base or any(l==('vehicle',key) for l in loc.values())): errors.append('history_return')
            clock[key]=a.end
            if exact_sum(orders[o].demand for o,l in loc.items() if l==('vehicle',key))>car.capacity: errors.append('history_capacity')
    if loc!=state.locations or pos!=state.positions: errors.append('snapshot_history_mismatch')
    if {k for k,o in state.orders.items() if o.status=='delivered'}!=delivered: errors.append('signoff_status_mismatch')
    active={k for k,o in state.orders.items() if o.status not in ('cancelled','expired')}
    return Report(not errors,not errors and active==delivered,not errors,tuple(errors))
