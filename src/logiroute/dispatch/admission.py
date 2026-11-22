"""Transactional critical-order admission using the existing planner and validator."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from typing import Any
from logiroute.algorithms.ordering import ordered_strings
from logiroute.dispatch.session import Session


class CriticalAdmissionError(ValueError):
    """No verified safe continuation for this proposed critical order."""

    def __init__(self, report: dict[str, Any], *, allow_late: bool = False) -> None:
        message=('该特急订单允许迟到，但在当前车辆载重、道路和已进入动作约束下仍未找到可验证的配送方案；未插入，原计划保持不变。请调整重量、道路或配送资源。'
                 if allow_late else '该特急订单在当前容量、路况和时间窗约束下未找到按时签收方案，未插入，原计划保持不变。建议选择更晚的签收截止时间后重试；若容量不足或道路不可达，还需调整载重或路况。')
        super().__init__(message)
        self.report = report


def admit_critical(session: Session, key: str, destination: str,
                   demand: Decimal | int | float, earliest: float, deadline: float,
                   *, allow_late: bool = False) -> None:
    """Preview the next physical checkpoint before committing admission.

    Try all commitments first, then allow only unentered warehouse lower-priority
    commitments to compete again. Existing critical and physical cargo never yield.
    Time O(copy + K*step + 2*planner); Space O(session + plan).
    The preview never advances the real clock, vehicle or entered action.
    """
    probe = deepcopy(session)
    probe.add_order(key, destination, demand, earliest, deadline, 'critical', allow_late=allow_late)
    probe.pause()
    while probe.running:
        probe.step()
    objective = session.plan.objective if session.plan else 'distance'
    proposal = probe.prepare(objective)
    released = []
    if key not in proposal.accepted or not proposal.report.safe_to_apply:
        released = [oid for oid in ordered_strings(probe.state.protected)
                    if probe.state.locations[oid][0] == 'warehouse'
                    and probe.state.orders[oid].priority != 'critical']
        for oid in released:
            probe.state.protected.discard(oid)
            probe.state.orders[oid] = replace(probe.state.orders[oid], status='pending', hub='')
        proposal = probe.prepare(objective)
    if key not in proposal.accepted or not proposal.report.valid or not proposal.report.safe_to_apply:
        raise CriticalAdmissionError(proposal.to_dict(), allow_late=allow_late)
    # All potentially failing planning work is complete. Commit only input changes.
    session.enable_auto_replan()
    session.add_order(key, destination, demand, earliest, deadline, 'critical', allow_late=allow_late)
    for oid in released:
        session.state.protected.discard(oid)
        session.state.orders[oid] = replace(session.state.orders[oid], status='pending', hub='')
    session.state.orders[key] = replace(session.state.orders[key], hub=dict(proposal.assignments)[key])
    session.state.protected.add(key)
    displaced = [oid for oid in released if oid not in proposal.accepted]
    delivery=next((r.vehicle,a.end) for r in proposal.routes for a in r.actions
                  if a.kind == 'deliver' and key in a.ids)
    session._critical_admission = {'order_id': key, 'checked_at': probe.state.now,
        'input_revision': session.state.revision, 'displaced_order_ids': displaced,
        'expected_signoff': delivery[1], 'assigned_vehicle': delivery[0],
        'lateness_minutes': max(0.0, delivery[1]-deadline)}
    session.events.append({'kind': 'critical_admission', 'time': session.state.now,
                           **session._critical_admission})
