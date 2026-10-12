"""pytest 全局 fixtures。

提供测试常用的工厂方法，用于快速构造小型配送网络。
"""

from __future__ import annotations

import pytest

from logiroute.core.couriers import Courier
from logiroute.core.enums import (
    CourierStatus,
    NodeType,
    OrderPriority,
    OrderStatus,
    TrafficStatus,
)
from logiroute.core.edges import Edge
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph


@pytest.fixture
def make_node():
    """创建一个生成 ``Node`` 的工厂函数。"""

    def _make(
        node_id: str,
        name: str = "node",
        node_type: NodeType = NodeType.CUSTOMER,
        x: float = 0.0,
        y: float = 0.0,
    ) -> Node:
        return Node(id=node_id, name=name, node_type=node_type, x=x, y=y)

    return _make


@pytest.fixture
def make_edge():
    """创建一个生成 ``Edge`` 的工厂函数。"""

    def _make(
        source_id: str,
        target_id: str,
        *,
        distance: float = 1.0,
        travel_time: float = 1.0,
        cost: float = 1.0,
        traffic_status: TrafficStatus = TrafficStatus.CLEAR,
    ) -> Edge:
        return Edge(
            source_id=source_id,
            target_id=target_id,
            distance=distance,
            travel_time=travel_time,
            cost=cost,
            traffic_status=traffic_status,
        )

    return _make


@pytest.fixture
def make_graph():
    """返回一个空的 :class:`LogisticsGraph`。

    注意：fixture 本身调用 ``clear()`` 以保证完全隔离，避免偶发的状态污染。
    """

    def _make() -> LogisticsGraph:
        return LogisticsGraph()

    return _make


@pytest.fixture
def sample_graph():
    """构造一个 5 节点、典型出边方向的小型图供多数测试复用。

    结构：
        仓库 A (0,0) -> 中转 T1 (1,1) -> 客户 C1 (2,2)
        仓库 A -> 中转 T2 (1,-1) -> 客户 C2 (2,-2)
        中转 T1 -> 客户 C2
    """
    g = LogisticsGraph()
    nodes = [
        Node("A", "主仓库", NodeType.WAREHOUSE, 0.0, 0.0),
        Node("T1", "中转A", NodeType.TRANSFER, 1.0, 1.0),
        Node("T2", "中转B", NodeType.TRANSFER, 1.0, -1.0),
        Node("C1", "客户1", NodeType.CUSTOMER, 2.0, 2.0),
        Node("C2", "客户2", NodeType.CUSTOMER, 2.0, -2.0),
    ]
    edges = [
        Edge("A", "T1", distance=1.0, travel_time=2.0, cost=1.0),
        Edge("A", "T2", distance=1.0, travel_time=2.0, cost=1.0),
        Edge("T1", "C1", distance=1.0, travel_time=1.0, cost=1.0),
        Edge("T2", "C2", distance=1.0, travel_time=1.0, cost=1.0),
        Edge("T1", "C2", distance=2.0, travel_time=3.0, cost=2.0),
    ]
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    return g


@pytest.fixture
def make_vehicle():
    def _make(
        vehicle_id: str = "V1",
        max_capacity: float = 100.0,
        current_load: float = 0.0,
        current_node_id: str = "",
    ) -> Vehicle:
        return Vehicle(
            id=vehicle_id,
            max_capacity=max_capacity,
            current_load=current_load,
            current_node_id=current_node_id,
        )

    return _make


@pytest.fixture
def make_courier():
    def _make(
        courier_id: str = "CO1",
        name: str = "courier",
        vehicle_id: str = "V1",
        status: CourierStatus = CourierStatus.IDLE,
    ) -> Courier:
        return Courier(
            id=courier_id, name=name, vehicle_id=vehicle_id, status=status
        )

    return _make


@pytest.fixture
def make_order():
    def _make(
        order_id: str = "O1",
        destination_node_id: str = "C1",
        demand: float = 1.0,
        time_window_start: float = 0.0,
        time_window_end: float = 60.0,
        priority: OrderPriority = OrderPriority.NORMAL,
        status: OrderStatus = OrderStatus.PENDING,
    ) -> Order:
        return Order(
            id=order_id,
            destination_node_id=destination_node_id,
            demand=demand,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            priority=priority,
            status=status,
        )

    return _make
