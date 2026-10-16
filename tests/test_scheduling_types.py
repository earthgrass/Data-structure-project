"""``tests/test_scheduling_types.py`` —— Phase 3 数据类型 + graph_identity 单测。

仅依赖 stdlib 与 Phase 1 已存在的 ``LogisticsGraph`` / ``Edge`` / ``Node``。
"""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import Any
from unittest import TestCase

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, TrafficStatus
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.graph_identity import graph_identity
from logiroute.scheduling.types import (
    DeliveryStop,
    FeasibilityReport,
    PlanningContext,
    PlanningError,
    PlanningStats,
    RoutePlan,
    ScheduleResult,
    VIOLATION_KINDS,
    Violation,
)


# ---------------------------------------------------------------------------
#  工厂辅助
# ---------------------------------------------------------------------------


def _node(nid: str, t: NodeType = NodeType.CUSTOMER) -> Node:
    return Node(id=nid, name=nid, node_type=t, x=0.0, y=0.0)


def _edge(src: str, tgt: str, d: float = 1.0, t: float = 1.0, c: float = 1.0) -> Edge:
    return Edge(
        source_id=src,
        target_id=tgt,
        distance=d,
        travel_time=t,
        cost=c,
    )


def _mini_graph() -> LogisticsGraph:
    """4 节点 + 5 有向边，可连通的最小图。"""
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
    ):
        g.add_node(n)
    for e in (
        _edge("W1", "C1", 2.0, 4.0, 6.0),
        _edge("C1", "C2", 2.0, 4.0, 6.0),
        _edge("C2", "W1", 2.0, 4.0, 6.0),
        _edge("W1", "W2", 5.0, 8.0, 12.0),
        _edge("W2", "C1", 3.0, 5.0, 9.0),
    ):
        g.add_edge(e)
    return g


@dataclass(frozen=True)
class _FakeLeg:
    """测试用最简伪 leg，模拟 PathResult 的相关字段。"""

    source: str
    target: str
    metric: str
    path: tuple
    total_weight: float
    reachable: bool
    cross_metrics: dict


def _make_legs(stop_seq, metric="distance"):
    legs = []
    for s, t in zip(stop_seq[:-1], stop_seq[1:]):
        legs.append(
            _FakeLeg(
                source=s,
                target=t,
                metric=metric,
                path=(s, t),
                total_weight=1.0,
                reachable=True,
                cross_metrics={"distance": 1.0, "travel_time": 1.0, "cost": 1.0},
            )
        )
    return tuple(legs)


def _make_stops(stop_seq, initial_time=540.0):
    stops = []
    for i, nid in enumerate(stop_seq):
        stops.append(
            DeliveryStop(
                sequence_index=i,
                node_id=nid,
                arrival_time=initial_time,
                service_start=initial_time,
                service_end=initial_time,
                waiting_time=0.0,
                order_id=None,
                demand=0.0,
            )
        )
    return tuple(stops)


def _make_plan(
    *, algorithm="nearest_neighbor", objective="distance", vehicle_id="VH1",
    depot_id="W1", stop_seq=("W1", "C1", "W1"),
) -> RoutePlan:
    legs = _make_legs(stop_seq, metric=objective)
    stops = _make_stops(stop_seq)
    total_distance = sum(l.total_weight for l in legs) if objective == "distance" else 0.0
    total_cost = sum(l.total_weight for l in legs) if objective == "cost" else 0.0
    total_travel_time = sum(l.cross_metrics["travel_time"] for l in legs)
    return RoutePlan(
        algorithm=algorithm,
        objective=objective,
        vehicle_id=vehicle_id,
        depot_id=depot_id,
        stop_sequence=stop_seq,
        road_node_sequence=tuple(sum((list(l.path) for l in legs), [])),
        legs=legs,
        stops=stops,
        total_distance=total_distance if objective == "distance" else 0.0,
        total_travel_time=total_travel_time,
        total_cost=total_cost if objective == "cost" else 0.0,
        main_objective_total=total_distance + total_cost,
        departure_time=540.0,
        return_time=545.0,
        capacity=100.0,
        served_order_ids=(),
        is_feasible=True,
    )


# ---------------------------------------------------------------------------
#  DeliveryStop
# ---------------------------------------------------------------------------


class TestDeliveryStop(TestCase):
    def test_frozen_rejects_mutation(self):
        s = DeliveryStop(
            sequence_index=0,
            node_id="W1",
            arrival_time=0.0,
            service_start=0.0,
            service_end=0.0,
            waiting_time=0.0,
        )
        with self.assertRaises(FrozenInstanceError):
            s.node_id = "X"  # type: ignore[misc]

    def test_depot_stop_requires_zero_demand_and_no_time_window(self):
        with self.assertRaises(ValueError):
            DeliveryStop(
                sequence_index=0,
                node_id="W1",
                arrival_time=0.0,
                service_start=0.0,
                service_end=0.0,
                waiting_time=0.0,
                demand=5.0,
            )

        with self.assertRaises(ValueError):
            DeliveryStop(
                sequence_index=0,
                node_id="W1",
                arrival_time=0.0,
                service_start=0.0,
                service_end=0.0,
                waiting_time=0.0,
                time_window_start=540.0,
            )

    def test_negative_sequence_index_rejected(self):
        with self.assertRaises(ValueError):
            DeliveryStop(
                sequence_index=-1,
                node_id="W1",
                arrival_time=0.0,
                service_start=0.0,
                service_end=0.0,
                waiting_time=0.0,
            )

    def test_negative_waiting_time_rejected(self):
        with self.assertRaises(ValueError):
            DeliveryStop(
                sequence_index=0,
                node_id="W1",
                arrival_time=0.0,
                service_start=0.0,
                service_end=0.0,
                waiting_time=-1.0,
            )

    def test_to_dict_returns_all_fields(self):
        s = DeliveryStop(
            sequence_index=2,
            node_id="C1",
            arrival_time=600.0,
            service_start=600.0,
            service_end=605.0,
            waiting_time=0.0,
            order_id="O001",
            demand=7.5,
            cumulative_load=7.5,
            time_window_start=560.0,
            time_window_end=680.0,
        )
        d = s.to_dict()
        self.assertEqual(d["node_id"], "C1")
        self.assertEqual(d["order_id"], "O001")
        self.assertEqual(d["time_window_end"], 680.0)


# ---------------------------------------------------------------------------
#  Violation / FeasibilityReport
# ---------------------------------------------------------------------------


class TestViolation(TestCase):
    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            Violation(order_id="O1", kind="something_unknown", message="...")

    def test_all_listed_kinds_accepted(self):
        for kind in VIOLATION_KINDS:
            Violation(order_id="O1", kind=kind, message="x")

    def test_empty_message_rejected(self):
        with self.assertRaises(ValueError):
            Violation(order_id="O1", kind="capacity_overflow", message="")

    def test_feasibility_report_requires_violations_when_infeasible(self):
        with self.assertRaises(ValueError):
            FeasibilityReport(is_feasible=False, violations=())

    def test_feasibility_report_is_feasible_true_requires_no_violations(self):
        with self.assertRaises(ValueError):
            FeasibilityReport(
                is_feasible=True,
                violations=(Violation(order_id="O1", kind="capacity_overflow", message="x"),),
            )


# ---------------------------------------------------------------------------
#  RoutePlan
# ---------------------------------------------------------------------------


class TestRoutePlan(TestCase):
    def test_legs_length_must_equal_stop_sequence_minus_one(self):
        # Direct constructor with mismatched lengths must raise.
        with self.assertRaises(ValueError):
            RoutePlan(
                algorithm="nearest_neighbor",
                objective="distance",
                vehicle_id="VH1",
                depot_id="W1",
                stop_sequence=("W1", "C1", "W1"),
                road_node_sequence=("W1", "C1", "W1"),
                legs=_make_legs(("W1", "C1")),  # too few
                stops=_make_stops(("W1", "C1", "W1")),
                total_distance=0.0,
                total_travel_time=0.0,
                total_cost=0.0,
                main_objective_total=0.0,
                departure_time=0.0,
                return_time=0.0,
                capacity=0.0,
                served_order_ids=(),
                is_feasible=True,
            )

    def test_depot_must_be_at_both_ends_of_stop_sequence(self):
        # Wrong start
        with self.assertRaises(ValueError):
            RoutePlan(
                algorithm="nearest_neighbor",
                objective="distance",
                vehicle_id="VH1",
                depot_id="W1",
                stop_sequence=("C1", "C1", "W1"),  # wrong start
                road_node_sequence=("C1", "W1"),
                legs=_make_legs(("C1", "C1", "W1")),
                stops=_make_stops(("C1", "C1", "W1")),
                total_distance=2.0,
                total_travel_time=2.0,
                total_cost=2.0,
                main_objective_total=2.0,
                departure_time=0.0,
                return_time=0.0,
                capacity=100.0,
                served_order_ids=(),
                is_feasible=True,
            )

        # Wrong end (open tour)
        with self.assertRaises(ValueError):
            RoutePlan(
                algorithm="nearest_neighbor",
                objective="distance",
                vehicle_id="VH1",
                depot_id="W1",
                stop_sequence=("W1", "C1"),
                road_node_sequence=("W1", "C1"),
                legs=_make_legs(("W1", "C1")),
                stops=_make_stops(("W1", "C1")),
                total_distance=1.0,
                total_travel_time=1.0,
                total_cost=1.0,
                main_objective_total=1.0,
                departure_time=0.0,
                return_time=0.0,
                capacity=100.0,
                served_order_ids=(),
                is_feasible=True,
            )

    def test_unreachable_leg_rejected(self):
        bad_leg = _FakeLeg(
            source="W1", target="C1", metric="distance",
            path=(), total_weight=float("inf"), reachable=False,
            cross_metrics={},
        )
        with self.assertRaises(ValueError):
            RoutePlan(
                algorithm="nearest_neighbor",
                objective="distance",
                vehicle_id="VH1",
                depot_id="W1",
                stop_sequence=("W1", "C1", "W1"),
                road_node_sequence=("W1", "C1", "W1"),
                legs=(bad_leg, _make_legs(("C1", "W1"))[0]),
                stops=_make_stops(("W1", "C1", "W1")),
                total_distance=1.0,
                total_travel_time=1.0,
                total_cost=1.0,
                main_objective_total=1.0,
                departure_time=0.0,
                return_time=0.0,
                capacity=100.0,
                served_order_ids=(),
                is_feasible=True,
            )

    def test_main_objective_total_must_match_total_distance_when_objective_distance(self):
        with self.assertRaises(ValueError):
            RoutePlan(
                algorithm="nearest_neighbor",
                objective="distance",
                vehicle_id="VH1",
                depot_id="W1",
                stop_sequence=("W1", "C1", "W1"),
                road_node_sequence=("W1", "C1", "W1"),
                legs=_make_legs(("W1", "C1", "W1")),
                stops=_make_stops(("W1", "C1", "W1")),
                total_distance=1.0,
                total_travel_time=1.0,
                total_cost=1.0,
                main_objective_total=999.0,  # mismatch
                departure_time=0.0,
                return_time=0.0,
                capacity=100.0,
                served_order_ids=(),
                is_feasible=True,
            )

    def test_objective_must_be_distance_or_cost(self):
        with self.assertRaises(ValueError):
            _make_plan(objective="travel_time")  # raises

    def test_frozen_after_construction(self):
        plan = _make_plan()
        with self.assertRaises(FrozenInstanceError):
            plan.depot_id = "X"  # type: ignore[misc]

    def test_to_dict_is_json_serializable(self):
        plan = _make_plan()
        d = plan.to_dict()
        s = json.dumps(d)
        # round-trip via loads
        restored = json.loads(s)
        self.assertEqual(restored["depot_id"], "W1")
        self.assertEqual(restored["stop_sequence"], ["W1", "C1", "W1"])
        self.assertEqual(restored["legs"][0]["source"], "W1")


# ---------------------------------------------------------------------------
#  PlanningStats
# ---------------------------------------------------------------------------


class TestPlanningStats(TestCase):
    def test_negative_counter_rejected(self):
        with self.assertRaises(ValueError):
            PlanningStats(cache_hits=-1)

    def test_runtime_must_be_non_negative(self):
        with self.assertRaises(ValueError):
            PlanningStats(runtime_seconds=-0.1)

    def test_to_dict_returns_all_counters(self):
        s = PlanningStats(
            cache_hits=10,
            cache_misses=5,
            dijkstra_calls=5,
            paths_evaluated=15,
            feasibility_checks=3,
            iterations=2,
            runtime_seconds=0.123,
        )
        d = s.to_dict()
        self.assertEqual(d["cache_hits"], 10)
        self.assertEqual(d["runtime_seconds"], 0.123)


# ---------------------------------------------------------------------------
#  ScheduleResult
# ---------------------------------------------------------------------------


class TestScheduleResult(TestCase):
    def test_fake_100pct_is_suppressed(self):
        # Plan feasible but unserved orders exist → is_feasible must flip to False.
        plan = _make_plan()
        violation = Violation(
            order_id="O1", kind="no_feasible_next_step", message="x"
        )
        result = ScheduleResult(
            scenario_name="scn1",
            algorithm="nearest_neighbor",
            objective="distance",
            depot_id="W1",
            vehicle_id="VH1",
            route_plan=plan,
            served_order_ids=(),
            unserved_orders=(violation,),
            total_distance=plan.total_distance,
            total_travel_time=plan.total_travel_time,
            total_cost=plan.total_cost,
            main_objective_total=plan.main_objective_total,
            planning_stats=PlanningStats(),
            is_feasible=True,  # Tried to fake 100%; constructor must override
        )
        self.assertFalse(result.is_feasible)

    def test_to_dict_is_json_serializable(self):
        plan = _make_plan()
        result = ScheduleResult(
            scenario_name="scn1",
            algorithm="nearest_neighbor",
            objective="distance",
            depot_id="W1",
            vehicle_id="VH1",
            route_plan=plan,
            served_order_ids=("O1",),
            unserved_orders=(),
            total_distance=plan.total_distance,
            total_travel_time=plan.total_travel_time,
            total_cost=plan.total_cost,
            main_objective_total=plan.main_objective_total,
            planning_stats=PlanningStats(),
            is_feasible=True,
        )
        d = result.to_dict()
        s = json.dumps(d)
        restored = json.loads(s)
        self.assertEqual(restored["scenario_name"], "scn1")
        self.assertEqual(restored["is_feasible"], True)


# ---------------------------------------------------------------------------
#  PlanningContext
# ---------------------------------------------------------------------------


class TestPlanningContext(TestCase):
    def _ctx(self, **overrides) -> PlanningContext:
        defaults = dict(
            scenario=object(),
            graph=_mini_graph(),
            path_provider=object(),
            objective="distance",
            service_time=5.0,
            initial_time=540.0,
            depot_id="W1",
            vehicle=object(),
            courier=None,
            capacity=100.0,
        )
        defaults.update(overrides)
        return PlanningContext(**defaults)

    def test_invalid_objective_rejected(self):
        with self.assertRaises(ValueError):
            self._ctx(objective="travel_time")

    def test_negative_service_time_rejected(self):
        with self.assertRaises(ValueError):
            self._ctx(service_time=-1.0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            self._ctx(capacity=-1.0)

    def test_frozen_blocks_mutation(self):
        ctx = self._ctx()
        with self.assertRaises(FrozenInstanceError):
            ctx.depot_id = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
#  PlanningError 子类
# ---------------------------------------------------------------------------


class TestPlanningErrors(TestCase):
    def test_subclass_relationships(self):
        from logiroute.scheduling.types import (
            DepotNotFoundError,
            EmptyOrdersError,
            InfeasibleSeedError,
            InvalidObjectiveError,
            NoAvailableVehicleError,
            UnknownAlgorithmError,
        )

        for cls in (
            NoAvailableVehicleError,
            EmptyOrdersError,
            UnknownAlgorithmError,
            InvalidObjectiveError,
            DepotNotFoundError,
            InfeasibleSeedError,
        ):
            self.assertTrue(issubclass(cls, PlanningError))


# ---------------------------------------------------------------------------
#  graph_identity
# ---------------------------------------------------------------------------


class TestGraphIdentity(TestCase):
    def test_same_graph_returns_equal_tuple_twice(self):
        g = _mini_graph()
        a = graph_identity(g)
        b = graph_identity(g)
        self.assertEqual(a, b)

    def test_graph_mutation_changes_fingerprint(self):
        g = _mini_graph()
        a = graph_identity(g)
        g.add_edge(_edge("C1", "W1", 1.0))
        b = graph_identity(g)
        self.assertNotEqual(a, b)

    def test_edge_fingerprint_contains_all_components(self):
        g = _mini_graph()
        ident = graph_identity(g)
        # Last component is the edge_fingerprint tuple
        edge_fp = ident[3]
        self.assertGreater(len(edge_fp), 0)
        # every tuple has exactly 6 fields
        for tup in edge_fp:
            self.assertEqual(len(tup), 6)
            src, tgt, d, t, c, traffic = tup
            self.assertIsInstance(src, str)
            self.assertIsInstance(tgt, str)
            self.assertIsInstance(d, float)
            self.assertIsInstance(t, float)
            self.assertIsInstance(c, float)
            self.assertIn(
                traffic,
                {s.value for s in TrafficStatus},
            )

    def test_changing_edge_weight_changes_fingerprint(self):
        g = _mini_graph()
        a = graph_identity(g)
        g.remove_edge("W1", "C1")
        g.add_edge(_edge("W1", "C1", 99.0))
        b = graph_identity(g)
        self.assertNotEqual(a, b)

    def test_no_sorted_calls_in_module(self):
        import ast
        import inspect

        from logiroute.scheduling import graph_identity as gi_mod

        src = inspect.getsource(gi_mod)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # ban sorted(...) call
                if isinstance(func, ast.Name) and func.id == "sorted":
                    self.fail(f"sorted() call found at line {node.lineno}")
                # ban list.sort() method call
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "sort"
                    and not isinstance(func.value, ast.Call)
                ):
                    self.fail(
                        f"mutating sort() method call found at line {node.lineno}"
                    )


if __name__ == "__main__":
    unittest.main()
