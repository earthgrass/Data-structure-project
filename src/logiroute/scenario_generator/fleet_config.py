"""Explicit V2 fleet-generation JSON contract, separate from legacy single-car config."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Any

from logiroute.core import Vehicle, Courier
from logiroute.core.quantities import decimal_quantity
from logiroute.scenario_generator.config_spec import GeneratorConfig, ROAD_DEFAULTS
from logiroute.scheduling.fleet_paths import finite_time


@dataclass(frozen=True, slots=True)
class FleetVehicleSpec:
    id: str
    capacity: Decimal
    depot_id: str
    courier_id: str

    def __post_init__(self) -> None:
        capacity = decimal_quantity(self.capacity, 'capacity')
        if capacity <= 0:
            raise ValueError('capacity must be positive')
        object.__setattr__(self, 'capacity', capacity)
        Vehicle(self.id, capacity, current_node_id=self.depot_id)
        Courier(self.courier_id, self.courier_id, self.id)
        if not isinstance(self.depot_id, str) or not self.depot_id.strip():
            raise ValueError('depot_id must be nonempty')

    def to_dict(self) -> dict[str, Any]:
        """JSON boundary preserves exact capacity text. Time/Space O(digits)."""
        return dict(id=self.id, capacity=str(self.capacity), depot_id=self.depot_id,
                    courier_id=self.courier_id)


@dataclass(frozen=True, slots=True)
class FleetGeneratorConfig:
    name: str
    network: GeneratorConfig
    vehicles: tuple[FleetVehicleSpec, ...]
    orders_count: int
    order_id_prefix: str
    demand_choices: tuple[Decimal, ...]
    urgent_fraction: float
    initial_time: float
    service_time: float
    witness_horizon: float
    window_early_slack: float
    window_late_slack: float
    max_attempts: int

    def __post_init__(self) -> None:
        for name in ('name', 'order_id_prefix'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be nonempty')
        if not isinstance(self.network, GeneratorConfig):
            raise ValueError('network must be a GeneratorConfig')
        if not isinstance(self.vehicles, tuple) or not self.vehicles:
            raise ValueError('vehicles must be a nonempty tuple')
        if any(not isinstance(v, FleetVehicleSpec) for v in self.vehicles):
            raise ValueError('invalid vehicle specification')
        if (len({v.id for v in self.vehicles}) != len(self.vehicles)
                or len({v.courier_id for v in self.vehicles}) != len(self.vehicles)):
            raise ValueError('duplicate vehicle/courier ID')
        depots = {f'{self.network.node_prefixes["warehouse"]}{i+1}'
                  for i in range(self.network.min_warehouses)}
        if any(v.depot_id not in depots for v in self.vehicles):
            raise ValueError('configured depot is not a generated warehouse')
        for name in ('orders_count', 'max_attempts'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if not isinstance(self.demand_choices, tuple) or not self.demand_choices:
            raise ValueError('demand_choices must be a nonempty tuple')
        object.__setattr__(self, 'demand_choices', tuple(
            decimal_quantity(value, 'demand') for value in self.demand_choices))
        for name in ('initial_time', 'service_time', 'witness_horizon',
                     'window_early_slack', 'window_late_slack', 'urgent_fraction'):
            object.__setattr__(self, name, finite_time(getattr(self, name), name, nonnegative=True))
        if self.urgent_fraction > 1:
            raise ValueError('urgent_fraction must be in [0,1]')
        if self.witness_horizon <= self.initial_time:
            raise ValueError('witness_horizon must be > initial_time')
        if self.window_early_slack == 0 and self.window_late_slack == 0:
            raise ValueError('at least one window slack must be positive (core requires start < end)')

    def to_dict(self) -> dict[str, Any]:
        """Canonical configured order; no builtin sorting. Time/Space O(config size)."""
        return dict(name=self.name,
                    network={key: getattr(self.network, key) for key in ROAD_DEFAULTS},
                    vehicles=[v.to_dict() for v in self.vehicles], orders_count=self.orders_count,
                    order_id_prefix=self.order_id_prefix,
                    demand_choices=[str(q) for q in self.demand_choices],
                    urgent_fraction=self.urgent_fraction, initial_time=self.initial_time,
                    service_time=self.service_time, witness_horizon=self.witness_horizon,
                    window_early_slack=self.window_early_slack,
                    window_late_slack=self.window_late_slack, max_attempts=self.max_attempts)

    @property
    def fingerprint(self) -> str:
        """Configuration identity includes every generation parameter. Time/Space O(size)."""
        encoded = json.dumps(self.to_dict(), ensure_ascii=True, allow_nan=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


def load_fleet_generator_config(path: str | Path) -> FleetGeneratorConfig:
    """Parse original single quantities as Decimal, never first through binary float.

    Only road parameters are accepted in network; legacy order/capacity knobs are
    rejected rather than silently reinterpreted. Time includes road quota scan;
    Space O(JSON size). Missing/unknown keys and malformed records raise ValueError.
    """
    values = json.loads(Path(path).read_text(encoding='utf-8'), parse_float=Decimal)
    if not isinstance(values, dict):
        raise ValueError('fleet generator config must be an object')
    values = dict(values)
    network = values.get('network')
    if not isinstance(network, dict) or any(key not in ROAD_DEFAULTS for key in network):
        raise ValueError('network accepts only explicit road parameters')
    def view(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)  # Geometry/time only; never load quantities.
        if isinstance(value, list):
            return [view(x) for x in value]
        return value
    def quantity(value: Any) -> Decimal:
        # Explicit serialized Decimal boundary, also accepts original JSON numbers.
        if isinstance(value, str):
            try:
                value = Decimal(value)
            except InvalidOperation as error:
                raise ValueError('invalid serialized Decimal quantity') from error
        return decimal_quantity(value)
    try:
        values['network'] = GeneratorConfig(**{k: view(v) for k, v in network.items()})
        vehicles = values['vehicles']
        if not isinstance(vehicles, list) or any(not isinstance(v, dict) for v in vehicles):
            raise ValueError('vehicles must contain object records')
        values['vehicles'] = tuple(FleetVehicleSpec(**{**v, 'capacity': quantity(v['capacity'])})
                                   for v in vehicles)
        if not isinstance(values['demand_choices'], list):
            raise ValueError('demand_choices must be an array')
        values['demand_choices'] = tuple(quantity(v) for v in values['demand_choices'])
        for name in ('urgent_fraction', 'initial_time', 'service_time', 'witness_horizon',
                     'window_early_slack', 'window_late_slack'):
            if name in values:
                values[name] = view(values[name])
        return FleetGeneratorConfig(**values)
    except (TypeError, KeyError) as error:
        raise ValueError(f'invalid fleet generator configuration: {error}') from error
