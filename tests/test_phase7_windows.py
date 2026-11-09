from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.controlled_demo import demo_state
from logiroute.dispatch.models import Parcel
from logiroute.dispatch.session import Session
from logiroute.dispatch.validation import validate_plan


class TestPhase7Windows(unittest.TestCase):
    def test_urgent_can_yield_service_order_but_critical_cannot(self) -> None:
        for priority,complete in [('urgent',True),('critical',False)]:
            state=demo_state();key=next(iter(state.orders));old=state.orders[key]
            state.orders[key]=replace(old,priority=priority)
            state.orders['NORMAL']=Parcel('NORMAL',old.destination,Decimal('0.1'),0,13)
            state.locations['NORMAL']=state.locations[key]
            p=Session(state).prepare('distance')
            self.assertTrue(p.report.valid);self.assertEqual(p.report.complete_all,complete)
            ids=[oid for r in p.routes for a in r.actions if a.kind=='deliver' for oid in a.ids]
            if complete:self.assertEqual(ids,['NORMAL',key])
            else:self.assertEqual(ids,[key]);self.assertIn('NORMAL',dict(p.deferred))

    def test_congestion_invalidates_exact_deadline_and_keeps_partial_honest(self) -> None:
        state=demo_state();key=next(iter(state.orders));state.orders[key]=replace(state.orders[key],deadline=13)
        session=Session(state);old=session.prepare('distance');self.assertTrue(old.report.complete_all)
        session.traffic('H','A','congested')
        self.assertFalse(validate_plan(session.state,old).valid)
        new=session.prepare('distance');self.assertTrue(new.report.valid);self.assertFalse(new.report.complete_all)
        self.assertEqual(dict(new.deferred)[key],'completion_deadline')
