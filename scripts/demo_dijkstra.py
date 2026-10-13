"""Dijkstra 教学演示脚本。

执行：

    PYTHONPATH=src python scripts/demo_dijkstra.py

功能：

1. 加载 Phase 1 固定场景（35 节点 / 192 边 / 强连通）。
2. 在小规模玩具图上演示 trace 模式（逐轮打印 dist / prev / 堆动作）。
3. 在固定场景上对 (仓库, 客户) 跑三种 metric，打印路径与权重。
4. 演示"同一对 (source, target) 三种策略通常给出不同路径"。
5. 演示 trace 模式的逐轮 StepRecord 结构化输出。

**禁止**在此脚本中重写 Dijkstra；所有计算都调用
``logiroute.algorithms.dijkstra`` 正式实现。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# 允许从仓库根目录直接运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.algorithms.dijkstra import (  # noqa: E402
    PathResult,
    compare_metrics,
    dijkstra_single_source,
    shortest_path,
)
from logiroute.core.edges import Edge  # noqa: E402
from logiroute.core.enums import NodeType  # noqa: E402
from logiroute.core.nodes import Node  # noqa: E402
from logiroute.graph.logistics_graph import LogisticsGraph  # noqa: E402


def banner(text: str) -> None:
    print()
    print("=" * 78)
    print(f"  {text}")
    print("=" * 78)


def toy_graph() -> LogisticsGraph:
    g = LogisticsGraph()
    for n in ("A", "B", "C", "D"):
        g.add_node(Node(id=n, name=n, node_type=NodeType.CUSTOMER, x=0.0, y=0.0))
    g.add_edge(Edge("A", "B", distance=1, travel_time=2, cost=10))
    g.add_edge(Edge("A", "C", distance=4, travel_time=1, cost=1))
    g.add_edge(Edge("B", "C", distance=2, travel_time=2, cost=2))
    g.add_edge(Edge("B", "D", distance=5, travel_time=10, cost=1))
    g.add_edge(Edge("C", "D", distance=1, travel_time=1, cost=10))
    return g


def demo_trace() -> None:
    banner("演示 1：小图 trace 模式（逐轮打印）")
    g = toy_graph()
    tr = dijkstra_single_source(g, "A", metric="distance", trace=True)
    print(f"源节点 = A, metric = distance")
    print(f"图：4 节点 / 5 边（A→B, A→C, B→C, B→D, C→D）")
    print()
    print(f"{'Round':>5} | {'Pop u':>4} | {'dist[u]':>8} | {'已确定':>10} | {'成功松弛'}")
    print("-" * 78)
    for s in tr.steps:
        relax_str = ", ".join(
            f"{r['source']}→{r['target']} ({r['old_dist']}→{r['new_dist']})"
            for r in s.relaxations
        ) or "—"
        print(
            f"{s.round:>5} | {s.popped_node:>4} | {s.popped_distance:>8.2f} | "
            f"{','.join(s.settled_snapshot):>10} | {relax_str}"
        )
    print()
    print(f"最终 dist = {tr.dist}")
    print(f"最终 prev = {tr.prev}")
    print(f"松弛成功 {tr.relaxed_edges} 次；堆弹出 {tr.heap_pops} 次（含懒删除）")


def demo_three_metrics() -> None:
    banner("演示 2：同一对 (A,D) 三种 metric 的不同最优路径")
    g = toy_graph()
    results = compare_metrics(g, "A", "D")
    print(f"{'metric':<14} | {'path':<24} | {'total':>8} | {'cross distance':>14} | {'cross time':>12} | {'cross cost':>10}")
    print("-" * 100)
    for m, r in results.items():
        path_str = " → ".join(r.path) if r.path else "（不可达）"
        print(
            f"{m:<14} | {path_str:<24} | {r.total_weight:>8.2f} | "
            f"{r.cross_metrics.get('distance', '-'):>14} | "
            f"{r.cross_metrics.get('travel_time', '-'):>12} | "
            f"{r.cross_metrics.get('cost', '-'):>10}"
        )


def demo_fixed_scenario() -> None:
    banner("演示 3：固定场景 (35 节点 / 192 边) 端到端")
    from logiroute.config import load_scenario
    bundle = load_scenario(ROOT / "config" / "scenario.json")
    g = bundle.graph
    # 选一对仓库 + 客户
    warehouses = [n for n in g.get_all_nodes() if n.node_type == NodeType.WAREHOUSE]
    customers = [n for n in g.get_all_nodes() if n.node_type == NodeType.CUSTOMER]
    if not warehouses or not customers:
        print("固定场景中未找到仓库或客户节点")
        return
    src = warehouses[0].id
    tgt = customers[0].id
    print(f"选择 source = {src} (仓库), target = {tgt} (客户)")
    print()
    results = compare_metrics(g, src, tgt)
    print(f"{'metric':<14} | {'path 长度':>8} | {'总权重':>10} | 前 6 步")
    print("-" * 90)
    for m, r in results.items():
        head = " → ".join(r.path[:6])
        if len(r.path) > 6:
            head += " → ..."
        if not r.reachable:
            print(f"{m:<14} | {'—':>8} | {'∞':>10} | （不可达）")
        else:
            print(
                f"{m:<14} | {len(r.path):>8} | {r.total_weight:>10.3f} | {head}"
            )
    print()
    print(f"说明：")
    print(f"  * 每条路径的 'cross' 字段表示同一实际路径在另外两种 metric 下的总权重")
    print(f"  * 这只反映该路径上的累加，不一定等于对应 metric 下的全局最小值")
    print()
    # 展示同对 (source, target) 三种 metric 通常给出不同路径
    if (
        results["distance"].path != results["travel_time"].path
        or results["distance"].path != results["cost"].path
    ):
        print("[OK] 三种 metric 至少在路径选择上产生了差异")
    else:
        print("(本场景此对节点三种策略恰好给出相同路径，属正常情形)")


def demo_compare_pairs() -> None:
    banner("演示 4：展示路径差异（多对仓库→客户）")
    from logiroute.config import load_scenario
    bundle = load_scenario(ROOT / "config" / "scenario.json")
    g = bundle.graph
    warehouses = [n for n in g.get_all_nodes() if n.node_type == NodeType.WAREHOUSE][:1]
    customers = [n for n in g.get_all_nodes() if n.node_type == NodeType.CUSTOMER][:3]
    if not warehouses or len(customers) < 3:
        print("数据不足")
        return
    src = warehouses[0].id
    for tgt in [c.id for c in customers]:
        results = compare_metrics(g, src, tgt)
        d_path = "→".join(results["distance"].path) if results["distance"].reachable else "?"
        t_path = "→".join(results["travel_time"].path) if results["travel_time"].reachable else "?"
        c_path = "→".join(results["cost"].path) if results["cost"].reachable else "?"
        print(f"  {src} → {tgt}:")
        print(f"    distance  : d={results['distance'].total_weight:6.2f}  path={d_path}")
        print(f"    time      : t={results['travel_time'].total_weight:6.2f}  path={t_path}")
        print(f"    cost      : c={results['cost'].total_weight:6.2f}  path={c_path}")
        if d_path != t_path or d_path != c_path:
            print("    ⇧ 至少一种策略选择了不同路径")


def main() -> None:
    demo_trace()
    demo_three_metrics()
    demo_fixed_scenario()
    demo_compare_pairs()
    banner("演示结束")


if __name__ == "__main__":
    main()
