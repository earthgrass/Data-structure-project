"""Phase 5 —— FastAPI 后端单元测试。

测试使用 :class:`fastapi.testclient.TestClient` 启动 in-process 应用，
避免依赖外部 uvicorn 进程。所有断言直接基于 HTTP 响应。

覆盖：

* ``GET /api/health`` —— 健康检查；
* ``POST /api/scenario/random`` —— 随机场景生成（默认参数 + 自定义 seed）；
* ``GET /api/scenario/current`` —— 当前场景读取；存在 / 不存在两种情形；
* ``POST /api/plan`` —— 三种算法 × 两种 objective；
* ``POST /api/compare`` —— 三算法对照；
* 参数校验 —— 非法 algorithm / objective 返回 400；
* JSON 可序列化 —— 所有响应体均能 ``json.dumps``。
"""
from __future__ import annotations

import json
import unittest
from unittest import TestCase

from fastapi.testclient import TestClient

from logiroute.api import create_app


class TestPhase5API(TestCase):
    """Phase 5 Dashboard 后端集成测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        # 用 ``with`` 触发 lifespan（FastAPI ≥ 0.99 必需）
        cls._client_ctx = TestClient(cls.app)
        cls._client_ctx.__enter__()
        cls.client = cls._client_ctx

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_ctx.__exit__(None, None, None)

    def setUp(self) -> None:
        # 每个用例独立 —— 重置场景状态（重启 lifespan 不便，
        # 改为在用例内重新 random 一个新场景保证隔离）。
        pass

    # ------------------------------------------------------------------ #
    # /api/health
    # ------------------------------------------------------------------ #

    def test_health(self) -> None:
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)
        self.assertIn("test_count", body)
        # 必为正整数
        self.assertIsInstance(body["test_count"], int)
        self.assertGreater(body["test_count"], 0)

    # ------------------------------------------------------------------ #
    # 场景生成 / 获取
    # ------------------------------------------------------------------ #

    def test_scenario_random_default(self) -> None:
        resp = self.client.post(
            "/api/scenario/random", json={"seed": 42}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # 关键字段
        self.assertIn("scenario", body)
        self.assertIn("validation", body)
        self.assertIn("config_name", body)
        # 单车辆硬约束
        vehicles = body["scenario"]["vehicles"]
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0]["id"], "VH1")
        # 订单可达
        orders = body["scenario"]["orders"]
        self.assertGreaterEqual(len(orders), 1)
        # 独立 validator 通过
        self.assertTrue(body["validation"]["feasible"])
        # backbone 闭合
        bb = body["scenario"]["backbone"]
        self.assertGreaterEqual(len(bb), 2)
        self.assertEqual(bb[0], bb[-1])

    def test_scenario_random_with_custom_seed(self) -> None:
        a = self.client.post("/api/scenario/random", json={"seed": 7})
        b = self.client.post("/api/scenario/random", json={"seed": 7})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        # 同 seed → 节点 ID 序列必须完全相同
        a_ids = [n["id"] for n in a.json()["scenario"]["graph"]["nodes"]]
        b_ids = [n["id"] for n in b.json()["scenario"]["graph"]["nodes"]]
        self.assertEqual(a_ids, b_ids)

    def test_scenario_random_different_seeds_diverge(self) -> None:
        a = self.client.post("/api/scenario/random", json={"seed": 1})
        b = self.client.post("/api/scenario/random", json={"seed": 9999})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        a_ids = [n["id"] for n in a.json()["scenario"]["graph"]["nodes"]]
        b_ids = [n["id"] for n in b.json()["scenario"]["graph"]["nodes"]]
        self.assertNotEqual(a_ids, b_ids)

    def test_scenario_random_custom_orders_count(self) -> None:
        resp = self.client.post(
            "/api/scenario/random",
            json={"seed": 42, "orders_count": 8, "capacity": 200.0},
        )
        self.assertEqual(resp.status_code, 200)
        orders = resp.json()["scenario"]["orders"]
        self.assertEqual(len(orders), 8)

    def test_scenario_random_invalid_orders_count_rejected(self) -> None:
        resp = self.client.post(
            "/api/scenario/random",
            json={"seed": 42, "orders_count": 0},
        )
        self.assertEqual(resp.status_code, 422)  # Pydantic ge=1 validation

    def test_scenario_current_after_random(self) -> None:
        self.client.post("/api/scenario/random", json={"seed": 42})
        resp = self.client.get("/api/scenario/current")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("scenario", body)
        self.assertIn("validation", body)

    def test_scenario_current_returns_404_on_fresh_app(self) -> None:
        # 使用一个全新的应用实例来测试 "无当前场景" 分支。
        fresh = create_app()
        with TestClient(fresh) as c:
            resp = c.get("/api/scenario/current")
        self.assertEqual(resp.status_code, 404)
        body = resp.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["kind"], "not_found")

    # ------------------------------------------------------------------ #
    # /api/plan
    # ------------------------------------------------------------------ #

    def _ensure_scenario(self, seed: int = 42) -> None:
        self.client.post("/api/scenario/random", json={"seed": seed})

    def test_plan_nearest_neighbor(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/plan",
            json={"algorithm": "nearest_neighbor", "objective": "distance"},
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(len(result["served_order_ids"]), 20)
        self.assertEqual(result["unserved_orders"], [])
        self.assertTrue(result["is_feasible"])

    def test_plan_insertion(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/plan",
            json={"algorithm": "insertion", "objective": "cost"},
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(len(result["served_order_ids"]), 20)
        self.assertTrue(result["is_feasible"])

    def test_plan_two_opt(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/plan",
            json={"algorithm": "two_opt", "objective": "distance"},
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(len(result["served_order_ids"]), 20)
        self.assertTrue(result["is_feasible"])

    def test_plan_invalid_algorithm(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/plan",
            json={"algorithm": "bogus_algo", "objective": "distance"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["kind"], "bad_request")

    def test_plan_invalid_objective(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/plan",
            json={"algorithm": "nearest_neighbor", "objective": "travel_time"},
        )
        # AGENTS §3.7: travel_time 不允许作主目标。
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------ #
    # /api/compare
    # ------------------------------------------------------------------ #

    def test_compare_default(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/compare", json={"objective": "distance"}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["objective"], "distance")
        results = body["results"]
        self.assertIn("nearest_neighbor", results)
        self.assertIn("insertion", results)
        self.assertIn("two_opt", results)
        for algo, result in results.items():
            self.assertEqual(
                len(result["served_order_ids"]), 20,
                f"{algo} served {len(result['served_order_ids'])}",
            )
            self.assertTrue(result["is_feasible"], f"{algo} not feasible")

    def test_compare_custom_algorithms(self) -> None:
        self._ensure_scenario()
        resp = self.client.post(
            "/api/compare",
            json={
                "objective": "distance",
                "algorithms": ["nearest_neighbor", "two_opt"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertIn("nearest_neighbor", results)
        self.assertIn("two_opt", results)
        self.assertNotIn("insertion", results)

    # ------------------------------------------------------------------ #
    # JSON 序列化
    # ------------------------------------------------------------------ #

    def test_all_responses_json_serializable(self) -> None:
        """所有响应体都能 ``json.dumps``（FastAPI 内部已编码，但保险起见再断言）。"""
        self._ensure_scenario()
        for path, method, body in [
            ("/api/health", "GET", None),
            ("/api/scenario/current", "GET", None),
            ("/api/plan", "POST", {"algorithm": "two_opt", "objective": "distance"}),
            ("/api/compare", "POST", {"objective": "cost"}),
        ]:
            if method == "GET":
                resp = self.client.get(path)
            else:
                resp = self.client.post(path, json=body)
            self.assertEqual(resp.status_code, 200, f"{method} {path}")
            json.dumps(resp.json())  # 不抛即通过

    # ------------------------------------------------------------------ #
    # 单车辆硬约束
    # ------------------------------------------------------------------ #

    def test_single_vehicle_in_response(self) -> None:
        self._ensure_scenario()
        scenario = self.client.get("/api/scenario/current").json()["scenario"]
        self.assertEqual(len(scenario["vehicles"]), 1)
        self.assertEqual(len(scenario["couriers"]), 1)
        # planner 返回的 vehicle_id 与唯一车辆一致
        plan = self.client.post(
            "/api/plan",
            json={"algorithm": "two_opt", "objective": "distance"},
        ).json()["result"]
        self.assertEqual(plan["vehicle_id"], "VH1")

    # ------------------------------------------------------------------ #
    # 多 seed 端到端
    # ------------------------------------------------------------------ #

    def test_three_seeds_all_serve_all_orders(self) -> None:
        for seed in (0, 42, 2026):
            self.client.post("/api/scenario/random", json={"seed": seed})
            resp = self.client.post(
                "/api/plan",
                json={"algorithm": "two_opt", "objective": "distance"},
            )
            self.assertEqual(resp.status_code, 200)
            result = resp.json()["result"]
            self.assertTrue(
                result["is_feasible"],
                f"seed={seed} not feasible: {result}",
            )
            self.assertEqual(
                len(result["served_order_ids"]),
                len(result["served_order_ids"]) - len(result["unserved_orders"]),
            )


if __name__ == "__main__":
    unittest.main()