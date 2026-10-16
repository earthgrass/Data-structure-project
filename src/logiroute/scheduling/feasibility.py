"""闭环调度硬约束可行性检查器（纯函数）。

依据 AGENTS.md §3.7：

* 仅做硬约束检查（容量、时间窗、可达性、仓库匹配、``service_time`` 完整性）；
* ``service_start > time_window_end`` 视为硬违反；``service_end`` 越界
  **不**视为违反（§3.7 明确本阶段不强制 ``service_end <= window_end``）；
* 早到允许并计入 ``waiting_time``；晚到记录违反；
* 实际行驶时间取 ``leg.cross_metrics['travel_time']``，避免主目标（distance /
  cost）所选的路径被当作时间累加口径（见下文"传播决策"）。

约束列表：

1. 每条 ``leg.reachable`` 必须为 ``True``；最后一条 leg（回归仓库）若不可达，
   使用 ``return_unreachable`` 特殊 kind；
2. 首尾 ``DeliveryStop.node_id`` 必须等于 ``depot_id``；
3. ``DeliveryStop.cumulative_load`` 不能超过 ``capacity``；
4. ``service_start > time_window_end`` 视为违反（``time_window_miss``）；
5. ``service_end == service_start + service_time`` 应默认成立；不一致记录
   ``service_time_overflow``（仅检查 ``order_id is not None`` 的客户站，
   仓库 stop 不参与服务故跳过）。

函数为**纯函数**：不修改入参，不读写全局状态；可重复调用并保证幂等。

Time   : O(K) 其中 K = stops 数；legs 与 stops 长度差 1。
Space  : O(K) violations 临时数组；最终 ``FeasibilityReport`` 不可变。

传播决策（说明）
----------------
文档中描述的传播规则——``arrival[i+1] = service_end[i] + drive_time``——由调用方
（即上层规划器）在构造 ``stops`` 时执行。本函数只校验已经填入
``DeliveryStop`` 的字段，不重新计算。

校验口径要求：实际行驶时间必须取 ``leg.cross_metrics['travel_time']`` 而非
``leg.total_weight``。后者在 ``objective=distance`` / ``objective=cost`` 模式下
分别为最短距离 / 最低成本路径权重，**不**等于实际行驶时间；用其累加会偷换
"最短时间路径"语义。本模块不重复计算，但 ``arrival_time`` 一旦构造错误，
后续 ``time_window_miss`` 检查会自动捕获。
"""

from __future__ import annotations

from typing import Any

from logiroute.scheduling.types import (
    DeliveryStop,
    FeasibilityReport,
    Violation,
)


#: 浮点比较容差，与 ``logiroute.scheduling.types`` 的 ``DeliveryStop.__post_init__``
#: 保持同一量级。
_TOL = 1e-9


def _leg_drive_time(leg: Any) -> float:
    """读取 ``leg`` 的实际行驶时间。

    优先级：``leg.cross_metrics['travel_time']`` > ``leg.total_weight``。
    本函数供传播校验调用方使用；``check_feasibility`` 本身不重新传播时间，
    但保留此工具以保持口径一致。

    Time : O(1)。
    Space: O(1)。
    """
    cross = getattr(leg, "cross_metrics", None) or {}
    travel = cross.get("travel_time")
    if travel is not None:
        return float(travel)
    return float(getattr(leg, "total_weight", 0.0))


def check_feasibility(
    stops: tuple[DeliveryStop, ...],
    legs: tuple[Any, ...],
    capacity: float,
    service_time: float,
    initial_time: float,
    depot_id: str,
) -> FeasibilityReport:
    """检查一条闭环调度的硬约束。

    检查项（详见模块 docstring）：

    1. 腿可达性（最后一条腿为 ``return_unreachable`` 特例）；
    2. 首尾仓库节点匹配；
    3. 容量溢出；
    4. 时间窗开始时间晚于上界（``service_end`` 越界不计入）；
    5. ``service_time`` 一致性（仅检查 ``order_id is not None`` 的客户站）。

    Args:
        stops: 闭环所有站点（含首尾仓库）；长度为 K+1，K 为配送站数。
        legs: 相邻站点之间的有向路径结果（``PathResult`` 或其等价对象）；
            长度为 K。
        capacity: 车辆容量上限。
        service_time: 每个客户站点的固定服务时长（仓库站不适用）。
        initial_time: 出发时刻（保留参数；当前用于 schema 自描述）。
        depot_id: 期望的出发 / 返回仓库节点 ID。

    Returns:
        ``FeasibilityReport(is_feasible=..., violations=...)``；无违反时
        ``violations=()``，``is_feasible=True``。

    Raises:
        ValueError: 当 ``len(legs) != len(stops) - 1`` 时抛出（schema 不一致）。

    Time : O(K) 其中 K = stops 数。
    Space: O(K) violations 临时数组。
    """
    if len(legs) != len(stops) - 1:
        raise ValueError(
            f"len(legs) ({len(legs)}) must equal len(stops) - 1 "
            f"({len(stops) - 1})"
        )

    violations: list[Violation] = []
    last_leg_index = len(legs) - 1

    # ---- Check 1: 腿可达性 -----------------------------------------------
    for i, leg in enumerate(legs):
        if getattr(leg, "reachable", False):
            continue
        kind = "return_unreachable" if i == last_leg_index else "unreachable_leg"
        source = getattr(leg, "source", "?")
        target = getattr(leg, "target", "?")
        if i == last_leg_index:
            message = (
                f"return-to-depot leg from {source!r} to {target!r} "
                f"is unreachable; closed tour cannot be completed"
            )
        else:
            message = (
                f"leg from {source!r} to {target!r} (index {i}) "
                f"is unreachable"
            )
        violations.append(
            Violation(order_id=None, kind=kind, message=message)
        )

    # ---- Check 2: 首尾仓库匹配 -------------------------------------------
    if stops[0].node_id != depot_id:
        violations.append(
            Violation(
                order_id=None,
                kind="depot_mismatch",
                message=(
                    f"first stop node_id ({stops[0].node_id!r}) does not "
                    f"equal depot_id ({depot_id!r})"
                ),
            )
        )
    if stops[-1].node_id != depot_id:
        violations.append(
            Violation(
                order_id=None,
                kind="depot_mismatch",
                message=(
                    f"last stop node_id ({stops[-1].node_id!r}) does not "
                    f"equal depot_id ({depot_id!r})"
                ),
            )
        )

    # ---- Check 3: 容量上限 -------------------------------------------------
    for stop in stops:
        if stop.cumulative_load <= capacity + _TOL:
            continue
        violations.append(
            Violation(
                order_id=stop.order_id,
                kind="capacity_overflow",
                message=(
                    f"cumulative_load ({stop.cumulative_load}) exceeds "
                    f"capacity ({capacity}) at stop {stop.node_id!r} "
                    f"(index {stop.sequence_index})"
                ),
            )
        )

    # ---- Check 4: 时间窗硬约束 -------------------------------------------
    # AGENTS §3.7：本阶段**不**强制 service_end <= time_window_end；
    # 只检查 service_start 是否晚于窗口上界。早到允许并计入 waiting。
    for stop in stops:
        if stop.time_window_end is None:
            continue  # 仓库 stop / 无时间窗约束
        if stop.service_start <= stop.time_window_end + _TOL:
            continue
        violations.append(
            Violation(
                order_id=stop.order_id,
                kind="time_window_miss",
                message=(
                    f"service_start ({stop.service_start}) exceeds "
                    f"time_window_end ({stop.time_window_end}) at "
                    f"stop {stop.node_id!r} (index {stop.sequence_index})"
                ),
            )
        )

    # ---- Check 5: service_time 一致性 -------------------------------------
    # 仅对客户站（order_id is not None）检查；仓库 stop 不进行服务，期望
    # service_end == service_start（服务时长为 0），不在此处校验。
    for stop in stops:
        if stop.order_id is None:
            continue
        expected_end = stop.service_start + service_time
        if abs(stop.service_end - expected_end) <= _TOL:
            continue
        violations.append(
            Violation(
                order_id=stop.order_id,
                kind="service_time_overflow",
                message=(
                    f"service_end ({stop.service_end}) differs from "
                    f"service_start + service_time "
                    f"({stop.service_start} + {service_time} = "
                    f"{expected_end}) at stop {stop.node_id!r} "
                    f"(index {stop.sequence_index})"
                ),
            )
        )

    # ---- 输出 --------------------------------------------------------------
    if not violations:
        return FeasibilityReport(is_feasible=True)
    return FeasibilityReport(is_feasible=False, violations=tuple(violations))


__all__ = ["check_feasibility"]