"""Immutable observations and proposals; exact loads cross JSON as decimal text."""
from __future__ import annotations
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any
from logiroute.core.enums import OrderStatus,OrderPriority,VehicleStatus,CourierStatus
from logiroute.scheduling.fleet_types import FleetScheduleResult


def _json(value: Any) -> Any:
    if isinstance(value,Decimal): return str(value)
    if isinstance(value,Enum): return value.value
    if isinstance(value,FleetScheduleResult): return value.to_dict()
    if is_dataclass(value): return {f.name:_json(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,tuple): return [_json(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class OrderView:
    id: str
    destination_id: str
    demand: Decimal
    time_window_start: float
    time_window_end: float
    priority: OrderPriority
    status: OrderStatus
    source: str


@dataclass(frozen=True, slots=True)
class DynamicEvent:
    sequence: int
    time: float
    kind: str
    order_id: str = ''
    vehicle_id: str = ''
    start_time: float = 0.0
    source_node: str = ''
    target_node: str = ''
    path: tuple[str,...] = ()
    distance: float = 0.0
    travel_time: float = 0.0
    cost: float = 0.0
    quantity: Decimal = Decimal(0)
    detail: str = ''
    order_ids: tuple[str,...] = ()
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionAction:
    kind: str
    start_time: float
    time: float
    source_node: str
    target_node: str
    path: tuple[str,...] = ()
    order_id: str = ''
    distance: float = 0.0
    travel_time: float = 0.0
    cost: float = 0.0


@dataclass(frozen=True, slots=True)
class VehicleView:
    id: str
    courier_id: str
    home_node_id: str
    current_node_id: str
    capacity: Decimal
    current_load: Decimal
    status: VehicleStatus
    courier_status: CourierStatus
    onboard_order_ids: tuple[str,...]
    action_kind: str
    action_start: float
    action_end: float
    in_flight_path: tuple[str,...]


@dataclass(frozen=True, slots=True)
class OrderReceipt:
    order_id: str
    source: str
    status: str = 'queued'
    requires_replan: bool = True


@dataclass(frozen=True, slots=True)
class ReplanProposal:
    base_revision: int
    input_fingerprint: str
    objective: str
    result: FleetScheduleResult


@dataclass(frozen=True, slots=True)
class ReplanOutcome:
    status: str
    result: FleetScheduleResult | None = None


@dataclass(frozen=True, slots=True)
class DynamicSnapshot:
    time: float
    service_time: float
    revision: int
    config_fingerprint: str
    orders: tuple[OrderView,...]
    vehicles: tuple[VehicleView,...]
    pending_ids: tuple[str,...]
    events: tuple[DynamicEvent,...]
    plan: FleetScheduleResult | None
    plan_history: tuple[FleetScheduleResult,...]
    needs_replan: bool

    def to_dict(self) -> dict[str,Any]:
        """Independent JSON value tree. Time/Space O(all records + digits)."""
        return _json(self)


@dataclass(frozen=True, slots=True)
class DynamicValidationReport:
    valid: bool
    violations: tuple[str,...]
