"""JSON 场景配置的加载、解析与强校验。

关键设计：

* 与 ``LogisticsGraph`` 解耦 —— 仅消费 ``Node`` / ``Edge`` 等纯数据类，
  同时通过 ``ScenarioBundle`` 暴露「配置驱动」的对象层。
* 所有数值校验在加载路径中执行，加载失败抛 ``ConfigError``；
* 唯一被允许的第三方依赖是 Python 标准库（``json``）；
* 完全不引用任何 Web 框架 / 数据库 / 第三方图算法库。
"""

from __future__ import annotations

import json
import math
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logiroute.core.couriers import Courier
from logiroute.core.edges import Edge
from logiroute.core.enums import (
    CourierStatus,
    NodeType,
    OrderPriority,
    OrderStatus,
    TrafficStatus,
    VehicleStatus,
)
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph


# ---------------------------------------------------------------------------
#  课程最低指标
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioLimits:
    """课程规格所要求的最小节点 / 边 / 类型数。"""

    min_nodes: int = 30
    min_warehouses: int = 2
    min_customers: int = 15
    min_transfers: int = 3
    min_edges: int = 50


# ---------------------------------------------------------------------------
#  错误类型
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """配置加载或校验失败。"""

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


# ---------------------------------------------------------------------------
#  Bundle —— 加载后的强类型对象集合
# ---------------------------------------------------------------------------


@dataclass
class ScenarioBundle:
    """从 JSON 配置构建出的场景对象集合。

    注意：``graph`` 已经是「填充完毕、校验通过」的 ``LogisticsGraph``，
    后续算法层可直接基于 ``graph`` 工作。
    """

    name: str
    mode: str
    random_seed: int
    graph: LogisticsGraph
    vehicles: list[Vehicle] = field(default_factory=list)
    couriers: list[Courier] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    simulation: dict[str, Any] = field(default_factory=dict)
    optimization: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  主入口
# ---------------------------------------------------------------------------


def load_scenario(path: str | Path) -> ScenarioBundle:
    """从文件路径加载场景。Path 由调用方提供。"""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"scenario file not found: {p}", path=str(p))
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read scenario file: {p}", path=str(p)) from exc
    data = json.loads(raw)
    return load_scenario_from_dict(data)


def load_scenario_from_file(path: str | Path) -> ScenarioBundle:
    """语义别名：与 :func:`load_scenario` 同义。"""
    return load_scenario(path)


def load_scenario_from_dict(data: dict[str, Any]) -> ScenarioBundle:
    """从已解析的 dict 构造 :class:`ScenarioBundle`。

    Raises:
        ConfigError: 任何字段缺失、非法、引用不存在节点等情况。
    """
    limits = ScenarioLimits()
    # ---- scenario 段 ----
    if not isinstance(data, dict):
        raise ConfigError("scenario root must be a JSON object")
    scenario_section = data.get("scenario")
    if not isinstance(scenario_section, dict):
        raise ConfigError("missing 'scenario' section")
    name = _require_str(scenario_section, "name")
    mode = _require_str(scenario_section, "mode")
    if mode != "fixed":
        raise ConfigError(
            f"scenario.mode must be 'fixed' in Phase 1, got {mode!r}",
            path="scenario.mode",
        )
    seed = _require_int(scenario_section, "random_seed")

    # ---- network 段 ----
    network = data.get("network")
    if not isinstance(network, dict):
        raise ConfigError("missing 'network' section")
    if network.get("directed") is not True:
        raise ConfigError("network.directed must be true", path="network.directed")
    raw_nodes = network.get("nodes")
    raw_edges = network.get("edges")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ConfigError("network.nodes must be a non-empty list")
    if not isinstance(raw_edges, list):
        raise ConfigError("network.edges must be a list")

    # 节点
    nodes: list[Node] = []
    seen_node_ids: set[str] = set()
    for idx, raw in enumerate(raw_nodes):
        try:
            node = _parse_node(raw)
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"node[{idx}] invalid: {exc}", path=f"network.nodes[{idx}]"
            ) from exc
        if node.id in seen_node_ids:
            raise ConfigError(
                f"duplicate node id: {node.id!r}", path=f"network.nodes[{idx}].id"
            )
        seen_node_ids.add(node.id)
        nodes.append(node)

    # 类型与节点数下界
    type_counts = Counter(n.node_type for n in nodes)
    if len(nodes) < limits.min_nodes:
        raise ConfigError(
            f"need at least {limits.min_nodes} nodes, got {len(nodes)}",
            path="network.nodes",
        )
    if type_counts[NodeType.WAREHOUSE] < limits.min_warehouses:
        raise ConfigError(
            f"need at least {limits.min_warehouses} warehouses, "
            f"got {type_counts[NodeType.WAREHOUSE]}",
            path="network.nodes[type=warehouse]",
        )
    if type_counts[NodeType.CUSTOMER] < limits.min_customers:
        raise ConfigError(
            f"need at least {limits.min_customers} customers, "
            f"got {type_counts[NodeType.CUSTOMER]}",
            path="network.nodes[type=customer]",
        )
    if type_counts[NodeType.TRANSFER] < limits.min_transfers:
        raise ConfigError(
            f"need at least {limits.min_transfers} transfers, "
            f"got {type_counts[NodeType.TRANSFER]}",
            path="network.nodes[type=transfer]",
        )

    # 边：先校验字段，再构造图
    if len(raw_edges) < limits.min_edges:
        raise ConfigError(
            f"need at least {limits.min_edges} edges, got {len(raw_edges)}",
            path="network.edges",
        )
    edges: list[Edge] = []
    for idx, raw in enumerate(raw_edges):
        try:
            edge = _parse_edge(raw, seen_node_ids)
        except (ValueError, TypeError, KeyError) as exc:
            raise ConfigError(
                f"edge[{idx}] invalid: {exc}", path=f"network.edges[{idx}]"
            ) from exc
        edges.append(edge)

    # ---- 构造图 + 校验邻接合法性 ----
    graph = LogisticsGraph()
    for n in nodes:
        graph.add_node(n)
    for e in edges:
        try:
            graph.add_edge(e)
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"failed to add edge to graph: {exc}",
                path=f"network.edges source={e.source_id} target={e.target_id}",
            ) from exc

    # 连通性校验：至少弱连通（任意两个节点可达，方向无关）；
    # 对于配送任务「仓库出发并返回仓库」的可达性，应再要求强连通。
    if not _is_weakly_connected(graph, nodes):
        raise ConfigError(
            "network is not weakly connected: some node isolated from the rest",
            path="network.edges",
        )
    if not _is_strongly_connected(graph, nodes):
        raise ConfigError(
            "network is not strongly connected: cannot form a closed tour from any warehouse",
            path="network.edges",
        )

    # ---- vehicles ----
    vehicles: list[Vehicle] = []
    raw_vehicles = data.get("vehicles", [])
    if not isinstance(raw_vehicles, list):
        raise ConfigError("vehicles must be a list")
    seen_v_ids: set[str] = set()
    for idx, raw in enumerate(raw_vehicles):
        try:
            v = _parse_vehicle(raw)
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"vehicles[{idx}] invalid: {exc}", path=f"vehicles[{idx}]"
            ) from exc
        if v.id in seen_v_ids:
            raise ConfigError(
                f"duplicate vehicle id: {v.id!r}", path=f"vehicles[{idx}].id"
            )
        if v.current_node_id and v.current_node_id not in seen_node_ids:
            raise ConfigError(
                f"vehicle {v.id!r} references unknown current_node_id "
                f"{v.current_node_id!r}",
                path=f"vehicles[{idx}].current_node_id",
            )
        seen_v_ids.add(v.id)
        vehicles.append(v)

    # ---- couriers ----
    couriers: list[Courier] = []
    raw_couriers = data.get("couriers", [])
    if not isinstance(raw_couriers, list):
        raise ConfigError("couriers must be a list")
    seen_co_ids: set[str] = set()
    for idx, raw in enumerate(raw_couriers):
        try:
            c = _parse_courier(raw)
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"couriers[{idx}] invalid: {exc}", path=f"couriers[{idx}]"
            ) from exc
        if c.id in seen_co_ids:
            raise ConfigError(
                f"duplicate courier id: {c.id!r}", path=f"couriers[{idx}].id"
            )
        if c.vehicle_id not in seen_v_ids:
            raise ConfigError(
                f"courier {c.id!r} references unknown vehicle {c.vehicle_id!r}",
                path=f"couriers[{idx}].vehicle_id",
            )
        seen_co_ids.add(c.id)
        couriers.append(c)

    # ---- orders ----
    orders: list[Order] = []
    raw_orders = data.get("orders", [])
    if not isinstance(raw_orders, list):
        raise ConfigError("orders must be a list")
    seen_o_ids: set[str] = set()
    for idx, raw in enumerate(raw_orders):
        try:
            o = _parse_order(raw)
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"orders[{idx}] invalid: {exc}", path=f"orders[{idx}]"
            ) from exc
        if o.id in seen_o_ids:
            raise ConfigError(
                f"duplicate order id: {o.id!r}", path=f"orders[{idx}].id"
            )
        if o.destination_id not in seen_node_ids:
            raise ConfigError(
                f"order {o.id!r} references unknown destination_id "
                f"{o.destination_id!r}",
                path=f"orders[{idx}].destination_id",
            )
        seen_o_ids.add(o.id)
        orders.append(o)

    # ---- simulation / optimization：仅做最浅校验 ----
    sim = data.get("simulation", {})
    if not isinstance(sim, dict):
        raise ConfigError("simulation must be an object")
    if "initial_time" in sim and not isinstance(sim["initial_time"], (int, float)):
        raise ConfigError("simulation.initial_time must be a number")
    opt = data.get("optimization", {})
    if not isinstance(opt, dict):
        raise ConfigError("optimization must be an object")
    if "default_objective" in opt:
        default_obj = opt["default_objective"]
        if default_obj not in ("distance", "travel_time", "cost"):
            raise ConfigError(
                "optimization.default_objective must be one of "
                "{distance, travel_time, cost}"
            )

    return ScenarioBundle(
        name=name,
        mode=mode,
        random_seed=seed,
        graph=graph,
        vehicles=vehicles,
        couriers=couriers,
        orders=orders,
        simulation=sim,
        optimization=opt,
        metadata=data.get("metadata", {}) if isinstance(data.get("metadata", {}), dict) else {},
    )


# ---------------------------------------------------------------------------
#  内部字段解析器
# ---------------------------------------------------------------------------


def _require_str(section: dict, *keys: str) -> str:
    cur: Any = section
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise ConfigError(f"missing key: {'.'.join(keys)}", path='.'.join(keys))
        cur = cur[k]
    if not isinstance(cur, str) or not cur.strip():
        raise ConfigError(f"invalid string at {'.'.join(keys)}", path='.'.join(keys))
    return cur


def _require_int(section: dict, *keys: str) -> int:
    cur: Any = section
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise ConfigError(f"missing key: {'.'.join(keys)}", path='.'.join(keys))
        cur = cur[k]
    if isinstance(cur, bool) or not isinstance(cur, int):
        raise ConfigError(f"invalid int at {'.'.join(keys)}", path='.'.join(keys))
    return cur


def _parse_node(raw: Any) -> Node:
    if not isinstance(raw, dict):
        raise ValueError("node must be an object")
    nid = raw.get("id")
    name = raw.get("name")
    type_str = raw.get("type")
    x = raw.get("x")
    y = raw.get("y")
    if type_str not in ("warehouse", "customer", "transfer"):
        raise ValueError(f"invalid node type: {type_str!r}")
    node_type = NodeType(type_str)
    # Node dataclass performs its own validation
    return Node(id=nid, name=name, node_type=node_type, x=float(x), y=float(y))


def _parse_edge(raw: Any, known_nodes: set[str]) -> Edge:
    if not isinstance(raw, dict):
        raise ValueError("edge must be an object")
    src = raw.get("source")
    dst = raw.get("target")
    if src not in known_nodes:
        raise ValueError(f"unknown source node {src!r}")
    if dst not in known_nodes:
        raise ValueError(f"unknown target node {dst!r}")
    distance = raw.get("distance")
    travel_time = raw.get("travel_time")
    cost = raw.get("cost")
    traffic = raw.get("traffic_status", "clear")
    if traffic not in {t.value for t in TrafficStatus}:
        raise ValueError(f"invalid traffic_status: {traffic!r}")
    return Edge(
        source_id=src,
        target_id=dst,
        distance=float(distance),
        travel_time=float(travel_time),
        cost=float(cost),
        traffic_status=TrafficStatus(traffic),
    )


def _parse_vehicle(raw: Any) -> Vehicle:
    if not isinstance(raw, dict):
        raise ValueError("vehicle must be an object")
    vid = raw.get("id")
    capacity = raw.get("capacity")
    current_load = float(raw.get("current_load", 0.0))
    node = raw.get("current_node_id", "")
    status_str = raw.get("status", "idle")
    if status_str not in {s.value for s in VehicleStatus}:
        raise ValueError(f"invalid vehicle status: {status_str!r}")
    return Vehicle(
        id=vid,
        capacity=float(capacity),
        current_load=current_load,
        current_node_id=str(node),
        status=VehicleStatus(status_str),
    )


def _parse_courier(raw: Any) -> Courier:
    if not isinstance(raw, dict):
        raise ValueError("courier must be an object")
    cid = raw.get("id")
    name = raw.get("name")
    vehicle_id = raw.get("vehicle_id")
    status_str = raw.get("status", "idle")
    if status_str not in {s.value for s in CourierStatus}:
        raise ValueError(f"invalid courier status: {status_str!r}")
    return Courier(
        id=cid,
        name=name,
        vehicle_id=str(vehicle_id),
        status=CourierStatus(status_str),
    )


def _parse_order(raw: Any) -> Order:
    if not isinstance(raw, dict):
        raise ValueError("order must be an object")
    oid = raw.get("id")
    dest = raw.get("destination_id")
    demand = raw.get("demand")
    tw_start = raw.get("time_window_start")
    tw_end = raw.get("time_window_end")
    priority_str = raw.get("priority", "normal")
    status_str = raw.get("status", "pending")
    if priority_str not in {p.value for p in OrderPriority}:
        raise ValueError(f"invalid order priority: {priority_str!r}")
    if status_str not in {s.value for s in OrderStatus}:
        raise ValueError(f"invalid order status: {status_str!r}")
    return Order(
        id=oid,
        destination_id=str(dest),
        demand=float(demand),
        time_window_start=float(tw_start),
        time_window_end=float(tw_end),
        priority=OrderPriority(priority_str),
        status=OrderStatus(status_str),
    )


# ---------------------------------------------------------------------------
#  连通性自检（标准库实现，无第三方依赖）
# ---------------------------------------------------------------------------


def _is_weakly_connected(graph: LogisticsGraph, nodes: list[Node]) -> bool:
    """弱连通性：在忽略方向的项目化图上，从任意节点都能到达任意节点。

    Time   : O(V + E) —— BFS 一次。
    Space  : O(V) 队列与 visited 集合。
    """
    if not nodes:
        return True
    adjacency: dict[str, list[str]] = {n.id: [] for n in nodes}
    for src_id in graph.node_ids:
        for edge in graph.get_neighbors(src_id):
            adjacency[src_id].append(edge.target_id)
            adjacency[edge.target_id].append(src_id)
    start = nodes[0].id
    visited = {start}
    queue: deque[str] = deque([start])
    while queue:
        u = queue.popleft()
        for v in adjacency[u]:
            if v not in visited:
                visited.add(v)
                queue.append(v)
    return visited == {n.id for n in nodes}


def _is_strongly_connected(graph: LogisticsGraph, nodes: list[Node]) -> bool:
    """强连通性：在有向项目化图上，任意节点间互达。

    使用 Kosaraju 双遍 DFS（手写递归版以避免 ``set`` 与 ``reversed`` 的依赖）：
    若正图与反图都能从同一起点访问全部节点，则原图强连通。

    Time   : O(V + E)
    Space  : O(V) 栈与 visited。
    """
    if not nodes:
        return True
    node_ids = [n.id for n in nodes]
    adjacency_fwd: dict[str, list[str]] = {n.id: [] for n in nodes}
    adjacency_rev: dict[str, list[str]] = {n.id: [] for n in nodes}
    for src_id in node_ids:
        for edge in graph.get_neighbors(src_id):
            adjacency_fwd[src_id].append(edge.target_id)
            adjacency_rev[edge.target_id].append(src_id)
    start = node_ids[0]
    if not _dfs_reaches_all(start, adjacency_fwd, set(node_ids)):
        return False
    if not _dfs_reaches_all(start, adjacency_rev, set(node_ids)):
        return False
    return True


def _dfs_reaches_all(
    start: str,
    adjacency: dict[str, list[str]],
    all_ids: set[str],
) -> bool:
    """手写 DFS；不使用任何第三方库。

    Time   : O(V + E)
    Space  : O(V) 显式栈与 visited。
    """
    visited: set[str] = set()
    stack: list[str] = [start]
    while stack:
        u = stack.pop()
        if u in visited:
            continue
        visited.add(u)
        for v in adjacency.get(u, []):
            if v not in visited:
                stack.append(v)
    return visited == all_ids


# 仅保留给单元测试 / debug 使用的工具方法
__all__ = [
    "ConfigError",
    "ScenarioBundle",
    "ScenarioLimits",
    "load_scenario",
    "load_scenario_from_file",
    "load_scenario_from_dict",
]
