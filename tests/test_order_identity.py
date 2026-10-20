"""P0: order identity is independent of destinations and route visit counts."""
from __future__ import annotations

from dataclasses import replace
import unittest

from logiroute.config.loader import ScenarioBundle
from logiroute.core import Edge, Node, NodeType, Order, OrderPriority, Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scenario_generator.validator import validate_generated_scenario
from logiroute.core.order_identity import OrderCoverageReport


def identity_scenario() -> ScenarioBundle:
    graph = LogisticsGraph()
    for name, kind in (("W", NodeType.WAREHOUSE), ("C1", NodeType.CUSTOMER),
                       ("C2", NodeType.CUSTOMER)):
        graph.add_node(Node(name, name, kind, 0, 0))
    for left, right in (("W", "C1"), ("C1", "C2"), ("C2", "W"),
                        ("C1", "W"), ("C2", "C1"), ("W", "C2")):
        graph.add_edge(Edge(left, right, 1, 1, 1))
    return ScenarioBundle(
        "identity", "fixed", 0, graph, vehicles=[Vehicle("V", 100, current_node_id="W")],
        orders=[Order("O1", "C1", 5, 0, 20, OrderPriority.URGENT),
                Order("O2", "C1", 8, 0, 30), Order("O3", "C2", 3, 0, 40)],
        simulation={"initial_time": 0, "service_time": 1},
    )


class TestIdentityP0(unittest.TestCase):
    def test_legacy_nodes_do_not_prove_same_destination_orders_served(self) -> None:
        report = validate_generated_scenario(identity_scenario(), ["W", "C1", "C2", "W"])
        self.assertFalse(report.all_orders_covered)
        self.assertFalse(report.feasible)

    def test_duplicate_input_ids_are_rejected(self) -> None:
        bundle = identity_scenario()
        bundle.orders[1] = replace(bundle.orders[1], id="O1")
        with self.assertRaises(ValueError):
            validate_generated_scenario(bundle, ["W", "C1", "C2", "W"])

    def test_one_visit_can_serve_two_distinct_orders(self) -> None:
        from logiroute.core.order_identity import ServiceAssignment
        report = validate_generated_scenario(
            identity_scenario(), ["W", "C1", "C2", "W"],
            assignments=[ServiceAssignment("O1", 1), ServiceAssignment("O2", 1),
                         ServiceAssignment("O3", 2)],
        )
        self.assertTrue(report.all_orders_covered, report.violations)
        self.assertTrue(report.route_coverage_ok)
        self.assertTrue(report.feasible, report.violations)
        self.assertEqual(report.total_demand, 16)

    def test_each_same_site_order_has_its_own_service_time(self) -> None:
        from logiroute.core.order_identity import ServiceAssignment
        bundle = identity_scenario()
        bundle.orders[1] = replace(bundle.orders[1], time_window_end=1.5)
        report = validate_generated_scenario(
            bundle, ["W", "C1", "C2", "W"], assignments=[
                ServiceAssignment("O1", 1), ServiceAssignment("O2", 1), ServiceAssignment("O3", 2)],
        )
        self.assertTrue(report.all_orders_covered)
        self.assertFalse(report.time_windows_ok)

    def test_assignment_at_wrong_node_is_rejected(self) -> None:
        from logiroute.core.order_identity import ServiceAssignment
        report = validate_generated_scenario(identity_scenario(), ["W", "C1", "C2", "W"],
            assignments=[ServiceAssignment("O1", 2), ServiceAssignment("O2", 1),
                         ServiceAssignment("O3", 2)])
        self.assertFalse(report.route_coverage_ok)
        self.assertFalse(report.feasible)

    def test_repeated_node_visits_can_have_distinct_service_assignments(self) -> None:
        from logiroute.core.order_identity import ServiceAssignment
        report = validate_generated_scenario(identity_scenario(), ["W", "C1", "C2", "C1", "W"],
            assignments=[ServiceAssignment("O1", 1), ServiceAssignment("O2", 3),
                         ServiceAssignment("O3", 2)])
        self.assertTrue(report.feasible, report.violations)

    def test_missing_witness_is_marked_unchecked(self) -> None:
        report = validate_generated_scenario(identity_scenario())
        self.assertFalse(report.coverage_checked)
        self.assertFalse(report.all_orders_covered)

    def test_assignments_without_route_are_rejected(self) -> None:
        from logiroute.core.order_identity import ServiceAssignment
        with self.assertRaises(ValueError):
            validate_generated_scenario(identity_scenario(), assignments=[ServiceAssignment("O1", 1)])

    def test_unserved_results_without_route_are_not_silently_ignored(self) -> None:
        with self.assertRaises(ValueError):
            validate_generated_scenario(identity_scenario(), unserved_order_ids=('GHOST',))

    def test_empty_or_nonwarehouse_closed_route_is_not_a_delivery_witness(self) -> None:
        for route in ([], ["W"], ["C1", "C2", "C1"]):
            with self.subTest(route=route):
                self.assertFalse(validate_generated_scenario(identity_scenario(), route).closed_route_ok)

    def test_fleet_capacity_is_explicitly_unchecked(self) -> None:
        bundle = identity_scenario()
        bundle.vehicles.append(Vehicle("V2", 100, current_node_id="W"))
        report = validate_generated_scenario(bundle)
        self.assertFalse(report.capacity_checked)
        self.assertFalse(report.feasible)
        self.assertIn('capacity.allocation_unchecked', [kind for kind, _ in report.violations])

    def test_validation_report_retains_exact_total_until_json_boundary(self) -> None:
        from decimal import Decimal
        bundle = identity_scenario()
        bundle.orders = [Order('O1', 'C1', 100, 0, 20),
                         Order('O2', 'C2', Decimal('1e-40'), 0, 20)]
        report = validate_generated_scenario(bundle, ['W', 'C1', 'C2', 'W'])
        self.assertGreater(report.total_demand, Decimal(100))
        self.assertFalse(report.capacity_ok)
        self.assertEqual(Decimal(report.to_dict()['total_demand_decimal']), report.total_demand)

    def test_inactive_orders_cannot_be_validated_as_new_service_tasks(self) -> None:
        from logiroute.core import OrderStatus, ServiceAssignment
        for status in (OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.DELIVERED,
                       OrderStatus.IN_TRANSIT, OrderStatus.CREATED):
            bundle = identity_scenario()
            bundle.orders[0].status = status
            with self.subTest(status=status):
                report = validate_generated_scenario(bundle, ['W', 'C1', 'C2', 'W'],
                    assignments=[ServiceAssignment('O1', 1), ServiceAssignment('O2', 1),
                                 ServiceAssignment('O3', 2)])
                self.assertFalse(report.feasible)
                self.assertIn('order.inactive_service', [kind for kind, _ in report.violations])


class TestOrderPartitions(unittest.TestCase):
    def validate(self, served: tuple[str, ...], unserved: tuple[str, ...] = ()) -> OrderCoverageReport:
        from logiroute.core.order_identity import validate_order_coverage
        return validate_order_coverage(identity_scenario().orders, served, unserved)

    def test_three_orders_two_destinations(self) -> None:
        report = self.validate(("O1", "O2", "O3"))
        self.assertTrue(report.valid)
        self.assertTrue(report.all_orders_served)

    def test_missing_same_site_order(self) -> None:
        self.assertFalse(self.validate(("O1", "O3")).valid)

    def test_duplicate_service(self) -> None:
        self.assertFalse(self.validate(("O1", "O2", "O3", "O1")).valid)

    def test_overlap(self) -> None:
        self.assertFalse(self.validate(("O1", "O2", "O3"), ("O1",)).valid)

    def test_unknown_service_id(self) -> None:
        self.assertFalse(self.validate(("O1", "O2", "O3", "GHOST")).valid)

    def test_unknown_unserved_id(self) -> None:
        self.assertFalse(self.validate(("O1", "O2", "O3"), ("GHOST",)).valid)

    def test_duplicate_unserved_id(self) -> None:
        self.assertFalse(self.validate(("O1", "O3"), ("O2", "O2")).valid)

    def test_complete_partition_is_not_full_service(self) -> None:
        report = self.validate(("O1", "O3"), ("O2",))
        self.assertTrue(report.valid)
        self.assertFalse(report.all_orders_served)

    def test_empty_orders(self) -> None:
        from logiroute.core.order_identity import validate_order_coverage
        report = validate_order_coverage([], (), ())
        self.assertTrue(report.valid)
        self.assertTrue(report.all_orders_served)

    def test_duplicate_input_even_with_partition_is_rejected(self) -> None:
        from logiroute.core.order_identity import validate_order_coverage
        orders = identity_scenario().orders
        with self.assertRaises(ValueError):
            validate_order_coverage(orders + [replace(orders[0], demand=9)], ("O1", "O2", "O3"))
