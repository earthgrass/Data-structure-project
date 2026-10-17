"""seed=42 跨进程可复现性回归测试（Phase 5 验收 P0）。

背景：``graph_sampler`` 曾直接迭代 ``set[tuple[str, str]]`` 构造边。Python 的
字符串哈希在**每个进程**随机化（``PYTHONHASHSEED``），导致同一 seed 在不同
进程中边权采样顺序不同 —— 场景表面规模一致，但边权、订单时间窗和最终路线
全部漂移，违反 ``generate_scenario`` "同 seed + 同 config → 完全相同场景"
的承诺，也破坏课程演示的可复现性。

本测试用两个不同的 ``PYTHONHASHSEED`` 启动独立子进程，比较生成场景与
distance / cost 两次规划的完整指纹。修复前该测试必须失败。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]

_CHILD_SCRIPT = r"""
import json
from logiroute.api.services import ScenarioService
from logiroute.scheduling.planner import plan_deliveries

bundle = ScenarioService().generate_random_scenario(seed=42).bundle
distance = plan_deliveries(bundle, objective="distance")
cost = plan_deliveries(bundle, objective="cost")

payload = {
    "nodes": [n.id for n in bundle.graph.nodes],
    "edges": sorted(
        (e.source_id, e.target_id, e.distance, e.travel_time, e.cost)
        for e in bundle.graph.edges
    ),
    "orders": [
        (o.id, o.destination_id, o.demand,
         o.time_window_start, o.time_window_end)
        for o in bundle.orders
    ],
    "distance_route": list(distance.route_plan.stop_sequence),
    "distance_total": round(distance.total_distance, 9),
    "cost_route": list(cost.route_plan.stop_sequence),
    "cost_total": round(cost.total_cost, 9),
}
print(json.dumps(payload, sort_keys=True))
"""


def _run_with_hash_seed(hash_seed: str) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "child process failed with PYTHONHASHSEED="
            f"{hash_seed}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


class TestSeed42CrossProcessReproducibility(unittest.TestCase):
    """同一 seed 必须与进程哈希种子无关。"""

    def test_seed42_is_identical_across_hash_seeds(self) -> None:
        first = _run_with_hash_seed("1")
        second = _run_with_hash_seed("2")

        self.assertEqual(
            first["nodes"], second["nodes"],
            "节点 ID 序列在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["edges"], second["edges"],
            "边集合 / 边权在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["orders"], second["orders"],
            "订单目的地 / 需求 / 时间窗在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["distance_route"], second["distance_route"],
            "distance 路线在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["distance_total"], second["distance_total"],
            "distance 总距离在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["cost_route"], second["cost_route"],
            "cost 路线在不同 PYTHONHASHSEED 下不一致",
        )
        self.assertEqual(
            first["cost_total"], second["cost_total"],
            "cost 总成本在不同 PYTHONHASHSEED 下不一致",
        )


if __name__ == "__main__":
    unittest.main()
