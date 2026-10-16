"""Phase 3 端到端演示脚本。

在固定场景 (config/scenario.json) 上分别以：
  - nearest_neighbor (distance)
  - nearest_neighbor (cost)
  - insertion (distance)
  - two_opt (distance)

四个配置跑 plan_deliveries 并打印闭环站点 / 总指标 / 未服务订单 /
缓存命中率，最后打印三算法在 distance 主目标下的对照表。
"""

from __future__ import annotations

import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.config import load_scenario  # noqa: E402
from logiroute.scheduling import plan_deliveries  # noqa: E402

SCENARIO = ROOT / "config" / "scenario.json"


def banner(text):
    bar = "=" * 78
    print(f"\n{bar}\n  {text}\n{bar}")


def short_path(plan, head=12):
    rs = plan.road_node_sequence
    if len(rs) <= head * 2:
        return " -> ".join(rs)
    return " -> ".join(rs[:head]) + f" ... ({len(rs) - 2*head} more) ... " + " -> ".join(rs[-head:])


def run(algorithm, objective):
    bundle = load_scenario(SCENARIO)
    t0 = time.monotonic()
    result = plan_deliveries(bundle, algorithm=algorithm, objective=objective)
    wall = time.monotonic() - t0
    return bundle, result, wall


def print_one(label, bundle, result, wall):
    banner(label)
    rp = result.route_plan
    print(f"  scenario_name   : {result.scenario_name}")
    print(f"  depot / vehicle : {result.depot_id} / {result.vehicle_id}")
    print(f"  courier         : {result.courier_id}")
    print(f"  algorithm       : {result.algorithm}")
    print(f"  objective       : {result.objective}")
    print(f"  stops           : {len(rp.stop_sequence)} (incl. depot x 2)")
    print(f"  road sequence   : ({len(rp.road_node_sequence)} nodes)")
    print(f"    " + short_path(rp))
    print(f"  served orders   : {len(result.served_order_ids)}/{len(bundle.orders)} -> {result.served_order_ids}")
    print(f"  total_distance  : {result.total_distance:.3f}")
    print(f"  total_travel_time: {result.total_travel_time:.3f}")
    print(f"  total_cost      : {result.total_cost:.3f}")
    print(f"  main_obj_total  : {result.main_objective_total:.3f}  (= main objective column)")
    print(f"  is_feasible     : {rp.is_feasible}  (route), global {result.is_feasible}")
    s = result.planning_stats
    print(f"  stats           : cache_hits={s.cache_hits} cache_misses={s.cache_misses} dijkstra_calls={s.dijkstra_calls} feasibility_checks={s.feasibility_checks} runtime={s.runtime_seconds*1000:.2f}ms (wall {wall*1000:.2f}ms)")
    if result.unserved_orders:
        print(f"  unserved ({len(result.unserved_orders)}):")
        for v in result.unserved_orders:
            print(f"    - {v.order_id} [{v.kind}] {v.message}")
    else:
        print(f"  unserved        : (none)")


def main():
    if not SCENARIO.is_file():
        print(f"!!  scenario file missing: {SCENARIO}")
        sys.exit(1)

    runs = [
        ("(1) NN + distance",   "nearest_neighbor", "distance"),
        ("(2) NN + cost",       "nearest_neighbor", "cost"),
        ("(3) insertion + distance", "insertion",   "distance"),
        ("(4) two_opt + distance",  "two_opt",    "distance"),
    ]
    results = []
    for label, algorithm, objective in runs:
        bundle, result, wall = run(algorithm, objective)
        print_one(label, bundle, result, wall)
        results.append((label, result))

    banner("对照表 (distance 主目标)")
    print(f"  {'label':<28} {'served':>6} {'unserved':>8} "
          f"{'distance':>10} {'travel_time':>12} {'cost':>10} "
          f"{'dijkstra':>8} {'runtime(ms)':>11}")
    for label, result in results:
        if result.objective != "distance":
            continue
        s = result.planning_stats
        print(f"  {label:<28} {len(result.served_order_ids):>6} "
              f"{len(result.unserved_orders):>8} "
              f"{result.total_distance:>10.3f} "
              f"{result.total_travel_time:>12.3f} "
              f"{result.total_cost:>10.3f} "
              f"{s.dijkstra_calls:>8} "
              f"{s.runtime_seconds * 1000:>11.2f}")

    banner("End")


if __name__ == "__main__":
    main()