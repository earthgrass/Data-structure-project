"""Phase 3 regression test layer — ``plan_deliveries`` end-to-end invariants.

These tests focus on **invariants that previous phases must continue to honor**:

* Graph immutability — ``plan_deliveries`` and ``PathProvider`` never mutate the
  underlying ``LogisticsGraph`` (Phase 1 hard contract);
* Metric isolation — ``total_travel_time`` is sourced from ``cross_metrics``,
  not from ``leg.total_weight``;
* ``service_time`` — taken from the scenario's ``simulation.service_time``;
* Single-vehicle enforcement (AGENTS §3.6);
* Closed-tour invariant — every algorithm returns a tour starting and ending
  at the chosen depot;
* Stats sanity — counters are non-negative and consistent;
* Cheapness contract — 2-opt never worsens its NN seed;
* Violation-kind whitelist — only known kinds leak into ``unserved_orders``;
* ``to_dict()`` JSON round-trip.

Requires stdlib only; uses ``unittest``. The fixed-scenario tests are guarded
by ``skipUnless`` and rely on ``config/scenario.json`` being present.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from logiroute.config.loader import load_scenario
from logiroute.core.couriers import Courier
from logiroute.core.edges import Edge
from logiroute.core.enums import (
    CourierStatus,
    NodeType,
    OrderPriority,
    OrderStatus,
    VehicleStatus,
)
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling import PathProvider, plan_deliveries
from logiroute.scheduling.types import (
    VIOLATION_KINDS,
    DeliveryStop,
    PlanningStats,
    PlanningContext,
    RoutePlan,
    Violation,
)


SCENARIO_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "scenario.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_minimal_graph() -> LogisticsGraph:
    """Build a small 4-node ring graph with 6 directed edges.

    Used by regression tests that don't need the full fixed scenario.
    """
    g = LogisticsGraph()
    for nid in ("W1", "C1", "T1", "C2"):
        g.add_node(
            Node(id=nid, name=nid, node_type=NodeType.WAREHOUSE, x=0.0, y=0.0)
            if nid == "W1"
            else Node(
                id=nid, name=nid, node_type=NodeType.CUSTOMER, x=0.0, y=0.0
            )
        )
    # W1 -> C1 -> T1 -> C2 -> W1 with parallel forward & backward paths
    edges = [
        Edge(source_id="W1", target_id="C1",
             distance=1.0, travel_time=2.0, cost=0.5),
        Edge(source_id="C1", target_id="T1",
             distance=1.5, travel_time=3.0, cost=0.7),
        Edge(source_id="T1", target_id="C2",
             distance=2.0, travel_time=4.0, cost=1.0),
        Edge(source_id="C2", target_id="W1",
             distance=2.5, travel_time=5.0, cost=1.2),
        Edge(source_id="W1", target_id="T1",
             distance=1.8, travel_time=3.6, cost=0.9),
        Edge(source_id="T1", target_id="W1",
             distance=2.2, travel_time=4.4, cost=1.1),
    ]
    for e in edges:
        g.add_edge(e)
    return g


def _build_minimal_scenario(
    *,
    service_time: float = 5.0,
    initial_time: float = 0.0,
    orders: list[Order] | None = None,
    capacity: float = 100.0,
) -> "ScenarioBundleLike":
    """Build a tiny scenario bundle suitable for unit tests.

    Returns a ``ScenarioBundle`` with a 4-node graph, 1 IDLE vehicle, 1 courier
    and the given orders. Marked as ``ScenarioBundleLike`` to avoid an
    import cycle at module load time — the import happens inside the function
    via ``load_scenario`` callers anyway.
    """
    from logiroute.config.loader import ScenarioBundle

    g = _build_minimal_graph()
    v = Vehicle(
        id="VH1",
        capacity=capacity,
        current_load=0.0,
        current_node_id="W1",
        status=VehicleStatus.IDLE,
    )
    c = Courier(
        id="CO1", name="CO1", vehicle_id="VH1", status=CourierStatus.IDLE
    )
    if orders is None:
        orders = [
            Order(
                id="O1",
                destination_id="C1",
                demand=5.0,
                time_window_start=0.0,
                time_window_end=1000.0,
                priority=OrderPriority.NORMAL,
                status=OrderStatus.PENDING,
            ),
        ]
    return ScenarioBundle(
        name="regression-mini",
        mode="fixed",
        random_seed=42,
        graph=g,
        vehicles=[v],
        couriers=[c],
        orders=list(orders),
        simulation={
            "service_time": service_time,
            "initial_time": initial_time,
        },
        optimization={"default_objective": "distance"},
        metadata={},
    )


def _graph_signature(graph: LogisticsGraph) -> tuple:
    """Return a comparable fingerprint of ``graph`` state.

    Used for immutability checks: snapshots before & after a planning run and
    confirms they are identical (no node / edge / weight mutation).
    """
    nodes = tuple(graph.node_ids)
    edge_pairs = tuple(
        (src, nbr["target"], nbr["travel_time"], nbr["cost"], nbr["distance"])
        for src, neighbors in sorted(graph.get_adjacency_list().items())
        for nbr in neighbors
    )
    return (graph.node_count, graph.edge_count, nodes, edge_pairs)


# ---------------------------------------------------------------------------
#  Unit-only regression tests (no fixed scenario required)
# ---------------------------------------------------------------------------


class TestRegressionWithoutFixedScenario(unittest.TestCase):
    """Regression cases that don't need ``config/scenario.json``.

    These build a tiny graph directly and exercise the planner / PathProvider
    contract on minimal inputs.
    """

    # -- A.3 graph immutability via PathProvider cache ---------------------

    def test_path_provider_cache_does_not_mutate_graph(self) -> None:
        """Repeated PathProvider queries must not mutate the graph."""
        g = _build_minimal_graph()
        before = _graph_signature(g)

        provider = PathProvider(g)
        nodes = ("W1", "C1", "T1", "C2")
        # Hammer all source-target-metric combos
        for src in nodes:
            for dst in nodes:
                for metric in ("distance", "travel_time", "cost"):
                    provider.shortest_path(src, dst, metric)

        after = _graph_signature(g)
        self.assertEqual(
            before,
            after,
            msg="PathProvider queries must not mutate the underlying graph",
        )

        # And the cache itself should only store reachable PathResults,
        # never None / wrong-shape objects.
        self.assertIsInstance(provider._cache, dict)  # noqa: SLF001
        for key, val in provider._cache.items():
            self.assertEqual(len(key), 4)
            self.assertTrue(hasattr(val, "reachable"))

    # -- C. service_time from simulation block ------------------------------

    def test_service_time_from_simulation_block_minimal(self) -> None:
        """``service_time`` must be sourced from ``simulation.service_time``."""
        b = _build_minimal_scenario(service_time=7.5, initial_time=100.0)
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        stops: tuple[DeliveryStop, ...] = r.route_plan.stops

        customer_stops = [s for s in stops if s.order_id is not None]
        self.assertGreater(
            len(customer_stops), 0,
            msg="expected at least one customer stop in the closed tour",
        )
        for s in customer_stops:
            delta = s.service_end - s.service_start
            self.assertAlmostEqual(
                delta,
                7.5,
                places=6,
                msg=f"service_end - service_start must equal simulation.service_time, "
                    f"got {delta} for stop node={s.node_id}",
            )
        # Depot stops must have service_end == service_start
        depot_stops = [s for s in stops if s.order_id is None]
        for s in depot_stops:
            self.assertAlmostEqual(
                s.service_end,
                s.service_start,
                places=6,
                msg="depot stops must not accumulate service_time",
            )

    # -- H. Violation kinds whitelist ---------------------

    def test_unserved_orders_have_known_kinds_on_minimal(self) -> None:
        """All Violation.kind values must come from VIOLATION_KINDS."""
        # Build a scenario whose single order's destination is NOT in the
        # graph, so the eligibility filter classifies it as unreachable.
        b = _build_minimal_scenario(
            orders=[
                Order(
                    id="O_BAD",
                    destination_id="NOT_IN_GRAPH",
                    demand=1.0,
                    time_window_start=0.0,
                    time_window_end=1000.0,
                    priority=OrderPriority.NORMAL,
                    status=OrderStatus.PENDING,
                ),
            ]
        )
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        # Either filter marked it OR the planner unserved it; either way the
        # kind must be a known one.
        self.assertGreaterEqual(len(r.unserved_orders), 1)
        for v in r.unserved_orders:
            self.assertIn(
                v.kind,
                VIOLATION_KINDS,
                msg=f"violation kind {v.kind!r} not in whitelist {VIOLATION_KINDS}",
            )
            self.assertEqual(v.order_id, "O_BAD")

    # -- I. JSON round-trip on minimal scenario ---------------------

    def test_json_roundtrip_on_minimal_scenario(self) -> None:
        """``ScheduleResult.to_dict()`` must be ``json.dumps``-safe."""
        b = _build_minimal_scenario()
        r = plan_deliveries(b, "nearest_neighbor", "distance")

        d = r.to_dict()
        # Must be JSON-serializable.
        blob = json.dumps(d)
        self.assertIsInstance(blob, str)
        self.assertGreater(len(blob), 0)

        # Round-trip equality on a few high-level fields.
        restored = json.loads(blob)
        self.assertEqual(restored["scenario_name"], b.name)
        self.assertEqual(restored["depot_id"], r.depot_id)
        self.assertEqual(restored["vehicle_id"], r.vehicle_id)
        self.assertEqual(restored["algorithm"], "nearest_neighbor")
        self.assertEqual(restored["objective"], "distance")
        self.assertEqual(
            restored["served_order_ids"], list(r.served_order_ids)
        )


# ---------------------------------------------------------------------------
#  End-to-end regression tests on the fixed scenario
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    SCENARIO_FILE.is_file(),
    "fixed scenario config/scenario.json is not present",
)
class TestPhase3RegressionFixedScenario(unittest.TestCase):
    """End-to-end regression: ``plan_deliveries`` on the bundled fixed scenario."""

    def setUp(self) -> None:
        self.bundle = load_scenario(SCENARIO_FILE)
        self.scenario_name = self.bundle.name

    # -- A.1 graph immutability across three algorithms --------------------

    def test_graph_unchanged_across_three_algorithms(self) -> None:
        """Run all three algorithms; the graph fingerprint must not change."""
        g = self.bundle.graph
        before = _graph_signature(g)
        # Also snapshot a specific edge weight for explicit per-edge check.
        any_edge: Edge | None = None
        for src in g.node_ids:
            for nbr in g.get_neighbors(src):
                any_edge = nbr
                break
            if any_edge is not None:
                break
        self.assertIsNotNone(any_edge)
        captured_weight = (
            any_edge.distance,
            any_edge.travel_time,
            any_edge.cost,
        )

        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                plan_deliveries(self.bundle, algo, "distance")
                after = _graph_signature(g)
                self.assertEqual(
                    before,
                    after,
                    msg=f"graph state must not change after {algo}",
                )
                # Per-edge check on the captured edge: weights unchanged.
                still = g.get_edge(any_edge.source_id, any_edge.target_id)
                self.assertEqual(
                    (still.distance, still.travel_time, still.cost),
                    captured_weight,
                    msg=f"edge weights must not change after {algo}",
                )

    # -- A.3 two_opt seed plan not mutated ---------------------

    def test_two_opt_inversions_do_not_modify_input_plan(self) -> None:
        """2-opt must not mutate the input ``RoutePlan`` (frozen dataclass)."""
        nn_result = plan_deliveries(
            self.bundle, "nearest_neighbor", "distance"
        )
        seed: RoutePlan = nn_result.route_plan
        seed_id_before = id(seed)
        seed_total_before = seed.main_objective_total
        seed_seq_before = seed.stop_sequence
        seed_legs_before = seed.legs
        seed_stops_before = seed.stops

        # Run 2-opt — internally builds its own seed from NN, but the
        # captured seed object reference must remain pristine.
        two_opt_result = plan_deliveries(
            self.bundle, "two_opt", "distance"
        )
        self.assertIsNotNone(two_opt_result.route_plan)

        self.assertEqual(id(seed), seed_id_before)
        self.assertEqual(seed.main_objective_total, seed_total_before)
        self.assertEqual(seed.stop_sequence, seed_seq_before)
        self.assertEqual(seed.legs, seed_legs_before)
        self.assertEqual(seed.stops, seed_stops_before)

    # -- B.1 main_objective_total vs total_distance for all algos ----------

    def test_objective_distance_main_matches_total_distance(self) -> None:
        """Under ``objective='distance'``, ``main_objective_total`` ==
        ``total_distance`` for all three algorithms."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                self.assertAlmostEqual(
                    r.main_objective_total,
                    r.total_distance,
                    places=6,
                    msg=f"{algo}: main_objective_total must equal total_distance",
                )

    # -- B.2: total_travel_time comes from cross_metrics, not total_weight ----

    def test_travel_time_uses_cross_metrics_under_both_objectives(self) -> None:
        """``total_travel_time`` must equal sum of cross_metrics['travel_time']."""
        for objective in ("distance", "cost"):
            with self.subTest(objective=objective):
                r = plan_deliveries(
                    self.bundle, "nearest_neighbor", objective
                )
                legs = r.route_plan.legs
                expected_travel = sum(
                    float(leg.cross_metrics["travel_time"]) for leg in legs
                )
                self.assertAlmostEqual(
                    r.total_travel_time,
                    expected_travel,
                    places=6,
                    msg=(
                        f"total_travel_time must equal "
                        f"sum(leg.cross_metrics['travel_time']) under objective={objective}"
                    ),
                )
                # Sanity: in this scenario the chosen metric's total_weight
                # differs from the time metric (distance / cost vs time).
                # If they're accidentally equal we'd have a degenerate graph
                # and the test is meaningless — but the fixed scenario is
                # designed to have different values.
                chosen_total = sum(leg.total_weight for leg in legs)
                self.assertNotAlmostEqual(
                    r.total_travel_time,
                    chosen_total,
                    places=3,
                    msg=(
                        "fixed-scenario regression: travel_time should differ "
                        "from leg.total_weight sum (objectives disagree). "
                        "If this fires, the scenario file may have been "
                        "rewritten with metric-aligned weights."
                    ),
                )

    # -- C.6: service_time from simulation (default scenario) --------------

    def test_service_time_from_simulation_block_default(self) -> None:
        """Default scenario: customer stops accumulate exactly the scenario's
        ``service_time`` (5.0)."""
        expected = float(self.bundle.simulation.get("service_time", 5.0))
        self.assertAlmostEqual(expected, 5.0, places=6)

        r = plan_deliveries(self.bundle, "nearest_neighbor", "distance")
        stops = r.route_plan.stops
        customer_stops = [s for s in stops if s.order_id is not None]
        self.assertGreater(
            len(customer_stops), 0,
            msg="fixed scenario must produce at least one customer stop",
        )
        for s in customer_stops:
            delta = s.service_end - s.service_start
            self.assertAlmostEqual(
                delta,
                expected,
                places=6,
                msg=(
                    f"customer stop node={s.node_id} delta={delta} should "
                    f"equal simulation.service_time={expected}"
                ),
            )

    # -- D.7: single-vehicle enforcement ---------------------

    def test_schedule_result_uses_one_vehicle_id(self) -> None:
        """``ScheduleResult`` must reference exactly one vehicle_id and a
        courier (when populated) that drives that vehicle."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                # vehicle_id must be one of the scenario's vehicle IDs.
                scenario_v_ids = {v.id for v in self.bundle.vehicles}
                self.assertIn(
                    r.vehicle_id,
                    scenario_v_ids,
                    msg=f"{algo}: vehicle_id={r.vehicle_id!r} not in scenario",
                )
                # courier_id, when populated, must drive the chosen vehicle.
                # (Some algorithms do not thread the courier through; that's
                # tolerated here as long as the contract on vehicle_id holds.)
                if r.courier_id is not None:
                    matching_couriers = [
                        c for c in self.bundle.couriers
                        if c.id == r.courier_id
                    ]
                    self.assertEqual(
                        len(matching_couriers), 1,
                        msg=f"{algo}: courier_id={r.courier_id!r} not found",
                    )
                    self.assertEqual(
                        matching_couriers[0].vehicle_id,
                        r.vehicle_id,
                        msg=(
                            f"{algo}: courier {r.courier_id!r} drives "
                            f"{matching_couriers[0].vehicle_id!r}, "
                            f"not the chosen vehicle {r.vehicle_id!r}"
                        ),
                    )
                # And vice-versa: any courier in the scenario that drives
                # this vehicle must include the chosen courier_id, ensuring
                # at-most-one courier-vehicle binding per result.
                candidates_for_vehicle = [
                    c.id for c in self.bundle.couriers
                    if c.vehicle_id == r.vehicle_id
                ]
                if r.courier_id is not None:
                    self.assertIn(
                        r.courier_id,
                        candidates_for_vehicle,
                        msg=(
                            f"{algo}: chosen courier {r.courier_id!r} "
                            f"not bound to vehicle {r.vehicle_id!r}"
                        ),
                    )

    # -- E.8: closed-tour for all algos -------------------

    def test_stop_sequence_first_equals_last_for_all_algorithms(self) -> None:
        """All algorithms must produce a closed tour
        ``[depot, ..., depot]``."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                seq = r.route_plan.stop_sequence
                self.assertGreaterEqual(
                    len(seq), 2,
                    msg=f"{algo}: tour must have >= 2 stops",
                )
                self.assertEqual(
                    seq[0],
                    r.depot_id,
                    msg=f"{algo}: tour start must equal depot_id",
                )
                self.assertEqual(
                    seq[-1],
                    r.depot_id,
                    msg=f"{algo}: tour end must equal depot_id (closed loop)",
                )
                self.assertEqual(
                    seq[0],
                    seq[-1],
                    msg=f"{algo}: first and last stop must match",
                )

    # -- F.9: planning stats sane -------------------

    def test_planning_stats_counters_within_bounds(self) -> None:
        """All ``PlanningStats`` counters must satisfy their invariants."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                stats: PlanningStats = r.planning_stats
                # All int counters are non-negative.
                for name in (
                    "cache_hits",
                    "cache_misses",
                    "dijkstra_calls",
                    "paths_evaluated",
                    "feasibility_checks",
                    "iterations",
                ):
                    val = getattr(stats, name)
                    self.assertIsInstance(val, int)
                    self.assertGreaterEqual(
                        val, 0,
                        msg=f"{algo}.{name} must be non-negative, got {val}",
                    )
                # Runtime strictly positive (any real call to monotonic()).
                self.assertGreater(
                    stats.runtime_seconds,
                    0.0,
                    msg=f"{algo}: runtime_seconds must be > 0",
                )
                # We routed legs through Dijkstra.
                self.assertGreaterEqual(
                    stats.dijkstra_calls, 1,
                    msg=f"{algo}: dijkstra_calls must be >= 1",
                )
                # Every dijkstra call produces a paths_evaluated increment.
                self.assertGreaterEqual(
                    stats.paths_evaluated,
                    stats.dijkstra_calls,
                    msg=(
                        f"{algo}: paths_evaluated ({stats.paths_evaluated}) "
                        f"must be >= dijkstra_calls ({stats.dijkstra_calls})"
                    ),
                )

    # -- G.10: 2-opt never worsens NN seed -------------------

    def test_two_opt_does_not_worsen_nn_seed(self) -> None:
        """``two_opt``'s ``main_objective_total`` must be ``<=`` NN's."""
        nn_result = plan_deliveries(
            self.bundle, "nearest_neighbor", "distance"
        )
        two_opt_result = plan_deliveries(
            self.bundle, "two_opt", "distance"
        )
        self.assertLessEqual(
            two_opt_result.main_objective_total,
            nn_result.main_objective_total,
            msg=(
                "constrained_two_opt must never worsen the NN seed: "
                f"NN={nn_result.main_objective_total}, "
                f"2opt={two_opt_result.main_objective_total}"
            ),
        )

    # -- H.11: Violation.kind whitelist (fixed scenario) -----------------

    def test_unserved_orders_have_known_kinds(self) -> None:
        """All Violation.kind values across all algorithms are whitelisted."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                for v in r.unserved_orders:
                    self.assertIsInstance(v, Violation)
                    self.assertIn(
                        v.kind,
                        VIOLATION_KINDS,
                        msg=(
                            f"{algo}: Violation.kind={v.kind!r} not in "
                            f"whitelist {VIOLATION_KINDS}"
                        ),
                    )

    # -- I.12: JSON round-trip on the full fixed scenario -----------------

    def test_schedule_result_to_dict_is_json_dumps_safe(self) -> None:
        """``ScheduleResult.to_dict()`` must round-trip through ``json``."""
        for algo in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algo):
                r = plan_deliveries(self.bundle, algo, "distance")
                d = r.to_dict()

                # JSON-serializable.
                blob = json.dumps(d)
                self.assertIsInstance(blob, str)
                self.assertGreater(len(blob), 0)

                # Round-trip equality of key identifiers.
                restored = json.loads(blob)
                self.assertEqual(
                    restored["scenario_name"], self.scenario_name,
                    msg=f"{algo}: scenario_name round-trip mismatch",
                )
                self.assertEqual(
                    restored["depot_id"], r.depot_id,
                    msg=f"{algo}: depot_id round-trip mismatch",
                )
                self.assertEqual(
                    restored["vehicle_id"], r.vehicle_id,
                    msg=f"{algo}: vehicle_id round-trip mismatch",
                )
                self.assertEqual(
                    restored["algorithm"], algo,
                    msg=f"{algo}: algorithm round-trip mismatch",
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()