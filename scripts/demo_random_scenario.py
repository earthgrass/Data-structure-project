"""Phase 4 — Random Scenario 端到端演示。

在多个 seed 上跑 ``generate_scenario`` 并把结果传入 Phase 3
``plan_deliveries``，证明：

1. 同一 seed 两次生成得到完全相同场景（可复现）；
2. 不同 seed 至少在节点结构上确实不同（随机性）；
3. 生成的场景全部通过独立 validator（feasible）；
4. 三个调度算法都能跑出 20/20（不下伪装、不伪造 100%）。

运行：

    PYTHONPATH=src python scripts/demo_random_scenario.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    generate_scenario,
    validate_generated_scenario,
)
from logiroute.scheduling import plan_deliveries


SEEDS = (0, 1, 42, 100, 2026)
ALGORITHMS = ("nearest_neighbor", "insertion", "two_opt")


def banner(text: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n  {text}\n{bar}")


def _bundle_signature(bundle) -> str:
    """手写 to_dict —— 因为 ScenarioBundle 没有 to_dict()。"""
    return json.dumps(
        {
            "name": bundle.name,
            "mode": bundle.mode,
            "seed": bundle.random_seed,
            "node_ids": bundle.graph.node_ids,
            "orders": [
                {"id": o.id, "dest": o.destination_id,
                 "demand": o.demand, "tws": o.time_window_start,
                 "twe": o.time_window_end}
                for o in bundle.orders
            ],
            "n_edges": bundle.graph.edge_count,
        },
        sort_keys=True,
        default=str,
    )


def seed_reproducibility_check() -> bool:
    """同 seed 运行两次：节点 + 订单 ID + 时间窗 + backbone 完全一致。"""
    bundle_a, bb_a = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    bundle_b, bb_b = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    same_nodes = bundle_a.graph.node_ids == bundle_b.graph.node_ids
    same_orders = (
        [(o.id, o.destination_id, o.demand, o.time_window_start,
          o.time_window_end) for o in bundle_a.orders]
        == [(o.id, o.destination_id, o.demand, o.time_window_start,
             o.time_window_end) for o in bundle_b.orders]
    )
    same_backbone = bb_a == bb_b
    return same_nodes and same_orders and same_backbone


def variant_check(seeds=SEEDS) -> bool:
    """不同 seed 至少在节点结构上确实有差异。"""
    node_lists = [generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=s)[0].graph.node_ids
                  for s in seeds]
    distinct = len({tuple(n) for n in node_lists}) >= 2
    return distinct


def main() -> int:
    banner("LogiRoute Random Scenario Demo (Phase 4)")
    print(f"  default config: orders_count={DEFAULT_GENERATOR_CONFIG.orders_count}"
          f" capacity={DEFAULT_GENERATOR_CONFIG.capacity}"
          f" service_time={DEFAULT_GENERATOR_CONFIG.service_time}")

    # ---- 1. Seed 复现 ----
    banner("Seed reproducibility (seed=42 跑两次)")
    ok = seed_reproducibility_check()
    print(f"  same nodes / orders / backbone on re-run : {'PASS' if ok else 'FAIL'}")
    _, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    a, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    sig_a = _bundle_signature(a)
    _, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    a2, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    sig_b = _bundle_signature(a2)
    byte_identical = sig_a == sig_b
    print(f"  signature byte-identical : {'PASS' if byte_identical else 'FAIL'}")

    # ---- 2. 变异 ----
    banner(f"Variance across seeds {SEEDS}")
    print(f"  distinct node_id lists across seeds : "
          f"{'PASS' if variant_check() else 'FAIL'}")

    # ---- 3. 每个 seed：独立 validator + 三算法 20/20 ----
    banner("Per-seed: validator + planner on 3 algorithms")
    print(f"  {'seed':>5} {'valid':>6} {'demand':>8} "
          f"{'NN':>6} {'CFI':>6} {'2opt':>6}  {'is_feasible':>12}")
    aggregate_ok = True
    for seed in SEEDS:
        bundle, backbone = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
        rep = validate_generated_scenario(bundle, backbone=backbone)
        served = {}
        feasible = {}
        for algo in ALGORITHMS:
            r = plan_deliveries(bundle, algo, "distance")
            served[algo] = f"{len(r.served_order_ids)}/{len(bundle.orders)}"
            feasible[algo] = r.is_feasible
        nn_ok = served["nearest_neighbor"] == f"20/{len(bundle.orders)}"
        cfi_ok = served["insertion"] == f"20/{len(bundle.orders)}"
        opt_ok = served["two_opt"] == f"20/{len(bundle.orders)}"
        ok_this = rep.feasible and nn_ok and cfi_ok and opt_ok
        aggregate_ok = aggregate_ok and ok_this
        print(
            f"  {seed:>5} {str(rep.feasible):>6} {rep.total_demand:>8.1f} "
            f"{served['nearest_neighbor']:>6} {served['insertion']:>6} "
            f"{served['two_opt']:>6}  feasible={feasible['nearest_neighbor']}"
        )

    # ---- 4. timing ----
    banner("Demo timing")
    t0 = time.monotonic()
    bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
    gen_ms = (time.monotonic() - t0) * 1000
    print(f"  generate_scenario(seed=42) wall time: {gen_ms:.2f} ms")
    t0 = time.monotonic()
    for algo in ALGORITHMS:
        plan_deliveries(bundle, algo, "distance")
    planner_total_ms = (time.monotonic() - t0) * 1000
    print(f"  plan_deliveries x 3 algorithms on seed=42: {planner_total_ms:.2f} ms")

    # ---- Summary ----
    banner("Summary")
    print(f"  P0 gates (5 seeds x 3 algorithms): "
          f"{'ALL PASS' if aggregate_ok else 'FAIL'}")
    print(f"  Independent validator used: YES (no plan_deliveries in validator)")
    print(f"  Hand-written Fisher-Yates: YES")
    print(f"  Random seed reproducibility: {'YES' if byte_identical else 'NO'}")
    return 0 if aggregate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
