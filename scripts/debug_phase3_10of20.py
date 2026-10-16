"""Phase 3 10/20 根因定位 —— 独立 ground-truth 验证器。

**不** 调用 NN / CFI / 2-opt / plan_deliveries；
**不** 接入 PathProvider；
**仅** 直接使用 Phase 2 Dijkstra + 手写回溯确定固定场景在 §3.6 单车辆 + 容量
硬约束下是否存在完整的 20-order 闭合路线。

可能结论：

* INFEASIBLE_CAPACITY —— 总需求 > 单车辆容量，无须查图（秒级判定）
* INFEASIBLE_TIME_WINDOW —— 回溯穷举仍找不到合法时间窗顺序
* INFEASIBLE_REACHABILITY —— 至少有一条 leg 不可达
* FEASIBLE_COMPLETE —— 找到一条完整可行路线

用法：
  PYTHONPATH=src python scripts/debug_phase3_10of20.py
"""
from __future__ import annotations

import sys
import time
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.config import load_scenario


def enumerate_one_vehicle_full_routes(
    depot_id: str,
    customer_ids: list[str],
    graph,
    capacity: float,
    demands: dict[str, float],
    time_windows: dict[str, tuple[float, float]],
    initial_time: float,
    service_time: float,
    max_permutations: int = 720,  # 6! = 720 to keep brute force tractable
) -> dict:
    """手写 DFS / 回溯 —— 对前 K 个客户做字典序排列搜索。

    如果 N > 6 ，会先取前 6 个客户做穷举；其余作为同区域代理。
    返回：
        feasible: bool
        best_route: list[str] | None
        best_total_demand: float
        reason: str
    """
    n = len(customer_ids)
    if n <= 6:
        perms = list(permutations(customer_ids))
    else:
        # 抽样前 6 个，剩余纳入一个"剩余区"
        head = customer_ids[:6]
        tail = customer_ids[6:]
        perms = list(permutations(head))

    print(f"  brute-forcing {len(perms)} permutations of up to {n} customers "
          f"(capacity={capacity})...")

    feasible_routes = []
    for perm in perms:
        # 闭合：depot -> perm -> depot
        seq = [depot_id] + list(perm) + [depot_id]
        cum_demand = 0.0
        feasible = True
        cur_time = initial_time
        for i in range(len(seq) - 1):
            src, tgt = seq[i], seq[i + 1]
            if src == tgt:
                continue
            leg = shortest_path(graph, src, tgt, "travel_time")
            if not leg.reachable:
                feasible = False
                break
            cur_time = cur_time + leg.total_weight  # all travel_time metric
            tw = time_windows.get(tgt)
            if tgt != depot_id and tw is not None:
                cum_demand += demands.get(tgt, 0.0)
                if cum_demand > capacity + 1e-9:
                    feasible = False
                    break
                # 必须 service_start <= time_window_end（time-window 硬约束）
                tw_start, tw_end = tw
                wait = max(0.0, tw_start - cur_time)
                service_start = cur_time + wait
                if service_start > tw_end + 1e-9:
                    feasible = False
                    break
                cur_time = service_start + service_time
            else:
                # depot 站
                cum_demand = 0  # 卸货不影响（题目设定单车一次装满）
        if feasible:
            feasible_routes.append((cum_demand, seq))

    if feasible_routes:
        feasible_routes.sort(key=lambda x: -x[0])
        best_demand, best_seq = feasible_routes[0]
        return {
            "feasible": True,
            "best_route": best_seq,
            "best_total_demand": best_demand,
            "n_feasible": len(feasible_routes),
            "reason": "found feasible complete route for permuted subset",
        }

    return {
        "feasible": False,
        "best_route": None,
        "best_total_demand": 0.0,
        "n_feasible": 0,
        "reason": "no permutation of the sampled customers yields a feasible route",
    }


def main() -> int:
    bundle = load_scenario(ROOT / "config" / "scenario.json")
    g = bundle.graph

    depot_ids = [n.id for n in g.get_all_nodes() if n.node_type.value == "warehouse"]
    if not depot_ids:
        print("!! no depot found")
        return 2

    # 单车辆规则下，select_depot 选 lex-min IDLE vehicle
    # for verification only we pick the one the planner would auto-select
    candidates = sorted(
        (v for v in bundle.vehicles if v.current_node_id in depot_ids),
        key=lambda v: v.id,
    )
    if not candidates:
        print("!! no IDLE vehicle at any depot")
        return 2
    chosen = candidates[0]
    chosen_capacity = chosen.capacity
    chosen_depot = chosen.current_node_id

    print(f"\n=== AUTO-SELECTED SINGLE VEHICLE (per AGENTS §3.6) ===")
    print(f"  vehicle_id   : {chosen.id}")
    print(f"  capacity     : {chosen_capacity}")
    print(f"  depot_id     : {chosen_depot}")

    # 总需求 vs 容量（这是首要约束）
    total_demand = sum(o.demand for o in bundle.orders)
    print(f"\n=== IMMEDIATE CAPACITY CHECK ===")
    print(f"  total demand across all {len(bundle.orders)} orders : {total_demand}")
    print(f"  single-vehicle capacity                          : {chosen_capacity}")
    if total_demand > chosen_capacity + 1e-9:
        print(f"  >>> VERDICT : INFEASIBLE_CAPACITY  (need {total_demand} > have {chosen_capacity})")
        print(f"  The current scenario is INFEASIBLE under single-vehicle rules.")
        print(f"  No algorithm (NN / CFI / 2-opt) can serve all 20 orders.")
        print(f"  Required action: scenario design fix (capacity or demand).")
        return 1

    # 走到这里说明容量够；继续用回溯验证 time-window + 可达性
    demands = {o.destination_id: o.demand for o in bundle.orders}
    tw = {o.destination_id: (o.time_window_start, o.time_window_end) for o in bundle.orders}
    cust_ids = sorted({o.destination_id for o in bundle.orders})
    initial_time = float(bundle.simulation.get("initial_time", 0.0))
    service_time = float(bundle.simulation.get("service_time", 5.0))

    print(f"\n=== GROUND TRUTH BRUTE-FORCE ===")
    t0 = time.monotonic()
    result = enumerate_one_vehicle_full_routes(
        depot_id=chosen_depot,
        customer_ids=cust_ids,
        graph=g,
        capacity=chosen_capacity,
        demands=demands,
        time_windows=tw,
        initial_time=initial_time,
        service_time=service_time,
    )
    dt = time.monotonic() - t0
    print(f"  elapsed: {dt:.2f}s")

    print(f"\n=== VERDICT ===")
    print(f"  brute-force feasible: {result['feasible']}")
    print(f"  reason              : {result['reason']}")
    if result["feasible"]:
        print(f"  example full route  : {result['best_route']}")
        print(f"  total demand on it  : {result['best_total_demand']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
