"""业务枚举类型集中定义。

将所有 Enum 集中放置以避免循环引用，并便于序列化（JSON 友好字符串值）。

注：本项目**仅使用 Python 标准库** ``enum``，未依赖任何第三方库。
"""

from __future__ import annotations

from enum import Enum


class NodeType(str, Enum):
    """配送网络节点的物理角色。"""

    WAREHOUSE = "warehouse"  # 仓库 / 始发点
    CUSTOMER = "customer"    # 客户 / 送达点
    TRANSFER = "transfer"    # 中转站 / 临时仓储与转运点


class TrafficStatus(str, Enum):
    """道路当前的交通状态。

    Phase 1 仅作为边的可观测属性存在，不影响算法行为。
    后续 Phase 引入动态交通时将参与路径重规划。
    """

    CLEAR = "clear"          # 畅通
    LIGHT = "light"          # 轻微拥堵
    MODERATE = "moderate"    # 一般拥堵
    CONGESTED = "congested"  # 严重拥堵
    BLOCKED = "blocked"      # 阻断（暂不可通行）


class VehicleStatus(str, Enum):
    """配送车辆的工作状态。"""

    IDLE = "idle"            # 停在仓库，待派单
    LOADING = "loading"      # 装货中
    DELIVERING = "delivering"  # 正在执行配送任务
    RETURNING = "returning"  # 完成配送、回程途中
    MAINTENANCE = "maintenance"  # 维护中 / 不可用


class CourierStatus(str, Enum):
    """配送员当前工作状态。"""

    IDLE = "idle"            # 空闲等待派单
    DELIVERING = "delivering"  # 正在执行配送任务
    RESTING = "resting"      # 休息
    OFFLINE = "offline"      # 离线 / 不可用


class OrderPriority(str, Enum):
    """订单优先级。"""

    NORMAL = "normal"
    URGENT = "urgent"


class OrderStatus(str, Enum):
    """订单生命周期状态。"""

    PENDING = "pending"        # 待配送
    IN_TRANSIT = "in_transit"  # 配送中
    DELIVERED = "delivered"    # 已完成
    EXPIRED = "expired"        # 超时（超过 time_window_end 仍未送达）
    CREATED = "created"        # 已创建，尚未入待处理队列
    PLANNED = "planned"        # 已规划，尚未出发
    CANCELLED = "cancelled"    # 已取消，终态
