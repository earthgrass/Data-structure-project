"""Phase 5 —— ``ScenarioBundle`` 序列化器。

将 Phase 1-4 强类型 dataclass 树转换为纯 Python 原生数据结构（dict /
list / str / float / int / None），便于：

* ``json.dumps`` 直接序列化（FastAPI / Pydantic 自动消费）；
* 前端 TypeScript 类型自动派生（**前端不复用** 任何 Pydantic / Python 类型）。

仅使用 Python 标准库，**不** 引入 Pydantic / cattrs 等序列化库，
避免对核心数据模型产生额外耦合。
"""
from __future__ import annotations

from typing import Any

from logiroute.config.loader import ScenarioBundle
from logiroute.core.couriers import Courier
from logiroute.core.edges import Edge
from logiroute.core.enums import (
    CourierStatus, NodeType, OrderPriority, OrderStatus,
    TrafficStatus, VehicleStatus,
)
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph


# ---------------------------------------------------------------------------
# 单对象序列化
# ---------------------------------------------------------------------------


def _node_to_dict(node: Node) -> dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.node_type.value,
        "x": float(node.x),
        "y": float(node.y),
    }


def _edge_to_dict(edge: Edge) -> dict[str, Any]:
    return {
        "source": edge.source_id,
        "target": edge.target_id,
        "distance": float(edge.distance),
        "travel_time": float(edge.travel_time),
        "cost": float(edge.cost),
        "traffic_status": edge.traffic_status.value,
    }


def _vehicle_to_dict(v: Vehicle) -> dict[str, Any]:
    return {
        "id": v.id,
        "capacity": float(v.capacity),
        "current_load": float(v.current_load),
        "current_node_id": v.current_node_id,
        "status": v.status.value,
    }


def _courier_to_dict(c: Courier) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "vehicle_id": c.vehicle_id,
        "status": c.status.value,
    }


def _order_to_dict(o: Order) -> dict[str, Any]:
    return {
        "id": o.id,
        "destination_id": o.destination_id,
        "demand": float(o.demand),
        "time_window_start": float(o.time_window_start),
        "time_window_end": float(o.time_window_end),
        "priority": o.priority.value,
        "status": o.status.value,
    }


# ---------------------------------------------------------------------------
# 图 / 场景 / 校验报告
# ---------------------------------------------------------------------------


def graph_to_dict(graph: LogisticsGraph) -> dict[str, Any]:
    """图 → JSON 友好结构（nodes + edges + summary）。"""
    nodes = [_node_to_dict(n) for n in graph.get_all_nodes()]
    edges: list[dict[str, Any]] = []
    for src_id in graph.node_ids:
        for edge in graph.get_neighbors(src_id):
            edges.append(_edge_to_dict(edge))
    return {
        "directed": True,
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "nodes": nodes,
        "edges": edges,
    }


def scenario_to_dict(
    bundle: ScenarioBundle, backbone: list[str] | None = None,
) -> dict[str, Any]:
    """ScenarioBundle → JSON 友好结构。

    ``backbone`` 作为独立字段附加在 ``scenario_metadata.backbone`` 之外，
    仍属于"生成器内部状态"，前端可读但不依赖（planner 看不到 backbone）。
    """
    return {
        "name": bundle.name,
        "mode": bundle.mode,
        "random_seed": bundle.random_seed,
        "graph": graph_to_dict(bundle.graph),
        "vehicles": [_vehicle_to_dict(v) for v in bundle.vehicles],
        "couriers": [_courier_to_dict(c) for c in bundle.couriers],
        "orders": [_order_to_dict(o) for o in bundle.orders],
        "simulation": dict(bundle.simulation),
        "optimization": dict(bundle.optimization),
        "metadata": dict(bundle.metadata),
        "backbone": list(backbone) if backbone is not None else None,
    }


__all__ = [
    "graph_to_dict",
    "scenario_to_dict",
]