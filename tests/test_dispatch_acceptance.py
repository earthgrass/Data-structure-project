from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.scenario import load_config,make_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.planner import plan_dispatch
from logiroute.dispatch.validation import validate_plan


class TestDispatchAcceptance(unittest.TestCase):
    def test_invalid_dynamic_time_and_automatic_seed_rejected(self) -> None:
        s=Session(make_state(42)); dest=next(iter(s.state.orders.values())).destination
        for earliest in (-1,True):
            with self.assertRaises(ValueError): s.add_order('bad',dest,1,earliest,2000,'normal')
        for seed in (True,None,1.5):
            with self.assertRaises(ValueError): s.automatic(1,seed)

    def test_unknown_order_in_history_rejected(self) -> None:
        s=Session(make_state(42)); s.apply(s.prepare('distance')); s.depart(); s.step()
        event=s.events[-1]; s.events[-1]={**event,'action':replace(event['action'],ids=('unknown',))}
        self.assertFalse(s.audit().valid)
        s.events[-1]=event
        for kind,start,end in (('unknown',s.state.now,s.state.now),('wait',float('nan'),float('nan'))):
            s.events.append({'kind':'action','time':end,'action':replace(event['action'],kind=kind,start=start,end=end,ids=())})
            self.assertFalse(s.audit().valid)
            s.events.pop()

    def test_zero_duration_hub_release_causal_ties(self) -> None:
        c=load_config()
        for field in ('loading','unloading','service'): c['timing'][field]=0
        s=Session(make_state(42,c)); s.apply(s.prepare('distance')); s.depart()
        while s.running: s.step()
        self.assertTrue(s.audit().complete_all,s.audit().violations)

    def test_alias_order_identity_is_rejected(self) -> None:
        s=make_state(1); keys=list(s.orders); s.orders[keys[1]]=replace(s.orders[keys[0]],id=keys[0])
        plan=plan_dispatch(s)
        self.assertFalse(validate_plan(s,plan).valid)

    def test_fractional_time_json_and_references_validated(self) -> None:
        c=load_config(); c['timing']['loading']=Decimal('0.1')
        self.assertTrue(plan_dispatch(make_state(42,c)).report.complete_all)
        c['warehouse_ids']=['missing']
        with self.assertRaises(ValueError): make_state(42,c)

    def test_bad_quantity_input_is_atomic_at_core_boundary(self) -> None:
        s=Session(make_state(0)); first=next(iter(s.state.orders.values())); before=s.state.fingerprint()
        with self.assertRaises(ValueError): s.add_order('bad',first.destination,Decimal('NaN'),0,2000,'urgent')
        self.assertEqual(before,s.state.fingerprint())
