"""Dynamic intake, transactional replanning and execution identity regressions."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from logiroute.core import Order
from logiroute.core.enums import OrderPriority, OrderStatus
from logiroute.dynamic.config import load_dynamic_config
from logiroute.dynamic.session import DynamicSession, DynamicStateError
from logiroute.dynamic.validator import validate_dynamic_snapshot
from tests.fleet_fixtures import toy

ROOT = Path(__file__).resolve().parents[1]


class TestDynamicOrders(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_dynamic_config(ROOT/'config/dynamic_orders.json')

    def session(self, orders=None, capacities=(10,)) -> DynamicSession:
        return DynamicSession(toy(orders, capacities), self.config)

    def drain(self, session: DynamicSession) -> None:
        for _ in range(200):
            if session.step() is None:
                return
        self.fail('execution failed to terminate')

    def test_same_site_multiple_orders_are_delivered_once_each(self) -> None:
        session = self.session([Order('A1','A',1,0,100), Order('A2','A',1,0,100)])
        self.assertEqual(session.replan().status, 'applied')
        session.depart()
        self.drain(session)
        snapshot = session.snapshot()
        self.assertEqual({o.id for o in snapshot.orders if o.status is OrderStatus.DELIVERED}, {'A1','A2'})
        self.assertEqual([e.order_id for e in snapshot.events if e.kind=='service'].count('A1'), 1)
        self.assertEqual([e.order_id for e in snapshot.events if e.kind=='service'].count('A2'), 1)
        self.assertTrue(session.validate().valid)

    def test_duplicate_ids_include_terminal_history(self) -> None:
        session = self.session([Order('A1','A',1,0,100)])
        session.cancel('A1')
        before = session.snapshot().to_dict()
        with self.assertRaises(ValueError):
            session.submit(Order('A1','B',1,0,100))
        self.assertEqual(before, session.snapshot().to_dict())

    def test_busy_arrival_waits_without_resetting_car_or_loading_new_cargo(self) -> None:
        session = self.session([Order('A1','A',1,0,100)])
        session.replan(); session.depart(); session.step()
        before = session.snapshot().vehicles[0]
        receipt = session.submit_manual('B', Decimal('2'), 0, 100)
        self.assertEqual(receipt.status, 'queued')
        self.assertEqual(session.replan().status, 'deferred')
        after = session.snapshot().vehicles[0]
        self.assertEqual((after.current_node_id,after.current_load,after.onboard_order_ids),
                         (before.current_node_id,before.current_load,before.onboard_order_ids))
        self.drain(session)
        self.assertEqual(session.replan().status, 'applied')
        self.assertEqual(tuple(s.order_id for r in session.snapshot().plan.routes for s in r.services),
                         (receipt.order_id,))
        session.depart(); self.drain(session)
        self.assertEqual(len([e for e in session.snapshot().events if e.kind=='service']), 2)
        self.assertTrue(session.validate().valid)

    def test_incomplete_replan_preserves_old_plan_and_statuses(self) -> None:
        session = self.session([Order('A1','A',1,0,100)], (1,))
        session.replan(); old = session.snapshot().plan
        new = session.submit_manual('B',1,0,100)
        self.assertEqual(session.replan().status, 'incomplete')
        self.assertEqual(session.snapshot().plan, old)
        self.assertEqual(session.order('A1').status, OrderStatus.PLANNED)
        self.assertEqual(session.order(new.order_id).status, OrderStatus.PENDING)
        session.depart(); self.drain(session)
        self.assertEqual(session.order('A1').status, OrderStatus.DELIVERED)
        session.replan(); session.depart(); self.drain(session)
        self.assertEqual(session.order(new.order_id).status, OrderStatus.DELIVERED)

    def test_stale_and_forged_proposals_do_not_commit(self) -> None:
        session = self.session()
        proposal = session.prepare_replan()
        session.submit_manual('A',1,0,100)
        with self.assertRaises(DynamicStateError):
            session.commit_replan(proposal)
        proposal = session.prepare_replan()
        forged = replace(proposal, result=replace(proposal.result, routes=()))
        with self.assertRaises(DynamicStateError):
            session.commit_replan(forged)
        self.assertIsNone(session.snapshot().plan)

    def test_planner_exception_leaves_previous_plan_intact(self) -> None:
        session = self.session(); session.replan()
        before = session.snapshot().to_dict()
        with patch('logiroute.dynamic.session.plan_fleet', side_effect=RuntimeError('defect')):
            with self.assertRaisesRegex(RuntimeError, 'defect'):
                session.replan()
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_exact_cargo_boundary_and_rejected_single_order(self) -> None:
        session = self.session([Order('A1','A',Decimal('0.1'),0,100),
                                Order('A2','A',Decimal('0.2'),0,100)], (Decimal('0.3'),))
        session.replan(); session.depart()
        self.assertEqual(session.snapshot().vehicles[0].current_load, Decimal('0.3'))
        with self.assertRaises(ValueError):
            session.submit_manual('B',Decimal('0.30000000000000000000001'),0,100)
        self.drain(session)
        self.assertEqual(session.snapshot().vehicles[0].current_load, Decimal(0))

    def test_queue_update_cancel_expire_and_terminal_rules(self) -> None:
        session = self.session()
        session.update_pending('O2', priority=OrderPriority.URGENT, time_window_end=10)
        self.assertEqual(session.next_pending().id, 'O2')
        session.cancel('O2')
        session.advance_to(101)
        session.expire('O1')
        self.assertIsNone(session.next_pending())
        for status in ('cancel', 'expire'):
            with self.assertRaises(ValueError): getattr(session,status)('O1')
        self.assertTrue(session.validate().valid)

    def test_planned_cancel_withdraws_before_departure(self) -> None:
        session = self.session(); session.replan(); session.cancel('O1')
        self.assertIsNone(session.snapshot().plan)
        self.assertEqual(session.order('O2').status, OrderStatus.PENDING)
        session.replan(); session.depart()
        with self.assertRaises(ValueError): session.cancel('O2')
        self.drain(session)

    def test_structural_validation_and_failed_update_are_atomic(self) -> None:
        session = self.session()
        before = session.snapshot().to_dict()
        for args in (('missing',1,0,100),('W',1,0,100),('A',100,0,100),('A',1,0,-1)):
            with self.subTest(args=args), self.assertRaises(ValueError): session.submit_manual(*args)
        with self.assertRaises(ValueError): session.update_pending('O1',time_window_end=-1)
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_automatic_initial_manual_use_unique_unified_ids(self) -> None:
        session = self.session([])
        first = session.submit_automatic(seed=42)
        second = session.submit_automatic(seed=42)
        self.assertNotEqual(first.order_id, second.order_id)
        self.assertEqual(session.order(first.order_id).destination_id,
                         session.order(second.order_id).destination_id)
        self.assertEqual(session.order(first.order_id).demand,session.order(second.order_id).demand)
        self.assertTrue(session.validate().valid)

    def test_caller_mutations_cannot_change_session_or_queue(self) -> None:
        original = toy(); session = DynamicSession(original,self.config)
        original.orders[0].id='bad'; original.vehicles[0].current_node_id='bad'
        order = Order('N','A',1,0,100); session.submit(order); order.priority=OrderPriority.URGENT
        self.assertEqual(session.order('N').priority, OrderPriority.NORMAL)
        self.assertEqual(session.snapshot().vehicles[0].current_node_id,'W')
        self.assertTrue(session.validate().valid)

    def test_inflight_position_and_clock_are_not_reset(self) -> None:
        session = self.session(); session.replan(); session.depart(); session.advance_to(0.5)
        snapshot = session.snapshot()
        self.assertEqual(snapshot.time,0.5)
        self.assertEqual(snapshot.vehicles[0].action_kind,'travel')
        self.assertTrue(snapshot.vehicles[0].in_flight_path)
        self.assertEqual(session.replan().status,'deferred')
        with self.assertRaises(ValueError): session.advance_to(0.4)

    def test_independent_snapshot_validator_rejects_tampering(self) -> None:
        original = toy(); session = DynamicSession(original,self.config)
        session.replan(); session.depart()
        snapshot = session.snapshot()
        broken = replace(snapshot, vehicles=(replace(snapshot.vehicles[0],current_load=Decimal(0)),))
        self.assertFalse(validate_dynamic_snapshot(original.graph,broken).valid)
        broken = replace(snapshot,pending_ids=('O1',))
        self.assertFalse(validate_dynamic_snapshot(original.graph,broken).valid)

    def test_idle_clock_change_marks_committed_schedule_stale(self) -> None:
        session=self.session(); session.replan(); session.advance_to(0.5)
        self.assertTrue(session.snapshot().needs_replan)
        with self.assertRaises(DynamicStateError): session.depart()
        session.replan(); session.depart(); self.drain(session)
        self.assertTrue(session.validate().valid)

    def test_automatic_seed_is_retained_in_event_history(self) -> None:
        session=self.session([]); receipt=session.submit_automatic(seed=2026)
        event=session.snapshot().events[-1]
        self.assertEqual(event.order_id,receipt.order_id)
        self.assertEqual(event.seed,2026)

    def test_customer_must_be_reachable_and_returnable(self) -> None:
        original=toy([])
        for edge in list(original.graph.edges):
            if edge.source_id=='A': original.graph.remove_edge(edge.source_id,edge.target_id)
        session=DynamicSession(original,self.config)
        with self.assertRaises(ValueError): session.submit_manual('A',1,0,100)
        self.assertEqual(session.snapshot().orders,())

    def test_creation_state_is_normalized_without_mutating_source(self) -> None:
        original=Order('C','A',1,0,100,status=OrderStatus.CREATED)
        session=self.session([original])
        self.assertEqual(original.status,OrderStatus.CREATED)
        self.assertEqual(session.order('C').status,OrderStatus.PENDING)
        with self.assertRaises(ValueError):
            self.session([Order('I','A',1,0,100,status=OrderStatus.IN_TRANSIT)])

    def test_service_start_at_deadline_can_finish_after_it(self) -> None:
        session=self.session([Order('T','A',1,0,1)])
        session.replan(); session.depart(); self.drain(session)
        event=next(e for e in session.snapshot().events if e.kind=='service')
        self.assertEqual(event.start_time,1)
        self.assertEqual(event.time,2)
        self.assertTrue(session.validate().valid)

    def test_zero_demand_and_multiple_depots_keep_real_state(self) -> None:
        original=toy([Order('Z','A',0,0,100),Order('P','B',1,0,100)],(1,1),('W','W2'))
        session=DynamicSession(original,self.config); session.replan('cost'); session.depart()
        self.drain(session)
        self.assertEqual([v.current_node_id for v in session.snapshot().vehicles],['W','W2'])
        self.assertTrue(all(o.status is OrderStatus.DELIVERED for o in session.snapshot().orders))
        self.assertTrue(session.validate().valid)

    def test_malicious_travel_and_duplicate_service_history_are_rejected(self) -> None:
        original=toy(); session=DynamicSession(original,self.config)
        session.replan(); session.depart(); self.drain(session)
        snapshot=session.snapshot()
        events=list(snapshot.events)
        index=next(i for i,e in enumerate(events) if e.kind=='travel')
        events[index]=replace(events[index],path=('W','missing','A'))
        self.assertFalse(validate_dynamic_snapshot(original.graph,replace(snapshot,events=tuple(events))).valid)
        service=next(e for e in snapshot.events if e.kind=='service')
        bad=replace(service,sequence=len(snapshot.events)+1,time=snapshot.time)
        self.assertFalse(validate_dynamic_snapshot(original.graph,replace(snapshot,events=snapshot.events+(bad,))).valid)

    def test_requested_objective_cannot_be_changed_by_a_proposal(self) -> None:
        session=self.session(); proposal=session.prepare_replan('distance')
        forged=replace(proposal,result=replace(proposal.result,objective='cost'))
        with self.assertRaises(DynamicStateError): session.commit_replan(forged)

    def test_invalid_objective_is_rejected_even_while_busy(self) -> None:
        session=self.session(); session.replan(); session.depart()
        with self.assertRaises(ValueError): session.replan('travel_time')

    def test_cancelling_unassigned_order_does_not_hide_stale_plan(self) -> None:
        session=self.session(); session.replan(); session.advance_to(0.5)
        item=session.submit_manual('A',1,0,100); session.cancel(item.order_id)
        self.assertTrue(session.snapshot().needs_replan)
        self.assertTrue(session.validate().valid,session.validate().violations)

    def test_boolean_time_fields_are_rejected_atomically(self) -> None:
        session=self.session(); before=session.snapshot().to_dict()
        with self.assertRaises(ValueError): session.submit_manual('A',1,False,100)
        with self.assertRaises(ValueError): session.update_pending('O1',time_window_end=True)
        self.assertEqual(session.snapshot().to_dict(),before)

    def test_auditor_rejects_changed_admission_and_idle_courier(self) -> None:
        from logiroute.core.enums import CourierStatus
        original=toy(); session=DynamicSession(original,self.config)
        snapshot=session.snapshot(); events=list(snapshot.events)
        events[0]=replace(events[0],quantity=Decimal(999))
        self.assertFalse(validate_dynamic_snapshot(original.graph,replace(snapshot,events=tuple(events))).valid)
        vehicles=(replace(snapshot.vehicles[0],courier_status=CourierStatus.DELIVERING),)
        self.assertFalse(validate_dynamic_snapshot(original.graph,replace(snapshot,vehicles=vehicles)).valid)

    def test_auditor_reports_nonfinite_observed_capacity_without_crashing(self) -> None:
        original=toy(); session=DynamicSession(original,self.config); session.replan(); session.depart()
        snapshot=session.snapshot()
        bad=replace(snapshot,vehicles=(replace(snapshot.vehicles[0],capacity=Decimal('NaN')),))
        self.assertFalse(validate_dynamic_snapshot(original.graph,bad).valid)
