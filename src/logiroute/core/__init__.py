"""核心业务数据模型。

包含配送网络涉及的实体：节点、边、车辆、配送员、订单。

数据模型之间相互独立，不耦合到任何具体算法或 Web 框架。
"""

from logiroute.core.enums import (
    CourierStatus,
    NodeType,
    OrderPriority,
    OrderStatus,
    TrafficStatus,
)
from logiroute.core.couriers import Courier
from logiroute.core.edges import Edge
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle

__all__ = [
    "Courier",
    "CourierStatus",
    "Edge",
    "Node",
    "NodeType",
    "Order",
    "OrderPriority",
    "OrderStatus",
    "TrafficStatus",
    "Vehicle",
]
