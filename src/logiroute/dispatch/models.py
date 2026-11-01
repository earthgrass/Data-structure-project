"""Versioned immutable contracts; load quantities never use float subtotals."""
from __future__ import annotations
from dataclasses import dataclass,fields,is_dataclass
from decimal import Decimal
from typing import Any
from logiroute.core.quantities import decimal_quantity
from logiroute.scheduling.fleet_paths import finite_time

SCHEMA='logiroute.v2.phase6'
RANK={'critical':0,'urgent':1,'normal':2}


def identifier(value: str) -> None:
    if not isinstance(value,str) or not value.strip(): raise ValueError('empty identifier')


def json_value(value: Any) -> Any:
    """JSON boundary, Time/Space O(records+digits)."""
    if isinstance(value,Decimal): return str(value)
    if is_dataclass(value): return {f.name:json_value(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,(tuple,list)): return [json_value(v) for v in value]
    if isinstance(value,dict): return {k:json_value(v) for k,v in value.items()}
    return value


@dataclass(frozen=True,slots=True)
class VehicleSpec:
    id: str
    courier_id: str
    role: str
    base: str
    capacity: Decimal

    def __post_init__(self) -> None:
        for x in (self.id,self.courier_id,self.base): identifier(x)
        if self.role not in ('trunk','delivery'): raise ValueError('invalid vehicle role')
        q=decimal_quantity(self.capacity)
        if q<=0: raise ValueError('capacity must be positive')
        object.__setattr__(self,'capacity',q)


@dataclass(frozen=True,slots=True)
class Parcel:
    id: str
    destination: str
    demand: Decimal
    earliest: float
    deadline: float
    priority: str = 'normal'
    status: str = 'pending'
    hub: str = ''

    def __post_init__(self) -> None:
        identifier(self.id); identifier(self.destination)
        object.__setattr__(self,'demand',decimal_quantity(self.demand))
        finite_time(self.earliest,'earliest'); finite_time(self.deadline,'deadline')
        if self.earliest>=self.deadline or self.priority not in RANK: raise ValueError('invalid order window/priority')
        if self.status not in ('pending','planned','in_transit','delivered','cancelled','expired'):
            raise ValueError('invalid order status')


@dataclass(frozen=True,slots=True)
class Job:
    id: str
    node: str
    kind: str
    ids: tuple[str,...]
    demand: Decimal
    priority: str
    earliest: float
    deadline: float
    duration: float

    def __post_init__(self) -> None:
        identifier(self.id); identifier(self.node)
        if self.priority not in RANK or self.kind not in ('deliver','unload'): raise ValueError('invalid job')
        object.__setattr__(self,'demand',decimal_quantity(self.demand))
        for x in (self.earliest,self.deadline,self.duration): finite_time(x,'job time',nonnegative=True)
        if not isinstance(self.ids,tuple) or len(self.ids)!=len(set(self.ids)): raise ValueError('invalid manifest')


@dataclass(frozen=True,slots=True)
class Action:
    vehicle: str
    kind: str
    start: float
    end: float
    source: str
    target: str
    ids: tuple[str,...] = ()
    distance: float = 0.0
    travel_time: float = 0.0
    cost: float = 0.0
    traffic_version: int = 0
    batch: int = 0


@dataclass(frozen=True,slots=True)
class Route:
    vehicle: str
    start_node: str
    end_node: str
    actions: tuple[Action,...]

    @property
    def end_time(self) -> float:
        return self.actions[-1].end if self.actions else 0.0

    @property
    def total_distance(self) -> float:
        return sum(a.distance for a in self.actions)

    @property
    def total_cost(self) -> float:
        return sum(a.cost for a in self.actions)


@dataclass(frozen=True,slots=True)
class Report:
    valid: bool
    complete_all: bool
    safe_to_apply: bool
    violations: tuple[str,...]


@dataclass(frozen=True,slots=True)
class Plan:
    objective: str
    revision: int
    traffic_version: int
    assignments: tuple[tuple[str,str],...]
    routes: tuple[Route,...]
    accepted: tuple[str,...]
    deferred: tuple[tuple[str,str],...]
    report: Report | None = None
    fingerprint: str = ''

    def to_dict(self) -> dict[str,Any]:
        """Time/Space O(plan records+digits), including actual route metrics."""
        result=json_value(self)
        for row,route in zip(result['routes'],self.routes):
            row.update(total_distance=route.total_distance,total_cost=route.total_cost,end_time=route.end_time)
        result['total_distance']=sum(r.total_distance for r in self.routes)
        result['total_cost']=sum(r.total_cost for r in self.routes)
        return result
