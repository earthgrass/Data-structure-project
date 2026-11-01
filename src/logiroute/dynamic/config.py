"""JSON-owned dynamic intake parameters; original single quantities remain exact."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Any
from logiroute.core.quantities import decimal_quantity
from logiroute.scheduling.fleet_paths import finite_time


@dataclass(frozen=True, slots=True)
class AutomaticOrderConfig:
    destination_ids: tuple[str, ...]
    demand_choices: tuple[Decimal, ...]
    urgent_fraction: float
    window_delay_range: tuple[float, float]
    window_width_range: tuple[float, float]

    def __post_init__(self) -> None:
        if (not isinstance(self.destination_ids,tuple) or
                any(not isinstance(k,str) or not k.strip() for k in self.destination_ids)
                or len(set(self.destination_ids))!=len(self.destination_ids)):
            raise ValueError('automatic destinations must be distinct nonempty IDs')
        if not isinstance(self.demand_choices,tuple) or not self.demand_choices:
            raise ValueError('demand_choices must be a nonempty tuple')
        object.__setattr__(self,'demand_choices',tuple(decimal_quantity(q) for q in self.demand_choices))
        fraction=finite_time(self.urgent_fraction,'urgent_fraction',nonnegative=True)
        if fraction>1: raise ValueError('urgent_fraction must be in [0,1]')
        object.__setattr__(self,'urgent_fraction',fraction)
        for name in ('window_delay_range','window_width_range'):
            values=getattr(self,name)
            if not isinstance(values,tuple) or len(values)!=2:
                raise ValueError(f'{name} requires two ordered bounds')
            bounds=tuple(finite_time(v,name,nonnegative=True) for v in values)
            if bounds[0]>bounds[1] or (name=='window_width_range' and bounds[0]<=0):
                raise ValueError(f'invalid {name}')
            object.__setattr__(self,name,bounds)


@dataclass(frozen=True, slots=True)
class DynamicConfig:
    name: str
    default_objective: str
    order_id_prefix: str
    automatic: AutomaticOrderConfig

    def __post_init__(self) -> None:
        if any(not isinstance(v,str) or not v.strip() for v in (self.name,self.order_id_prefix)):
            raise ValueError('name and order_id_prefix must be nonempty')
        if self.default_objective not in ('distance','cost'):
            raise ValueError('objective must be distance or cost')
        if not isinstance(self.automatic,AutomaticOrderConfig):
            raise ValueError('invalid automatic configuration')

    def to_dict(self) -> dict[str, Any]:
        """Exact JSON boundary. Time/Space O(config records and digits)."""
        a=self.automatic
        return dict(name=self.name,default_objective=self.default_objective,
                    order_id_prefix=self.order_id_prefix,
                    automatic=dict(destination_ids=list(a.destination_ids),
                                   demand_choices=[str(q) for q in a.demand_choices],
                                   urgent_fraction=a.urgent_fraction,
                                   window_delay_range=list(a.window_delay_range),
                                   window_width_range=list(a.window_width_range)))

    @property
    def fingerprint(self) -> str:
        """Time/Space O(config size); explicit field order, no builtin sorting."""
        return hashlib.sha256(json.dumps(self.to_dict(),ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def load_dynamic_config(path: str | Path) -> DynamicConfig:
    """Read JSON numbers as Decimal before exact quantity conversion. O(JSON size)."""
    values=json.loads(Path(path).read_text(encoding='utf-8'),parse_float=Decimal)
    if not isinstance(values,dict) or not isinstance(values.get('automatic'),dict):
        raise ValueError('dynamic config and automatic must be objects')
    try:
        a=dict(values['automatic'])
        for key in ('destination_ids','demand_choices','window_delay_range','window_width_range'):
            if not isinstance(a[key],list): raise ValueError(f'{key} must be an array')
            a[key]=tuple(a[key])
        a['demand_choices']=tuple(decimal_quantity(Decimal(q) if isinstance(q,str) else q)
                                   for q in a['demand_choices'])
        for key in ('window_delay_range','window_width_range'):
            a[key]=tuple(float(v) if isinstance(v,Decimal) else v for v in a[key])
        if isinstance(a.get('urgent_fraction'),Decimal): a['urgent_fraction']=float(a['urgent_fraction'])
        return DynamicConfig(**{**values,'automatic':AutomaticOrderConfig(**a)})
    except (TypeError,KeyError,InvalidOperation) as error:
        raise ValueError(f'invalid dynamic configuration: {error}') from error
