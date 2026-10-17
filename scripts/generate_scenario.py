"""生成固定标准测试场景的脚本。

本脚本可重复执行，输出 ``config/scenario.json``：
* 不依赖任何第三方库（仅使用 Python 标准库 ``json`` / ``random`` / ``math``）。
* 使用固定 seed=42 保证产出的网络、车辆、订单在多次执行下完全一致。
* 完全确定式生成，避免 Phase 1 不允许的「随机路网生成器」概念；
  这里只是一份「固定场景」的机器可读形式。

当 ``config/scenario.json`` 已存在时，本脚本可选地选择不覆盖，
或者通过 ``python scripts/generate_scenario.py --force`` 强制覆盖。
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

# 课程规格下限
MIN_NODES = 30
MIN_WAREHOUSES = 2
MIN_CUSTOMERS = 15
MIN_TRANSFERS = 3
MIN_EDGES = 50

# 测试用固定 seed（与 config/scenario.json 中的 random_seed 保持一致）
SEED = 42

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "config" / "scenario.json"


# ---------------------------------------------------------------------------
#  网络拓扑生成（确定性）
# ---------------------------------------------------------------------------


def _build_nodes() -> list[dict]:
    """2 仓库 + 4 中转 + 29 客户 = 35 节点。

    节点坐标为示意性二维城市网格，不对应真实地理。
    """
    nodes: list[dict] = []
    # 2 仓库：分布于城市对角
    nodes.append({"id": "W1", "name": "主仓（北）", "type": "warehouse", "x": 0.0, "y": 9.0})
    nodes.append({"id": "W2", "name": "次仓（南）", "type": "warehouse", "x": 9.0, "y": 0.0})

    # 4 中转：城市四角各 1
    for i, (x, y) in enumerate([(2.0, 7.0), (7.0, 7.0), (2.0, 2.0), (7.0, 2.0)], start=1):
        nodes.append({
            "id": f"T{i}",
            "name": f"中转站{i}",
            "type": "transfer",
            "x": float(x),
            "y": float(y),
        })

    # 29 客户：撒在中部
    customer_rng = random.Random(SEED)
    for i in range(1, 30):
        nodes.append({
            "id": f"C{i}",
            "name": f"客户{i:02d}",
            "type": "customer",
            "x": round(customer_rng.uniform(1.0, 8.0), 2),
            "y": round(customer_rng.uniform(1.0, 8.0), 2),
        })
    return nodes


def _euclid(a: dict, b: dict) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _make_edge(
    src: dict, dst: dict, rng: random.Random
) -> dict:
    """构造一条 (src -> dst) 边，三类权重解耦。"""
    d = _euclid(src, dst)
    # 引入抖动因子（确定性，使用固定 rng）
    j_dist = rng.uniform(0.9, 1.15)
    j_time = rng.uniform(0.7, 1.4)        # 与距离解耦：拥堵可让时间更长
    j_cost = rng.uniform(0.4, 1.8)        # 与距离 / 时间解耦：高速昂贵、绕行便宜等
    # 三种度量采用不同物理量纲：distance 公里 / travel_time 分钟 / cost 元
    return {
        "source": src["id"],
        "target": dst["id"],
        "distance": round(d * j_dist, 3),
        "travel_time": round(d * j_time * 3.0, 3),   # ~3 分钟/公里 基准
        "cost": round(d * j_cost * 1.5, 3),
        "traffic_status": "clear",
    }


def _build_edges(nodes: list[dict]) -> list[dict]:
    """通过分轮机制造 80+ 条有向边，覆盖仓库 ↔ 中转 ↔ 客户的多层结构。"""
    rng = random.Random(SEED)
    by_id = {n["id"]: n for n in nodes}

    warehouses = [n for n in nodes if n["type"] == "warehouse"]
    transfers = [n for n in nodes if n["type"] == "transfer"]
    customers = [n for n in nodes if n["type"] == "customer"]

    edges: list[dict] = []

    def _add_undirected(a: dict, b: dict) -> None:
        edges.append(_make_edge(a, b, rng))
        edges.append(_make_edge(b, a, rng))

    # 第 1 轮：每个仓库连接所有中转（双向）
    for w in warehouses:
        for t in transfers:
            _add_undirected(w, t)

    # 第 2 轮：中转 ↔ 中转 形成环
    transfer_pairs = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    for i, j in transfer_pairs:
        _add_undirected(transfers[i], transfers[j])

    # 第 3 轮：每个中转连接其区域客户（按距离最近的前 7 个）
    customer_by_distance = sorted(
        customers, key=lambda c: _euclid(c, transfers[0])
    )
    # 静态分区：每 7 个客户对应 1 个中转
    for k, t in enumerate(transfers):
        my_customers = customers[k * 7:(k + 1) * 7] if k < 3 else customers[k * 7:]
        for c in my_customers:
            _add_undirected(t, c)

    # 第 4 轮：客户到客户「近邻连接」，增加交通便利但允许更长路径
    for c in customers:
        # 找最近的 3 个客户
        others = sorted(customers, key=lambda o: _euclid(c, o))
        for o in others[1:4]:
            if not _has_edge(edges, c["id"], o["id"]):
                edges.append(_make_edge(c, o, rng))
            if not _has_edge(edges, o["id"], c["id"]):
                edges.append(_make_edge(o, c, rng))

    # 第 5 轮：仓库 ↔ 中转之间的少量长距离「绕行」边（增加多路径选择）
    extra_pairs = [
        (transfers[0], warehouses[1]),  # T1 -> W2：跨城高速
        (transfers[2], warehouses[0]),  # T3 -> W1：跨城高速
    ]
    for a, b in extra_pairs:
        if not _has_edge(edges, a["id"], b["id"]):
            edges.append(_make_edge(a, b, rng))

    return edges


def _has_edge(edges: list[dict], src: str, dst: str) -> bool:
    for e in edges:
        if e["source"] == src and e["target"] == dst:
            return True
    return False


# ---------------------------------------------------------------------------
#  车辆 / 配送员 / 订单 / 仿真 / 优化段
# ---------------------------------------------------------------------------


def _build_vehicles() -> list[dict]:
    """严格单车辆：仅一辆 ``VH1`` 容量 250 kg @ ``W1``（主仓）。

    AGENTS.md §3.6 + 教师原题：场景中只能有一辆实际参与配送的车辆。
    """
    return [
        {"id": "VH1", "capacity": 250.0, "current_load": 0.0, "current_node_id": "W1",
         "status": "idle"},
    ]


def _build_couriers() -> list[dict]:
    """单配送员，跟随唯一车辆 ``VH1``。"""
    return [
        {"id": "CO1", "name": "配送员01", "vehicle_id": "VH1", "status": "idle"},
    ]


def _build_orders(nodes: list[dict]) -> list[dict]:
    """从客户节点派生订单；使用按距离排序的轮转窗口。"""
    customers = [n for n in nodes if n["type"] == "customer"]
    # 前 20 个客户有订单（覆盖 15 的最低门槛）
    target_customers = customers[:20]
    base_start = 9 * 60      # 9:00
    window_len = 120         # 2 小时
    orders: list[dict] = []
    for i, c in enumerate(target_customers, start=1):
        # 错开窗口，让「紧急」订单集中在 10:30 之前送达
        offset = (i % 6) * 20
        priority = "urgent" if i % 7 == 0 else "normal"
        # demand 与距离近似正相关，但加抖动
        demand = round(5.0 + (i % 5) * 2.5, 2)
        orders.append({
            "id": f"O{i:03d}",
            "destination_id": c["id"],
            "demand": demand,
            "time_window_start": float(base_start + offset),
            "time_window_end": float(base_start + offset + window_len),
            "priority": priority,
            "status": "pending",
        })
    return orders


def _build_simulation() -> dict:
    return {
        "initial_time": 540.0,        # 9:00 起步
        "traffic_update_interval": 30,  # 30 分钟一次路况更新
        "congestion_threshold": 0.20,   # 20% 升幅触发拥堵
        "service_time": 5.0,           # 每次送达服务耗时（分钟）
    }


def _build_optimization() -> dict:
    return {
        "default_objective": "distance",
        "weights": {
            "distance": 1.0,
            "travel_time": 1.0,
            "cost": 1.0,
        },
        "late_penalty_per_minute": 0.5,
        "expiry_grace_minutes": 10,
    }


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------


def build_scenario() -> dict:
    nodes = _build_nodes()
    edges = _build_edges(nodes)
    # 关键防御：确保 ≥30 / ≥60，否则立即抛出错误，让脚本自检失败
    assert len(nodes) >= MIN_NODES
    assert len(edges) >= MIN_EDGES
    n_warehouse = sum(1 for n in nodes if n["type"] == "warehouse")
    n_customer = sum(1 for n in nodes if n["type"] == "customer")
    n_transfer = sum(1 for n in nodes if n["type"] == "transfer")
    assert n_warehouse >= MIN_WAREHOUSES
    assert n_customer >= MIN_CUSTOMERS
    assert n_transfer >= MIN_TRANSFERS

    return {
        "scenario": {
            "name": "logiroute.standard.35",
            "mode": "fixed",
            "random_seed": SEED,
        },
        "network": {
            "directed": True,
            "nodes": nodes,
            "edges": edges,
        },
        "vehicles": _build_vehicles(),
        "couriers": _build_couriers(),
        "orders": _build_orders(nodes),
        "simulation": _build_simulation(),
        "optimization": _build_optimization(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 JSON")
    args = parser.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists() and not args.force:
        print(f"{OUTPUT_PATH} 已存在，未覆盖。传 --force 以覆盖。")
        return

    data = build_scenario()
    summary = {
        "nodes": len(data["network"]["nodes"]),
        "edges": len(data["network"]["edges"]),
        "warehouses": sum(1 for n in data["network"]["nodes"] if n["type"] == "warehouse"),
        "customers": sum(1 for n in data["network"]["nodes"] if n["type"] == "customer"),
        "transfers": sum(1 for n in data["network"]["nodes"] if n["type"] == "transfer"),
        "vehicles": len(data["vehicles"]),
        "couriers": len(data["couriers"]),
        "orders": len(data["orders"]),
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已写入 {OUTPUT_PATH}")
    print("场景摘要:", json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
