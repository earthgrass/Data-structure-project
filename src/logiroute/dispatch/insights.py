"""Read-only evidence projections; no route search or business-state mutation."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from logiroute.dispatch.models import Action, Plan, json_value
from logiroute.dispatch.scenario import State

if TYPE_CHECKING:
    from logiroute.dispatch.session import Session


def _metrics(actions: list[Action]) -> dict[str, float]:
    return {name: sum(getattr(a, attr) for a in actions)
            for name, attr in (('distance', 'distance'), ('cost', 'cost'), ('travel_time', 'travel_time'))}


def _delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {key: after[key] - before[key] for key in before}


def build_impact(state: State, before: Plan | None, after: Plan,
                 events: list[dict[str, Any]],
                 previous_statuses: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Freeze same-checkpoint remaining-route comparison. Time/Space O(A+E+N).

    Completion requires the entire immutable Action identity in an actual event.
    A concurrent action ending at now is not complete merely because time matches.
    Old action weights remain historical evidence, even after traffic changes.
    """
    if before is None:
        return None
    completed = {e['action'] for e in events if e['kind'] == 'action'}
    old = {r.vehicle: [a for a in r.actions if a not in completed] for r in before.routes}
    new = {r.vehicle: list(r.actions) for r in after.routes}
    vehicles = list(old)
    for key in new:
        if key not in old:
            vehicles.append(key)
    rows = []
    for key in vehicles:
        old_actions, new_actions = old.get(key, []), new.get(key, [])
        a, b = _metrics(old_actions), _metrics(new_actions)
        rows.append({'vehicle': key, 'before': a, 'after': b, 'delta': _delta(a, b),
                     'changed': old_actions != new_actions})
    old_ends = {oid: a.end for actions in old.values() for a in actions if a.kind == 'deliver' for oid in a.ids}
    new_ends = {oid: a.end for actions in new.values() for a in actions if a.kind == 'deliver' for oid in a.ids}
    ids = list(old_ends)
    for key in new_ends:
        if key not in old_ends:
            ids.append(key)
    orders = []
    for key in ids:
        a, b = old_ends.get(key), new_ends.get(key)
        difference = None if a is None or b is None else b - a
        change = ('newly_planned' if a is None else 'removed' if b is None else
                  'earlier' if difference < 0 else 'later' if difference > 0 else 'unchanged')
        orders.append({'order_id': key, 'before': a, 'after': b, 'delta': difference, 'change': change})
    a = _metrics([action for actions in old.values() for action in actions])
    b = _metrics([action for actions in new.values() for action in actions])
    return {'at': state.now, 'baseline_revision': before.revision, 'plan_revision': after.revision,
            'baseline_traffic_version': before.traffic_version, 'traffic_version': after.traffic_version,
            'comparison_basis': 'remaining_at_checkpoint', 'historical_baseline': True,
            'objective_before': before.objective, 'objective_after': after.objective,
            'before': a, 'after': b, 'delta': _delta(a, b), 'vehicles': rows, 'orders': orders,
            'newly_accepted': [key for key in new_ends if key not in old_ends],
            'no_longer_planned': [key for key in old_ends if key not in new_ends],
            'cancelled': ([key for key, order in state.orders.items()
                           if order.status in ('cancelled', 'expired') and previous_statuses.get(key) != order.status]
                          if previous_statuses is not None else
                          [key for key in old_ends if state.orders[key].status in ('cancelled', 'expired')]),
            'deferred': [key for key, _ in after.deferred]}


def actual_arrivals(session: Session) -> dict[str, tuple[str, float]]:
    """Last completed physical arrival per vehicle; Time O(E+K), Space O(K)."""
    result = {key: (node, float(session.state.config['timing']['initial']))
              for key, node in session._initial_positions.items()}
    for event in session.events:
        if event['kind'] == 'action' and event['action'].kind == 'drive':
            action = event['action']
            result[action.vehicle] = (action.target, action.end)
    return result


def _service_times(actions: list[Action], arrivals: dict[str, tuple[str, float]],
                   state: State) -> dict[str, dict[str, Any]]:
    """Physical arrival persists through waiting and same-site services. O(A+N)."""
    positions = dict(arrivals)
    result = {}
    for action in actions:
        if action.kind == 'drive':
            positions[action.vehicle] = (action.target, action.end)
        elif action.kind == 'deliver':
            last = positions.get(action.vehicle)
            arrived = last[1] if last and last[0] == action.target else None
            for key in action.ids:
                result[key] = {'vehicle': action.vehicle, 'arrival': arrived,
                               'service_start': action.start, 'signoff': action.end,
                               'slack': state.orders[key].deadline - action.end}
    return result


def planning_insights(session: Session) -> dict[str, Any]:
    """Fresh JSON projection of frozen impact and event-backed times. O(A+E+N+K).

    Proposed service times are hidden while the applied input is stale. Actual
    signoff exists only after a completed deliver event, never after a clock check.
    """
    state, plan = session.state, session.plan
    reason = ('尚无已应用计划' if plan is None else '配送已暂停，等待新的有效计划' if session._pausing else
              '订单版本已变化，等待重新规划' if session._planned_order_version != session._order_version else
              '路况版本已变化，等待重新规划' if plan.traffic_version != state.traffic_version else None)
    stale = reason is not None
    expected = {} if stale else _service_times([a for r in plan.routes for a in r.actions], session._plan_arrivals, state)
    start = {key: (node, float(state.config['timing']['initial'])) for key, node in session._initial_positions.items()}
    actual = _service_times([e['action'] for e in session.events if e['kind'] == 'action'], start, state)
    deferred = dict(plan.deferred) if plan else {}
    rows = []
    for key, order in state.orders.items():
        terminal = order.status in ('delivered', 'cancelled', 'expired')
        rows.append({'order_id': key, 'destination': order.destination, 'priority': order.priority,
                     'status': order.status, 'earliest': order.earliest, 'deadline': order.deadline,
                     'expected': None if terminal else expected.get(key), 'actual': actual.get(key),
                     'deferred_reason': None if terminal or stale else deferred.get(key)})
    attempt = session._last_attempt
    explanations = {'source': 'none', 'revision': None, 'traffic_version': None, 'stale': False, 'items': []}
    if attempt is not None:
        explanations = {'source': 'applied_plan' if attempt is plan else 'blocked_proposal',
                        'revision': attempt.revision, 'traffic_version': attempt.traffic_version,
                        'stale': (session._last_attempt_order_version != session._order_version or
                                  attempt.traffic_version != state.traffic_version or session._last_attempt_at != state.now),
                        'items': json_value(getattr(attempt, 'explanations', ()))}
    return {'impact': json_value(session._planning_impact),
            'timeline': {'now': state.now, 'plan_revision': plan.revision if plan else None,
                         'stale': stale, 'stale_reason': reason, 'orders': rows},
            'explanations': explanations}
