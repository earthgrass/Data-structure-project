"""Fleet result contracts, independent of HTTP and the legacy single-car DTO.

Quantities remain Decimal until to_dict(). All public collections are tuples.
Construction/serialization is linear in the number of contained records/digits.
Validity and full coverage are separate; no unverified result implies success.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
import math
from typing import Any


def _id(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('identifier must be a nonempty string')


def _number(value: float, *, signed: bool = False) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (not signed and value < 0)):
        raise ValueError('expected a finite numeric scalar in its allowed range')


def _quantity(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError('load quantities must be finite nonnegative Decimal')


def _tuple(value: tuple) -> None:
    if not isinstance(value, tuple):
        raise ValueError('public collections must be immutable tuples')


def _json(value: Any) -> Any:
    """Explicit serialization boundary. Time/Space O(records + scalar digits)."""
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {f.name: _json(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple):
        return [_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class FleetVisit:
    node_id: str
    order_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _id(self.node_id)
        _tuple(self.order_ids)
        for order_id in self.order_ids:
            _id(order_id)

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class FleetLeg:
    source: str
    target: str
    path: tuple[str, ...]
    distance: float
    travel_time: float
    cost: float

    def __post_init__(self) -> None:
        _id(self.source)
        _id(self.target)
        _tuple(self.path)
        for node in self.path:
            _id(node)
        for value in (self.distance, self.travel_time, self.cost):
            _number(value)

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class FleetService:
    order_id: str
    visit_index: int
    service_index: int
    arrival_time: float
    waiting_time: float
    service_start: float
    service_end: float
    load_after: Decimal

    def __post_init__(self) -> None:
        _id(self.order_id)
        for index in (self.visit_index, self.service_index):
            if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                raise ValueError('service indices must be nonnegative integers')
        for value in (self.arrival_time, self.service_start, self.service_end):
            _number(value, signed=True)
        _number(self.waiting_time)
        _quantity(self.load_after)

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class VehicleRoutePlan:
    vehicle_id: str
    courier_id: str
    depot_id: str
    visits: tuple[FleetVisit, ...]
    legs: tuple[FleetLeg, ...]
    services: tuple[FleetService, ...]
    capacity: Decimal
    initial_load: Decimal
    departure_time: float
    return_time: float
    total_distance: float
    total_travel_time: float
    total_cost: float

    def __post_init__(self) -> None:
        for value in (self.vehicle_id, self.courier_id, self.depot_id):
            _id(value)
        for records, kind in ((self.visits, FleetVisit), (self.legs, FleetLeg),
                              (self.services, FleetService)):
            _tuple(records)
            if any(not isinstance(item, kind) for item in records):
                raise ValueError('route contains an invalid record type')
        _quantity(self.capacity)
        _quantity(self.initial_load)
        for value in (self.departure_time, self.return_time):
            _number(value, signed=True)
        for value in (self.total_distance, self.total_travel_time, self.total_cost):
            _number(value)

    @property
    def served_order_ids(self) -> tuple[str, ...]:
        """Actual service event IDs, not destination count. Time/Space O(M)."""
        return tuple(event.order_id for event in self.services)

    @property
    def stop_sequence(self) -> tuple[str, ...]:
        """Node visits independent of service count. Time/Space O(visits)."""
        return tuple(visit.node_id for visit in self.visits)

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


UNSERVED_REASONS = ('order_not_pending', 'no_available_vehicle', 'capacity',
                   'unreachable_leg', 'return_unreachable', 'time_window',
                   'nonfinite_path', 'nonfinite_time', 'heuristic_unassigned')


@dataclass(frozen=True, slots=True)
class UnservedOrder:
    order_id: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _id(self.order_id)
        _tuple(self.reasons)
        if not self.reasons or any(reason not in UNSERVED_REASONS for reason in self.reasons):
            raise ValueError('unserved orders require explicit recognized reasons')

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class FleetValidationReport:
    valid: bool
    complete: bool
    violations: tuple[str, ...]
    return_deadline_checked: bool = False

    def __post_init__(self) -> None:
        _tuple(self.violations)
        if not isinstance(self.valid, bool) or not isinstance(self.complete, bool):
            raise ValueError('validation flags must be bool')
        if self.complete and not self.valid:
            raise ValueError('an invalid plan cannot be complete')

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class FleetStats:
    dijkstra_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    path_table_hits: int = 0
    candidate_evaluations: int = 0
    feasibility_checks: int = 0
    time_window_checks: int = 0
    iterations: int = 0
    runtime_seconds: float = 0.0
    validation_seconds: float = 0.0

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name.endswith('seconds'):
                _number(value)
            elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError('statistics counters must be nonnegative integers')

    def to_dict(self) -> dict[str, Any]:
        return _json(self)


@dataclass(frozen=True, slots=True)
class FleetScheduleResult:
    scenario_name: str
    objective: str
    routes: tuple[VehicleRoutePlan, ...]
    unserved_orders: tuple[UnservedOrder, ...]
    unavailable_vehicles: tuple[tuple[str, tuple[str, ...]], ...]
    planning_stats: FleetStats
    validation: FleetValidationReport | None = None
    selection_trace: tuple[tuple[str, str, int, int, int], ...] = ()
    input_fingerprint: str = ''

    def __post_init__(self) -> None:
        _id(self.scenario_name)
        if self.objective not in ('distance', 'cost'):
            raise ValueError('fleet objective must be distance or cost')
        for value in (self.routes, self.unserved_orders, self.unavailable_vehicles,
                      self.selection_trace):
            _tuple(value)
        if any(not isinstance(route, VehicleRoutePlan) for route in self.routes):
            raise ValueError('invalid route record')
        if any(not isinstance(item, UnservedOrder) for item in self.unserved_orders):
            raise ValueError('invalid unserved record')
        for vehicle_id, reasons in self.unavailable_vehicles:
            _id(vehicle_id)
            _tuple(reasons)
            if not reasons or any(not isinstance(reason, str) or not reason for reason in reasons):
                raise ValueError('unavailable vehicles require reasons')
        if not isinstance(self.planning_stats, FleetStats):
            raise ValueError('invalid statistics record')
        if self.validation is not None and not isinstance(self.validation, FleetValidationReport):
            raise ValueError('invalid validation report')

    @property
    def status(self) -> str:
        """Time/Space O(1). Coverage and validity remain independent."""
        if self.validation is None:
            return 'unverified'
        if not self.validation.valid:
            return 'invalid'
        return 'complete' if self.validation.complete else 'partial'

    @property
    def is_feasible(self) -> bool:
        """Only independently validated full coverage is success. Time/Space O(1)."""
        return self.status == 'complete'

    @property
    def search_outcome(self) -> str:
        """No outcome claims mathematical infeasibility. Time/Space O(1)."""
        return 'full_plan_found' if self.is_feasible else 'heuristic_incomplete'

    @property
    def total_distance(self) -> float:
        """Sum actual final route reports. Time O(K); Space O(1)."""
        return sum(route.total_distance for route in self.routes)

    @property
    def total_travel_time(self) -> float:
        """Driving only; waiting/service remain in schedules. Time O(K); Space O(1)."""
        return sum(route.total_travel_time for route in self.routes)

    @property
    def total_cost(self) -> float:
        """Includes outbound and return legs. Time O(K); Space O(1)."""
        return sum(route.total_cost for route in self.routes)

    def to_dict(self) -> dict[str, Any]:
        result = _json(self)
        result.update(status=self.status, is_feasible=self.is_feasible,
                      search_outcome=self.search_outcome,
                      total_distance=self.total_distance,
                      total_travel_time=self.total_travel_time, total_cost=self.total_cost)
        return result
