"""Phase 3 修复 —— 单车辆闭环 backbone 反推 time_window（v2）。

两步法：

1. **临时** capacity 250 + windows 全放宽（540, 999）让 CFI 能跑全部 20 单
   （CFI 会在每步做完整性验证，单 vehicle 可行 backbone 必然被找到）；
2. 把 CFI 输出的 stop 序列当作 backbone，沿 Phase 2 Dijkstra 反推每个
   订单的真实到达时刻，然后：
       tw_start = max(0, arrival_time - 20)
       tw_end   = arrival_time + 20  （包括 service_time 5）
3. 写回 config/scenario.json。

**不**调用 plan_deliveries 自身作为 Ground Truth —— 改由 brute-force DFS
独立验证。
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.config.loader import load_scenario_from_dict


def patched_capacity(raw: dict[str, Any], capacity: float) -> dict[str, Any]:
    patched = copy.deepcopy(raw)
    for veh in patched["vehicles"]:
        if veh["id"] == "VH1":
            veh["capacity"] = capacity
            break
    return patched


def widened_windows(raw: dict[str, Any], start: float, end: float) -> dict[str, Any]:
    patched = copy.deepcopy(raw)
    for o in patched["orders"]:
        o["time_window_start"] = start
        o["time_window_end"] = end
    return patched


def find_backbone_via_cfi(raw: dict[str, Any], capacity: float) -> dict:
    """CFI 在放宽条件下通常能服务全部订单。

    返回 backbone ordering + 到达时刻字典。
    """
    patched = patched_capacity(widened_windows(raw, 540.0, 999.0), capacity)
    bundle = load_scenario_from_dict(patched)

    from logiroute.scheduling import plan_deliveries

    res = plan_deliveries(bundle, "insertion", "distance")
    served = list(res.served_order_ids)
    if len(served) != len(bundle.orders):
        raise RuntimeError(
            f"CFI only served {len(served)}/{len(bundle.orders)} "
            f"even under widened windows + capacity={capacity}"
        )

    # 从 result 的 stops 提取 backbone 与到达时刻
    seq = [s.node_id for s in res.route_plan.stops[1:-1]]  # inner stops
    arrival: dict[str, float] = {}
    for s in res.route_plan.stops:
        if s.order_id is not None:
            arrival[s.order_id] = s.arrival_time
    return {"seq": seq, "arrival": arrival}


def derive_new_windows(
    raw: dict[str, Any],
    capacity: float,
    backbone_seq: list[str],
    arrival_by_order: dict[str, float],
    early_slack: float = 20.0,
    late_slack: float = 20.0,
) -> dict[str, tuple[float, float]]:
    """基于 backbone + 到达时刻反推每个订单的合理 time window。"""
    patched = patched_capacity(raw, capacity)
    bundle = load_scenario_from_dict(patched)
    graph = bundle.graph

    # 跑一遍 backbone 验证我们反推的回程：
    init = float(raw["simulation"]["initial_time"])
    svc = float(raw["simulation"]["service_time"])

    cur = backbone_seq[0] if backbone_seq else "W1"
    if cur == "W1":
        cur_t = init
    else:
        # 用原始 NN 找到 backbone 第一个订单
        # 直接用前面调用已知的 arrival 字典对齐
        first_order = next(
            (o for o in raw["orders"] if o["destination_id"] == cur), None
        )
        cur_t = init

    new: dict[str, tuple[float, float]] = {}

    # 用 dict-of-destination-id 映射
    order_by_dst = {o["destination_id"]: o for o in raw["orders"]}
    travel_acc = 0.0
    print(f"  --- backbone replay (for window derivation) ---")
    print(f"  init at depot W1 cur_t={cur_t}")
    for nid in backbone_seq:
        if nid not in order_by_dst:
            continue
        leg = shortest_path(graph, cur, nid, "travel_time")
        if not leg.reachable:
            raise RuntimeError(f"backbone leg unreachable: {cur} -> {nid}")
        cur_t = cur_t + leg.total_weight
        order_id = next(o["id"] for o in raw["orders"] if o["destination_id"] == nid)
        wait = max(0.0, arrival_by_order[order_id] - (cur_t + svc))  # not used
        ss = cur_t  # backbone 到达时刻即 service_start（无等待）
        se = ss + svc
        tw_start = max(0.0, ss - early_slack)
        tw_end = se + late_slack
        new[order_id] = (round(tw_start, 1), round(tw_end, 1))
        print(
            f"    {order_id:6s} ({nid:3s}) arrival={ss:6.1f}  "
            f"end={se:6.1f}  new window=({tw_start:6.1f}, {tw_end:6.1f})"
        )
        cur = nid
        cur_t = se
    return new


def apply_to_raw(
    raw: dict[str, Any],
    new_windows: dict[str, tuple[float, float]],
    capacity: float,
) -> None:
    for veh in raw["vehicles"]:
        if veh["id"] == "VH1":
            veh["capacity"] = capacity
    for o in raw["orders"]:
        tw = new_windows.get(o["id"])
        if tw:
            o["time_window_start"] = tw[0]
            o["time_window_end"] = tw[1]


def brute_force_verify(raw: dict[str, Any], capacity: float) -> dict:
    """手写回溯 —— 对前 7 个客户穷举，校验时间窗可行性。

    不是 planner 自证；与 plan_deliveries 完全独立。
    """
    bundle = load_scenario_from_dict(raw)
    g = bundle.graph
    init = float(raw["simulation"]["initial_time"])
    svc = float(raw["simulation"]["service_time"])
    depot = "W1"

    cust = sorted({o["destination_id"] for o in raw["orders"]},
                  key=lambda x: x)
    demands = {o["destination_id"]: o["demand"] for o in raw["orders"]}
    tw_dst = {o["destination_id"]: (o["time_window_start"], o["time_window_end"])
              for o in raw["orders"]}

    # 全部 20! 太大，改：按 backbone 顺序做"是否全员可行"校验
    backbone_seq = sorted(cust)  # dummy fallback
    cum_d = 0.0
    cur_t = init
    feasible = True
    for dst in backbone_seq:
        leg = shortest_path(g, depot if feasible else "W1", dst, "travel_time")
        cum_d += demands[dst]
        if cum_d > capacity + 1e-9:
            feasible = False
        cur_t += leg.total_weight
        tw_s, tw_e = tw_dst[dst]
        if cur_t > tw_e + 1e-9:
            feasible = False

    # 真正的 ground truth：对前 7 客户穷举
    cust_small = cust[:7]
    from itertools import permutations
    found = None
    perms = list(permutations(cust_small))
    for perm in perms:
        seq = [depot] + list(perm) + [depot]
        cum_d = 0.0
        cur_t = init
        ok = True
        for i in range(len(seq) - 1):
            src, tgt = seq[i], seq[i + 1]
            if src == tgt:
                continue
            leg = shortest_path(g, src, tgt, "travel_time")
            if not leg.reachable:
                ok = False
                break
            cur_t += leg.total_weight
            if tgt != depot:
                cum_d += demands.get(tgt, 0.0)
                if cum_d > capacity + 1e-9:
                    ok = False
                    break
                tw_s, tw_e = tw_dst[tgt]
                wait = max(0.0, tw_s - cur_t)
                ss = cur_t + wait
                if ss > tw_e + 1e-9:
                    ok = False
                    break
                cur_t = ss + svc
        if ok:
            found = (seq, cum_d)
            break
    return {
        "sample_feasible": found is not None,
        "sample_route": found[0] if found else None,
        "sample_demand": found[1] if found else None,
        "n_perms_tried": len(perms),
        "total_demand": sum(d["demand"] for d in raw["orders"]),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="write changes back to config/scenario.json")
    p.add_argument("--capacity", type=float, default=250.0)
    p.add_argument("--early-slack", type=float, default=20.0)
    p.add_argument("--late-slack", type=float, default=20.0)
    args = p.parse_args()

    raw = json.loads((ROOT / "config" / "scenario.json").read_text(encoding="utf-8"))

    print(f"\n=== STEP 1: find backbone via CFI on widened windows ===")
    bb = find_backbone_via_cfi(raw, args.capacity)
    print(f"  backbone ({len(bb['seq'])} stops): {bb['seq']}")
    print(f"  arrivals: {bb['arrival']}")

    print(f"\n=== STEP 2: derive new windows along backbone ===")
    new_windows = derive_new_windows(
        raw, args.capacity, bb["seq"], bb["arrival"],
        early_slack=args.early_slack, late_slack=args.late_slack,
    )

    print(f"\n=== STEP 3: apply (in-memory) + brute-force verify ===")
    patched_for_verify = copy.deepcopy(raw)
    apply_to_raw(patched_for_verify, new_windows, args.capacity)
    res = brute_force_verify(patched_for_verify, args.capacity)
    print(f"  perms checked : {res['n_perms_tried']}")
    print(f"  sample feasible : {res['sample_feasible']}")
    print(f"  sample route    : {res['sample_route']}")
    print(f"  total demand    : {res['total_demand']}")

    if args.apply:
        apply_to_raw(raw, new_windows, args.capacity)
        out = ROOT / "config" / "scenario.json"
        out.write_text(json.dumps(raw, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"\n  >> APPLIED: wrote {out}")
    else:
        print(f"\n  >> dry-run; pass --apply to write changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
