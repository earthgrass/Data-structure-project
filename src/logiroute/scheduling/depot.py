"""仓库与车辆自动选择。

依据 AGENTS.md §3.6「单车辆」约束：

* ``ScenarioBundle.vehicles`` 中只允许 **一辆** 车辆参与实际配送；
* 选车标准（按优先级）：
  1. ``vehicle.status is VehicleStatus.IDLE``
  2. ``vehicle.current_node_id`` 是仓库节点（``NodeType.WAREHOUSE``）
  3. ``vehicle.id`` 字典序最小（确定性 tie-break）

无任何车辆满足条件 → 抛 :class:`PlanningError`。
"""

from __future__ import annotations

from typing import NamedTuple

from logiroute.config.loader import ScenarioBundle
from logiroute.core.couriers import Courier
from logiroute.core.enums import NodeType, VehicleStatus
from logiroute.core.vehicles import Vehicle
from logiroute.scheduling.types import (
    DepotNotFoundError,
    NoAvailableVehicleError,
)


class DepotChoice(NamedTuple):
    """自动选仓库 / 车辆 / 配送员的结果。"""

    vehicle: Vehicle
    depot_id: str
    courier: Courier | None


def _warehouse_ids(scenario: ScenarioBundle) -> set[str]:
    """返回图内全部仓库节点 ID。"""
    return {
        n.id
        for n in scenario.graph.get_all_nodes()
        if n.node_type == NodeType.WAREHOUSE
    }


def _pick_courier(scenario: ScenarioBundle, vehicle_id: str) -> Courier | None:
    """按 ``vehicle_id`` 在 ``scenario.couriers`` 中查 lex-min 配送员。"""
    matching = sorted(
        (c for c in scenario.couriers if c.vehicle_id == vehicle_id),
        key=lambda c: c.id,
    )
    return matching[0] if matching else None


def select_depot(
    scenario: ScenarioBundle,
    depot_id: str | None = None,
    min_total_demand: float | None = None,
) -> DepotChoice:
    """挑选本次调度的**唯一**车辆与对应仓库。

    Args:
        scenario: 加载完毕的 :class:`ScenarioBundle`。
        depot_id: 显式指定的仓库 ID；为 ``None`` 时自动挑选。
        min_total_demand: 本次调度的最小装载需求；为 ``None`` 时按"lex-min
            IDLE vehicle"策略；当给出时，**额外**过滤掉容量严格小于
            ``min_total_demand`` 的车辆。这避免了"车选上了但装不下"的
            灾难 —— 满足 AGENTS §3.6 单车辆 + 全订单服务的硬约束。

    Returns:
        :class:`DepotChoice` —— 选定车辆 + 仓库节点 ID + 委派配送员。

    Raises:
        NoAvailableVehicleError: 无 IDLE 车辆 / 无仓库匹配 / 容量不足。
        DepotNotFoundError: 显式指定 ``depot_id`` 但不是仓库或无对应 IDLE 车辆。
    """
    warehouses = _warehouse_ids(scenario)

    def _eligible(v) -> bool:
        if v.status is not VehicleStatus.IDLE:
            return False
        if v.current_node_id not in warehouses:
            return False
        if (
            min_total_demand is not None
            and v.capacity + 1e-9 < min_total_demand
        ):
            return False
        return True

    if depot_id is not None:
        if depot_id not in warehouses:
            raise DepotNotFoundError(
                f"depot_id={depot_id!r} is not a warehouse node "
                f"(known warehouses: {sorted(warehouses)})"
            )
        for v in sorted(scenario.vehicles, key=lambda x: x.id):
            if v.current_node_id == depot_id and v.status is VehicleStatus.IDLE:
                if (
                    min_total_demand is not None
                    and v.capacity + 1e-9 < min_total_demand
                ):
                    raise DepotNotFoundError(
                        f"vehicle {v.id!r} at depot {depot_id!r} has capacity "
                        f"{v.capacity} < required {min_total_demand}"
                    )
                return DepotChoice(
                    vehicle=v,
                    depot_id=depot_id,
                    courier=_pick_courier(scenario, v.id),
                )
        raise DepotNotFoundError(
            f"no IDLE vehicle currently at depot {depot_id!r}"
        )

    # 自动选：lex-min 满足所有约束的 IDLE vehicle
    candidates = sorted(
        (v for v in scenario.vehicles if _eligible(v)),
        key=lambda v: v.id,
    )
    if not candidates:
        reasons = []
        if min_total_demand is not None:
            reasons.append(
                f"min_total_demand={min_total_demand}"
            )
        raise NoAvailableVehicleError(
            "no IDLE vehicle currently parked at any warehouse node "
            f"with {'required capacity' if min_total_demand is not None else 'available status'}; "
            f"vehicles={[v.id for v in scenario.vehicles]}, "
            f"warehouses={sorted(warehouses)}, "
            + (" ".join(reasons))
        )
    chosen = candidates[0]
    return DepotChoice(
        vehicle=chosen,
        depot_id=chosen.current_node_id,
        courier=_pick_courier(scenario, chosen.id),
    )


__all__ = ["DepotChoice", "select_depot"]
