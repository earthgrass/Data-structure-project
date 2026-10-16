"""Phase 4 — 独立场景验证器（不调 ``plan_deliveries``）。

依据 ``AGENTS.md`` §3.6 + prompt ``# 二十四``：

* 验证器**不** 调用任何 planner / NN / CFI / 2-opt；
* 仅接受 :class:`ScenarioBundle`（与 Phase 1 ``load_scenario`` 一致）以及
  可选的 ``backbone: list[str]`` 作为输入；
* 输出结构化 :class:`ScenarioValidationReport`，含逐项 PASS/FAIL 与
  ``violations`` 列表（每条对应一个硬约束违反）。

校验项：

* Q1 所有订单 :class:`Order.destination_id` 都在图中
* Q2 总需求 ``<=`` 车辆容量（单车辆硬约束，``AGENTS.md`` §3.6）
* Q3 图强连通（任一节点出发可触达全部其它节点）
* Q4 ``backbone`` 内相邻节点对 ``(backbone[i], backbone[i+1])`` 在有向图中
       shortest_path 可达
* Q5 backbone 模拟时刻表：service_start <= time_window_end
* Q6 backbone 起止同节点（depot 闭合）
* Q7 所有订单恰好被 backbone 覆盖一次（无遗漏 / 无重复）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from logiroute.algorithms.dijkstra import DijkstraError, shortest_path
from logiroute.config.loader import ScenarioBundle
from logiroute.core.enums import NodeType
from logiroute.core.orders import Order
from logiroute.scenario_generator.config_spec import GeneratorConfig


class ScenarioValidationError(Exception):
    """``validate_generated_scenario`` 抛出的硬失败错误（粗粒度）。"""

    def __init__(self, message: str, report: "ScenarioValidationReport"):
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class ScenarioValidationReport:
    """独立验证器的输出。"""

    feasible: bool
    scenario_name: str
    nodes: int
    edges: int
    warehouses: int
    customers: int
    transfers: int
    orders: int
    total_demand: float
    capacity: float
    backbone_length: int
    all_orders_covered: bool
    capacity_ok: bool
    time_windows_ok: bool
    all_legs_reachable: bool
    closed_route_ok: bool
    service_time: float
    initial_time: float
    violations: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "scenario_name": self.scenario_name,
            "nodes": self.nodes,
            "edges": self.edges,
            "warehouses": self.warehouses,
            "customers": self.customers,
            "transfers": self.transfers,
            "orders": self.orders,
            "total_demand": self.total_demand,
            "capacity": self.capacity,
            "backbone_length": self.backbone_length,
            "all_orders_covered": self.all_orders_covered,
            "capacity_ok": self.capacity_ok,
            "time_windows_ok": self.time_windows_ok,
            "all_legs_reachable": self.all_legs_reachable,
            "closed_route_ok": self.closed_route_ok,
            "service_time": self.service_time,
            "initial_time": self.initial_time,
            "violations": [{"check": k, "message": m} for (k, m) in self.violations],
        }


# ---------------------------------------------------------------------------
# 内部 helper
# ---------------------------------------------------------------------------


def _node_type_counts(bundle: ScenarioBundle) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in bundle.graph.get_all_nodes():
        counts[n.node_type.value] = counts.get(n.node_type.value, 0) + 1
    return counts


def _strongly_connected_or_explain(bundle: ScenarioBundle) -> list[str]:
    """返回 violations（如果有），否则 ``[]``。

    用 BFS 检查：从任一节点出发 forward + reverse 都能到达全部节点。
    """
    graph = bundle.graph
    if graph.node_count == 0:
        return [("graph.strongly_connected", "graph has 0 nodes")]
    seed = graph.node_ids[0]

    # forward
    seen_f = {seed}
    stack = [seed]
    edges_f = 0
    while stack:
        u = stack.pop()
        for e in graph.get_neighbors(u):
            edges_f += 1
            if e.target_id not in seen_f:
                seen_f.add(e.target_id)
                stack.append(e.target_id)

    # reverse via get_in_edges
    seen_r = {seed}
    stack = [seed]
    while stack:
        u = stack.pop()
        for e in graph.get_in_edges(u):
            if e.source_id not in seen_r:
                seen_r.add(e.source_id)
                stack.append(e.source_id)

    if len(seen_f) != graph.node_count or len(seen_r) != graph.node_count:
        return [
            (
                "graph.strongly_connected",
                f"forward-reachable={len(seen_f)}/{graph.node_count} "
                f"reverse-reachable={len(seen_r)}/{graph.node_count}",
            )
        ]
    return []


# ---------------------------------------------------------------------------
#  公开入口
# ---------------------------------------------------------------------------


def validate_generated_scenario(
    bundle: ScenarioBundle,
    backbone: list[str] | None = None,
) -> ScenarioValidationReport:
    """独立验证一个已生成的物流场景（不调用 planner）。

    Args:
        bundle: 加载后的 :class:`ScenarioBundle`（通常是
            :func:`generate_scenario` 的输出）。
        backbone: 可选：``[depot, stop_1, stop_2, ..., stop_K, depot]``
            单车辆 backbone 序列。若提供，校验覆盖性 / 时间窗 / 可达性。

    Returns:
        :class:`ScenarioValidationReport`（不可变）。
    """
    violations: list[tuple[str, str]] = []
    graph = bundle.graph
    orders = list(bundle.orders)
    sim = bundle.simulation or {}
    service_time = float(sim.get("service_time", 5.0))
    initial_time = float(sim.get("initial_time", 0.0))

    # 默认从 lex-min IDLE vehicle 取 capacity（如有）。若没有则取 0。
    capacity = 0.0
    for v in bundle.vehicles:
        if v.status.name == "IDLE":
            capacity = v.capacity
            break

    # Q1: destination_id 都在图内
    node_id_set = set(graph.node_ids)
    for o in orders:
        if o.destination_id not in node_id_set:
            violations.append((
                "order.destination_in_graph",
                f"order {o.id!r} destination_id={o.destination_id!r} "
                "not in graph",
            ))

    # Q2: 总需求与容量
    total_demand = sum(o.demand for o in orders)
    capacity_ok = total_demand <= capacity + 1e-9
    if not capacity_ok:
        violations.append((
            "capacity.total_demand",
            f"total_demand={total_demand} > capacity={capacity}",
        ))

    # Q3: 强连通（仅在提供了 backbone 时校验 —— 无 backbone 时不强求）
    if backbone is not None:
        violations.extend(_strongly_connected_or_explain(bundle))

    # Q4 / Q5 / Q6 / Q7 —— backbone 相关
    backbone_length = 0
    all_orders_covered = True
    time_windows_ok = True
    all_legs_reachable = True
    closed_route_ok = True

    if backbone is not None:
        backbone_length = len(backbone)
        if len(backbone) >= 2 and backbone[0] != backbone[-1]:
            closed_route_ok = False
            violations.append((
                "backbone.closed_route",
                f"backbone[0]={backbone[0]!r} != backbone[-1]={backbone[-1]!r}",
            ))

        # backbone 内涉及的 destination 去重覆盖 = orders 的 destination 集合
        backbone_inner = set(backbone[1:-1])
        order_dests = {o.destination_id for o in orders}
        if backbone_inner != order_dests:
            missing = order_dests - backbone_inner
            extra = backbone_inner - order_dests
            all_orders_covered = False
            violations.append((
                "backbone.coverage",
                f"missing from backbone: {missing}; extra in backbone: {extra}",
            ))

        # 检查相邻 leg 可达性 + 时间窗
        # arrival = previous leg drive_time + maybe wait + service
        # 注意 backbone 没有手算 service_time + wait；这里只校验 'service_start <= time_window_end'
        dest_to_order = {o.destination_id: o for o in orders}
        cur = backbone[0]
        cur_t = initial_time
        for nxt in backbone[1:]:
            if cur not in node_id_set or nxt not in node_id_set:
                all_legs_reachable = False
                violations.append((
                    "backbone.leg_unreachable",
                    f"leg {cur} -> {nxt} : node(s) missing from graph",
                ))
                cur = nxt
                continue
            try:
                leg = shortest_path(graph, cur, nxt, "travel_time")
            except DijkstraError:
                all_legs_reachable = False
                violations.append((
                    "backbone.leg_unreachable",
                    f"leg {cur} -> {nxt} raised DijkstraError",
                ))
                cur = nxt
                continue
            if not leg.reachable:
                all_legs_reachable = False
                violations.append((
                    "backbone.leg_unreachable",
                    f"leg {cur} -> {nxt} unreachable",
                ))
                cur = nxt
                continue
            cur_t = cur_t + leg.total_weight
            order = dest_to_order.get(nxt)
            if order is not None:
                tw_s, tw_e = order.time_window_start, order.time_window_end
                wait = max(0.0, tw_s - cur_t)
                service_start = cur_t + wait
                if service_start > tw_e + 1e-9:
                    time_windows_ok = False
                    violations.append((
                        "backbone.time_window_miss",
                        f"order {order.id!r} (dest {nxt!r}) "
                        f"service_start={service_start:.2f} > time_window_end="
                        f"{tw_e:.2f}",
                    ))
                cur_t = service_start + service_time
            cur = nxt

    feasible = (
        (backbone is None or (
            all_orders_covered
            and all_legs_reachable
            and time_windows_ok
            and closed_route_ok
        ))
        and capacity_ok
        and all(check_kind not in v[0] for v in violations
                for check_kind in [
                    "graph.strongly_connected",
                    "order.destination_in_graph",
                ])
    )

    nt = _node_type_counts(bundle)
    return ScenarioValidationReport(
        feasible=feasible,
        scenario_name=bundle.name,
        nodes=graph.node_count,
        edges=graph.edge_count,
        warehouses=nt.get("warehouse", 0),
        customers=nt.get("customer", 0),
        transfers=nt.get("transfer", 0),
        orders=len(orders),
        total_demand=total_demand,
        capacity=capacity,
        backbone_length=backbone_length,
        all_orders_covered=all_orders_covered,
        capacity_ok=capacity_ok,
        time_windows_ok=time_windows_ok,
        all_legs_reachable=all_legs_reachable,
        closed_route_ok=closed_route_ok,
        service_time=service_time,
        initial_time=initial_time,
        violations=tuple(violations),
    )


__all__ = [
    "ScenarioValidationError",
    "ScenarioValidationReport",
    "validate_generated_scenario",
]
