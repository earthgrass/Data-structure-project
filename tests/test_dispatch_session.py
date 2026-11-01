from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.session import Session,ConflictError
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.planner import plan_dispatch


class TestDispatchSession(unittest.TestCase):
    def test_execution_conserves_and_only_customer_signoff_delivers(self) -> None:
        session=Session(make_state(42)); plan=session.prepare('distance'); session.apply(plan); session.depart()
        saw_hub=False
        while session.running:
            session.step()
            for key,loc in session.state.locations.items():
                if loc[0]=='hub': saw_hub=True; self.assertNotEqual(session.state.orders[key].status,'delivered')
        self.assertTrue(saw_hub)
        self.assertTrue(all(o.status=='delivered' for o in session.state.orders.values()))
        self.assertTrue(session.audit().valid,session.audit().violations)

    def test_in_transit_insert_pause_replan_preserves_cargo_and_history(self) -> None:
        s=Session(make_state(1)); s.apply(s.prepare('distance')); s.depart(); s.step()
        old=s.state.locations.copy(); before=len(s.events)
        first=next(iter(s.state.orders.values()))
        s.add_order('new',first.destination,Decimal('0.1'),s.state.now,s.state.now+2000,'urgent')
        with self.assertRaises(ConflictError): s.prepare('cost')
        s.pause()
        while s.running: s.step()
        self.assertEqual(old,{k:s.state.locations[k] for k in old})
        s.apply(s.prepare('cost')); s.depart()
        while s.running: s.step()
        self.assertEqual(s.state.orders['new'].status,'delivered')
        self.assertGreater(len(s.events),before)
        self.assertTrue(s.audit().valid,s.audit().violations)

    def test_stale_forged_plan_and_loaded_cancellation_rejected(self) -> None:
        s=Session(make_state(0)); p=s.prepare('distance')
        first=next(iter(s.state.orders.values()))
        s.add_order('new',first.destination,1,0,2000,'normal')
        with self.assertRaises(ConflictError): s.apply(p)
        p=s.prepare('distance')
        with self.assertRaises(ValueError): s.apply(replace(p,accepted=()))
        s.apply(p); s.depart(); s.step()
        loaded=next(k for k,l in s.state.locations.items() if l[0]=='vehicle')
        with self.assertRaises(ConflictError): s.cancel(loaded)

    def test_blocked_entered_edge_finishes_then_stops(self) -> None:
        s=Session(make_state(42)); s.apply(s.prepare('distance')); s.depart(); s.step()
        entered=next(a for a in s.current.values() if a and a.kind=='drive')
        s.traffic(entered.source,entered.target,'blocked')
        self.assertTrue(s.network.validate_entered_edge(entered))
        while s.running: s.step()
        self.assertEqual(s.state.positions[entered.vehicle],entered.target)
        p=s.prepare('cost'); self.assertTrue(p.report.safe_to_apply,p.report.violations)
        s.apply(p); s.depart()
        while s.running: s.step()
        self.assertTrue(s.audit().valid,s.audit().violations)

    def test_cancel_expire_and_duplicate_terminal_identity(self) -> None:
        s=Session(make_state(100)); keys=list(s.state.orders)
        s.cancel(keys[0]); s.cancel(keys[1],expired=True)
        self.assertEqual(s.state.orders[keys[1]].status,'expired')
        first=s.state.orders[keys[0]]
        with self.assertRaises(ValueError): s.add_order(first.id,first.destination,1,0,2000,'normal')
        p=s.prepare('distance'); self.assertTrue(p.report.complete_all)
        self.assertNotIn(keys[0],p.accepted)

    def test_impossible_loaded_continuation_preserves_state(self) -> None:
        s=Session(make_state(42)); s.apply(s.prepare('distance')); s.depart(); s.step(); s.pause()
        while s.running: s.step()
        key=next(k for k,l in s.state.locations.items() if l[0]=='vehicle'); car=s.state.locations[key][1]; node=s.state.positions[car]
        for edge in list(s.state.graph.get_neighbors(node)): s.traffic(*edge.key,'blocked')
        before=s.state.fingerprint(); proposal=s.prepare('cost')
        self.assertFalse(proposal.report.safe_to_apply)
        with self.assertRaises(ValueError): s.apply(proposal)
        self.assertEqual(before,s.state.fingerprint())

    def test_history_tampering_detected(self) -> None:
        s=Session(make_state(2026)); s.apply(s.prepare('distance')); s.depart()
        while s.running: s.step()
        index=next(i for i,e in enumerate(s.events) if e['kind']=='action' and e['action'].kind=='deliver')
        s.events.insert(index+1,s.events[index].copy())
        self.assertFalse(s.audit().valid)
