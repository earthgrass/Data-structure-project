from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.planner import plan_dispatch
from logiroute.dispatch.validation import validate_plan


class TestDispatchEchelons(unittest.TestCase):
    def test_nonexistent_road_is_invalid_not_an_exception(self) -> None:
        state=make_state(42); plan=plan_dispatch(state)
        routes=list(plan.routes); i=next(i for i,r in enumerate(routes) if any(a.kind=='drive' for a in r.actions))
        actions=list(routes[i].actions); j=next(j for j,a in enumerate(actions) if a.kind=='drive')
        actions[j]=replace(actions[j],target='NONEXISTENT')
        routes[i]=replace(routes[i],actions=tuple(actions))
        self.assertFalse(validate_plan(state,replace(plan,routes=tuple(routes))).valid)

    def test_full_two_level_conservation_and_both_modes(self) -> None:
        state=make_state(42)
        for objective in ('distance','cost'):
            plan=plan_dispatch(state,objective)
            report=validate_plan(state,plan)
            self.assertTrue(report.valid,report.violations)
            self.assertTrue(report.complete_all,plan.deferred)
            delivered=[oid for r in plan.routes for a in r.actions if a.kind=='deliver' for oid in a.ids]
            self.assertEqual(set(delivered),set(state.orders)); self.assertEqual(len(delivered),len(state.orders))
            self.assertTrue(any(a.kind=='unload' for r in plan.routes for a in r.actions))
            self.assertTrue(all(r.end_node==state.vehicles[r.vehicle].base for r in plan.routes))

    def test_loading_before_hub_release_and_duplicate_delivery_rejected(self) -> None:
        state=make_state(1); plan=plan_dispatch(state,'distance')
        routes=list(plan.routes)
        index=next(i for i,r in enumerate(routes) if state.vehicles[r.vehicle].role=='delivery' and r.actions)
        route=routes[index]; actions=list(route.actions)
        j=next(i for i,a in enumerate(actions) if a.kind=='load')
        actions[j]=replace(actions[j],start=0,end=state.config['timing']['loading'])
        routes[index]=replace(route,actions=tuple(actions))
        self.assertFalse(validate_plan(state,replace(plan,routes=tuple(routes))).valid)
        action=next(a for r in plan.routes for a in r.actions if a.kind=='deliver')
        route=plan.routes[index]
        forged=replace(route,actions=route.actions+(action,))
        self.assertFalse(validate_plan(state,replace(plan,routes=(forged,))).valid)

    def test_same_destination_separate_ids_and_capacity(self) -> None:
        state=make_state(100); first=next(iter(state.orders.values()))
        state.orders={f'X{i}':replace(first,id=f'X{i}',demand=Decimal('0.1')) for i in range(4)}
        state.locations={key:('warehouse',state.config['warehouse_ids'][0]) for key in state.orders}
        plan=plan_dispatch(state,'cost')
        self.assertTrue(plan.report.complete_all,plan.deferred)
        self.assertEqual(len([a for r in plan.routes for a in r.actions if a.kind=='deliver']),4)

    def test_unserviceable_critical_is_reported_without_false_success(self) -> None:
        state=make_state(0); key=next(iter(state.orders))
        state.orders[key]=replace(state.orders[key],priority='critical',deadline=0.01)
        plan=plan_dispatch(state,'distance')
        self.assertFalse(plan.report.complete_all)
        self.assertTrue(plan.report.valid,plan.report.violations)
        self.assertIn(key,dict(plan.deferred))

    def test_forged_manifest_and_assignment_rejected(self) -> None:
        state=make_state(2026); plan=plan_dispatch(state,'distance')
        routes=list(plan.routes); r=next(i for i,r in enumerate(routes) if any(a.kind=='load' for a in r.actions))
        actions=list(routes[r].actions); i=next(i for i,a in enumerate(actions) if a.kind=='load')
        actions[i]=replace(actions[i],ids=actions[i].ids+actions[i].ids[:1])
        routes[r]=replace(routes[r],actions=tuple(actions))
        self.assertFalse(validate_plan(state,replace(plan,routes=tuple(routes))).valid)
        self.assertFalse(validate_plan(state,replace(plan,assignments=())).valid)
