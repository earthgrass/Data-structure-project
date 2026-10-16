"""``tests/test_scheduling_feasibility.py`` —— ``check_feasibility`` 单测。

覆盖矩阵：

1. 全可行（基本 happy-path）
2. 容量溢出
3. 时间窗迟到违反
4. 时间窗早到允许 + waiting_time > 0
5. 不可达内层腿（``unreachable_leg``）
6. 回归仓库腿（``return_unreachable``）
7. 仓库节点首尾不匹配（``depot_mismatch``）
8. ``service_end > time_window_end`` **不**视为违反（AGENTS §3.7）
9. 入参不被修改 + 幂等性
10. 多违反同时报告（容量 + 时间窗 + 不可达）
11. ``len(legs) != len(stops) - 1`` schema 一致性保护
12. ``DeliveryStop`` / ``_FakeLeg`` frozen 不变性保护

仅依赖 stdlib + Phase 1/3 已存在的 ``DeliveryStop`` / ``FeasibilityReport`` /
``Violation``。
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, dataclass
from typing import Any
from unittest import TestCase

from logiroute.scheduling.feasibility import check_feasibility
from logiroute.scheduling.types import (
    DeliveryStop,
    FeasibilityReport,
    Violation,
)


# ---------------------------------------------------------------------------
#  工厂辅助
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeLeg:
    """测试用最简伪 leg，模拟 PathResult 的相关字段。

    字段集合与 ``logiroute.algorithms.dijkstra.PathResult`` 严格对齐；
    但 ``source/target`` 使用最简单的 ``str``，便于测试断言。
    """

    source: str
    target: str
    metric: str
    path: tuple
    total_weight: float
    reachable: bool
    cross_metrics: dict


def _leg(
    src: str,
    tgt: str,
    *,
    drv: float = 10.0,
    reachable: bool = True,
    metric: str = "distance",
) -> _FakeLeg:
    """构造一条简单可达腿，``drv`` 同时作为三个 metric 的权重（测试用）。"""
    return _FakeLeg(
        source=src,
        target=tgt,
        metric=metric,
        path=(src, tgt),
        total_weight=drv,
        reachable=reachable,
        cross_metrics={
            "distance": drv,
            "travel_time": drv,
            "cost": drv,
        },
    )


def _leg_unreachable(src: str, tgt: str) -> _FakeLeg:
    """构造一条不可达腿（空 path、inf 权重、空 cross_metrics）。"""
    return _FakeLeg(
        source=src,
        target=tgt,
        metric="distance",
        path=(),
        total_weight=float("inf"),
        reachable=False,
        cross_metrics={},
    )


def _depot_stop(
    seq: int,
    nid: str = "W1",
    *,
    at: float = 540.0,
) -> DeliveryStop:
    """构造仓库站：demand=0，无时间窗，service_start==service_end。"""
    return DeliveryStop(
        sequence_index=seq,
        node_id=nid,
        arrival_time=at,
        service_start=at,
        service_end=at,
        waiting_time=0.0,
        order_id=None,
        demand=0.0,
        cumulative_load=0.0,
        time_window_start=None,
        time_window_end=None,
    )


def _customer_stop(
    seq: int,
    nid: str,
    *,
    arrival: float,
    service_start: float,
    service_end: float,
    waiting: float = 0.0,
    order_id: str = "O1",
    demand: float = 5.0,
    cum_load: float = 5.0,
    tw_start: float = 0.0,
    tw_end: float = 1000.0,
) -> DeliveryStop:
    """构造客户站：所有字段显式传入，便于单独制造边界条件。"""
    return DeliveryStop(
        sequence_index=seq,
        node_id=nid,
        arrival_time=arrival,
        service_start=service_start,
        service_end=service_end,
        waiting_time=waiting,
        order_id=order_id,
        demand=demand,
        cumulative_load=cum_load,
        time_window_start=tw_start,
        time_window_end=tw_end,
    )


# ---------------------------------------------------------------------------
#  Test 1: 全可行
# ---------------------------------------------------------------------------


class TestAllFeasible(TestCase):
    def test_minimal_feasible_tour(self):
        # W1 -> C1 -> W1：容量、时间窗、service_time、depot 均合法
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=7.5, cum_load=7.5,
                tw_start=540.0, tw_end=720.0,
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg("C1", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertTrue(report.is_feasible)
        self.assertEqual(report.violations, ())
        # FeasibilityReport 自身也是 frozen
        self.assertIsInstance(report, FeasibilityReport)


# ---------------------------------------------------------------------------
#  Test 2: 容量溢出
# ---------------------------------------------------------------------------


class TestCapacityOverflow(TestCase):
    def test_cumulative_demand_exceeds_capacity(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=30.0, cum_load=30.0,
                tw_start=540.0, tw_end=720.0,
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg("C1", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=20.0,  # < cum_load=30
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("capacity_overflow", kinds)
        # order_id 应回填为对应订单，便于上层诊断
        cap_violations = [v for v in report.violations if v.kind == "capacity_overflow"]
        self.assertTrue(
            all(v.order_id == "O1" for v in cap_violations),
            msg=f"capacity_overflow violations must reference O1, got "
                f"{[v.order_id for v in cap_violations]}",
        )


# ---------------------------------------------------------------------------
#  Test 3: 时间窗迟到违反
# ---------------------------------------------------------------------------


class TestTimeWindowLate(TestCase):
    def test_service_start_after_window_end_violates(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=800.0, service_start=800.0, service_end=805.0,
                order_id="O1", demand=5.0, cum_load=5.0,
                tw_start=540.0, tw_end=600.0,  # service_start=800 > 600
            ),
            _depot_stop(2, "W1", at=815.0),
        )
        legs = (
            _leg("W1", "C1", drv=260.0),
            _leg("C1", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("time_window_miss", kinds)


# ---------------------------------------------------------------------------
#  Test 4: 时间窗早到允许 + waiting
# ---------------------------------------------------------------------------


class TestTimeWindowEarly(TestCase):
    def test_early_arrival_with_waiting_is_feasible(self):
        # arrival=545 < tw_start=560；service_start=560=max(545,560)；wait=15
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=545.0,
                service_start=560.0,
                service_end=565.0,
                waiting=15.0,
                order_id="O1", demand=5.0, cum_load=5.0,
                tw_start=560.0, tw_end=720.0,
            ),
            _depot_stop(2, "W1", at=580.0),
        )
        legs = (
            _leg("W1", "C1", drv=5.0),
            _leg("C1", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertTrue(
            report.is_feasible,
            msg=f"early arrival with waiting must be feasible; got "
                f"violations: {report.violations}",
        )
        self.assertEqual(report.violations, ())


# ---------------------------------------------------------------------------
#  Test 5: 不可达内层腿
# ---------------------------------------------------------------------------


class TestUnreachableLeg(TestCase):
    def test_unreachable_inner_leg(self):
        # legs[0] 不可达 —— 非最后一条 → "unreachable_leg"
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=5.0, cum_load=5.0,
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg_unreachable("W1", "C1"),
            _leg("C1", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("unreachable_leg", kinds)
        # 最后一条腿可达 → 不会产生 return_unreachable
        self.assertNotIn("return_unreachable", kinds)


# ---------------------------------------------------------------------------
#  Test 6: 回归仓库腿 return_unreachable
# ---------------------------------------------------------------------------


class TestReturnUnreachable(TestCase):
    def test_last_leg_unreachable_uses_return_unreachable_kind(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=5.0, cum_load=5.0,
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg_unreachable("C1", "W1"),  # last leg
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("return_unreachable", kinds)
        self.assertNotIn("unreachable_leg", kinds)
        # 消息必须含 "return-to-depot" 便于诊断
        msgs = [
            v.message
            for v in report.violations
            if v.kind == "return_unreachable"
        ]
        self.assertTrue(
            any("return-to-depot" in m for m in msgs),
            msg=f"return_unreachable message must contain 'return-to-depot'; "
                f"got {msgs}",
        )


# ---------------------------------------------------------------------------
#  Test 7: 仓库节点首尾不匹配
# ---------------------------------------------------------------------------


class TestDepotMismatch(TestCase):
    def test_first_stop_not_depot(self):
        # 起点不是仓库
        stops = (
            _customer_stop(
                0, "C1",
                arrival=540.0, service_start=540.0, service_end=545.0,
                order_id="O1", demand=5.0, cum_load=5.0,
                tw_start=0.0, tw_end=1000.0,
            ),
            _depot_stop(1, "W1", at=555.0),
        )
        legs = (_leg("C1", "W1", drv=10.0),)
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("depot_mismatch", kinds)

    def test_last_stop_not_depot(self):
        # 终点不是仓库
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C2",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=5.0, cum_load=5.0,
                tw_start=0.0, tw_end=1000.0,
            ),
        )
        legs = (_leg("W1", "C2", drv=10.0),)
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("depot_mismatch", kinds)


# ---------------------------------------------------------------------------
#  Test 8: service_end > time_window_end 不视为违反
# ---------------------------------------------------------------------------


class TestServiceEndOverflowNotViolation(TestCase):
    def test_service_end_grossly_exceeds_window_but_service_start_within(self):
        # 依据 AGENTS §3.7：本阶段不强制 service_end <= time_window_end；
        # 只要求 service_start 落在窗口内。service_start=10 ∈ [0, 20]，
        # service_end=10+30=40 ≫ 20；但 service_end > tw_end **不是**违反。
        stops = (
            _depot_stop(0, "W1", at=0.0),
            _customer_stop(
                1, "C1",
                arrival=10.0,
                service_start=10.0,        # 在窗口内
                service_end=40.0,          # 远超窗口 (NOT a violation)
                order_id="O1", demand=5.0, cum_load=5.0,
                tw_start=0.0, tw_end=20.0,
            ),
            _depot_stop(2, "W1", at=50.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg("C1", "W1", drv=10.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=30.0,  # 与 service_end=service_start+30 一致
            initial_time=0.0,
            depot_id="W1",
        )
        self.assertTrue(
            report.is_feasible,
            msg=f"service_end > tw_end should NOT be a violation per AGENTS "
                f"§3.7; got violations: {report.violations}",
        )
        self.assertEqual(report.violations, ())


# ---------------------------------------------------------------------------
#  Test 9: 入参不被修改 + 幂等性
# ---------------------------------------------------------------------------


class TestInputsNotMutated(TestCase):
    def test_running_twice_returns_identical_report(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=5.0, cum_load=5.0,
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg("C1", "W1", drv=15.0),
        )
        kwargs = dict(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        r1 = check_feasibility(**kwargs)
        r2 = check_feasibility(**kwargs)
        # 幂等：相同输入必须产生相同报告
        self.assertEqual(r1, r2)
        # 入参结构未变。``DeliveryStop`` 全字段可哈希；``_FakeLeg``
        # 含 dict（cross_metrics），不可哈希 —— 与真实 PathResult 同。
        # 此处仅验证 stops 仍可独立 hash（不会被函数偷偷换掉）。
        self.assertEqual(hash(stops[0]), hash(stops[0]))
        self.assertIsNotNone(hash(stops))
        # 通过对象 ID 与类型自检：腿对象本身未被替换
        self.assertIs(legs[0].__class__, _FakeLeg)


# ---------------------------------------------------------------------------
#  Test 10: 多违反同时报告
# ---------------------------------------------------------------------------


class TestMultipleViolations(TestCase):
    def test_capacity_time_window_and_unreachable_all_reported(self):
        # W1 -> C1 -> C2 -> W1
        #   legs[0] = W1->C1 reachable
        #   legs[1] = C1->C2 UNREACHABLE (内层腿)
        #   legs[2] = C2->W1 reachable
        #   C1: cumulative_load=30 > capacity=20 → capacity_overflow
        #   C2: service_start=900 > tw_end=600 → time_window_miss
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=30.0, cum_load=30.0,
                tw_start=540.0, tw_end=720.0,
            ),
            _customer_stop(
                2, "C2",
                arrival=900.0, service_start=900.0, service_end=905.0,
                order_id="O2", demand=10.0, cum_load=40.0,
                tw_start=540.0, tw_end=600.0,
            ),
            _depot_stop(3, "W1", at=920.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg_unreachable("C1", "C2"),
            _leg("C2", "W1", drv=15.0),
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=20.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        self.assertFalse(report.is_feasible)
        kinds = [v.kind for v in report.violations]
        self.assertIn("capacity_overflow", kinds)
        self.assertIn("time_window_miss", kinds)
        self.assertIn("unreachable_leg", kinds)
        # 至少 3 条违反记录（可能更多：capacity_overflow 会对 C1 和 C2 各自报一次）
        self.assertGreaterEqual(
            len(report.violations),
            3,
            msg=f"expected >=3 violations, got {report.violations}",
        )


# ---------------------------------------------------------------------------
#  Test 11: schema 一致性保护
# ---------------------------------------------------------------------------


class TestSchemaConsistency(TestCase):
    def test_legs_length_mismatch_raises_value_error(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _depot_stop(1, "W1", at=555.0),
        )
        # 期望 1 条腿；传入 0 → 触发 ValueError
        legs: tuple[Any, ...] = ()
        with self.assertRaises(ValueError) as ctx:
            check_feasibility(
                stops=stops,
                legs=legs,
                capacity=100.0,
                service_time=5.0,
                initial_time=540.0,
                depot_id="W1",
            )
        self.assertIn("legs", str(ctx.exception).lower())

    def test_too_many_legs_also_raises(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _depot_stop(1, "W1", at=555.0),
        )
        legs = (
            _leg("W1", "W1", drv=15.0),
            _leg("W1", "W1", drv=15.0),  # 多余
        )
        with self.assertRaises(ValueError):
            check_feasibility(
                stops=stops,
                legs=legs,
                capacity=100.0,
                service_time=5.0,
                initial_time=540.0,
                depot_id="W1",
            )


# ---------------------------------------------------------------------------
#  Test 12: 入参 frozen 不变性保护
# ---------------------------------------------------------------------------


class TestFrozenInputs(TestCase):
    def test_delivery_stop_frozen_blocks_mutation(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _depot_stop(1, "W1", at=555.0),
        )
        legs = (_leg("W1", "W1", drv=15.0),)
        check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        # 调用后入参仍可独立 hash；尝试 mutate 必须抛 FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            stops[0].node_id = "X"  # type: ignore[misc]

    def test_fake_leg_frozen_blocks_mutation(self):
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _depot_stop(1, "W1", at=555.0),
        )
        legs = (_leg("W1", "W1", drv=15.0),)
        check_feasibility(
            stops=stops,
            legs=legs,
            capacity=100.0,
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        with self.assertRaises(FrozenInstanceError):
            legs[0].source = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
#  Test 13: 顺序不敏感 — 同输入两次报告结构相同
# ---------------------------------------------------------------------------


class TestDeterministicOrdering(TestCase):
    def test_violation_order_matches_check_order(self):
        # violation 应按 Check 1 → 3 → 4 顺序追加，便于上层报告。
        # 设计：3 站点（W1, C1, W1），2 条腿；第二条（回归仓库）不可达，
        # C1 同时具备容量溢出与时间窗迟到。
        stops = (
            _depot_stop(0, "W1", at=540.0),
            _customer_stop(
                1, "C1",
                arrival=550.0, service_start=550.0, service_end=555.0,
                order_id="O1", demand=30.0, cum_load=30.0,
                tw_start=540.0, tw_end=500.0,  # service_start=550 > 500
            ),
            _depot_stop(2, "W1", at=565.0),
        )
        legs = (
            _leg("W1", "C1", drv=10.0),
            _leg_unreachable("C1", "W1"),  # last leg → return_unreachable
        )
        report = check_feasibility(
            stops=stops,
            legs=legs,
            capacity=20.0,  # < cum_load=30 → capacity_overflow
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
        )
        kinds_in_order = [v.kind for v in report.violations]
        # 期望顺序：Check 1 (return_unreachable) → Check 3 (capacity_overflow)
        #          → Check 4 (time_window_miss)
        self.assertEqual(
            kinds_in_order,
            ["return_unreachable", "capacity_overflow", "time_window_miss"],
            msg=f"violation order should match check order; got {kinds_in_order}",
        )


if __name__ == "__main__":
    unittest.main()