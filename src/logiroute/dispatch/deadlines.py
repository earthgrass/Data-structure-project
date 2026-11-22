"""Explicit completion-deadline policy for the operational pressure profile."""
from __future__ import annotations

from typing import Any
from logiroute.dispatch.models import Job, Route, Parcel


def hard_deadline(config: dict[str, Any], priority: str, allow_late: bool = False) -> bool:
    """Whether late completion is forbidden. Time/Space O(1)."""
    if priority == 'critical' and allow_late:
        return False
    policy = config.get('late_delivery')
    return policy is None or priority in policy['hard_priorities']


def lateness_score(route: Route, jobs: list[Job]) -> tuple[int, float, int, float]:
    """Urgent late count/minutes precede normal late count/minutes. O(actions+jobs)."""
    by_id = {job.id: job for job in jobs}
    urgent_count = normal_count = 0
    urgent_minutes = normal_minutes = 0.0
    for action in route.actions:
        if action.kind != 'deliver':
            continue
        job = by_id['deliver:' + action.ids[0]]
        late = max(0.0, action.end - job.deadline)
        if late <= 0:
            continue
        if job.priority == 'urgent':
            urgent_count += 1
            urgent_minutes += late
        elif job.priority == 'normal':
            normal_count += 1
            normal_minutes += late
    return urgent_count, urgent_minutes, normal_count, normal_minutes


def fleet_lateness_score(routes: tuple[Route, ...], orders: dict[str, Parcel]) -> tuple[int, float, int, float]:
    """Compare complete candidate continuations, not only the new parcel. O(actions)."""
    urgent_count = normal_count = 0
    urgent_minutes = normal_minutes = 0.0
    for route in routes:
        for action in route.actions:
            if action.kind != 'deliver':
                continue
            for oid in action.ids:
                order = orders[oid]
                late = max(0.0, action.end - order.deadline)
                if late <= 0:
                    continue
                if order.priority == 'urgent':
                    urgent_count += 1
                    urgent_minutes += late
                elif order.priority == 'normal':
                    normal_count += 1
                    normal_minutes += late
    return urgent_count, urgent_minutes, normal_count, normal_minutes
