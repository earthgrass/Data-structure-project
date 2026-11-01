from __future__ import annotations
from decimal import Decimal
import unittest
from tests.fleet_fixtures import toy
from logiroute.dispatch.models import Job,VehicleSpec
from logiroute.dispatch.algorithms import Paths,build_route


class TestDispatchRules(unittest.TestCase):
    def setUp(self) -> None:
        self.paths=Paths(toy().graph)
        self.car=VehicleSpec('v','c','delivery','W',Decimal(10))

    def job(self,key,node,priority='normal',deadline=100,demand=1):
        return Job(key,node,'deliver',(key,),Decimal(demand),priority,0,deadline,1)

    def test_finish_deadline_not_start_deadline(self) -> None:
        route,failed=build_route(self.paths,self.car,[self.job('x','A',deadline=1)],0)
        self.assertIn('x',failed)
        self.assertFalse(any(a.kind=='deliver' for a in route.actions))

    def test_completion_at_boundary_is_valid(self) -> None:
        route,failed=build_route(self.paths,self.car,[self.job('x','A',deadline=2)],0)
        self.assertFalse(failed)
        self.assertEqual(next(a.end for a in route.actions if a.kind=='deliver'),2)

    def test_urgent_can_follow_normal_to_preserve_window(self) -> None:
        route,failed=build_route(self.paths,self.car,[self.job('u','B','urgent'),self.job('n','A',deadline=2)],0)
        self.assertFalse(failed)
        self.assertEqual([a.ids[0] for a in route.actions if a.kind=='deliver'],['n','u'])

    def test_critical_precedes_lower_level_in_same_batch(self) -> None:
        route,failed=build_route(self.paths,self.car,[self.job('c','B','critical'),self.job('n','A')],0)
        self.assertFalse(failed)
        self.assertEqual([a.ids[0] for a in route.actions if a.kind=='deliver'],['c','n'])

    def test_unserviceable_critical_does_not_block_normal(self) -> None:
        route,failed=build_route(self.paths,self.car,[self.job('c','B','critical',deadline=1),self.job('n','A')],0)
        self.assertIn('c',failed)
        self.assertEqual([a.ids[0] for a in route.actions if a.kind=='deliver'],['n'])

    def test_exact_capacity(self) -> None:
        car=VehicleSpec('v','c','delivery','W',Decimal('0.3'))
        jobs=[self.job('a','A',demand=Decimal('0.1')),self.job('b','A',demand=Decimal('0.2'))]
        route,failed=build_route(self.paths,car,jobs,0)
        self.assertFalse(failed)
        jobs[1]=self.job('b','A',demand=Decimal('0.20000000000000000000001'))
        _,failed=build_route(self.paths,car,jobs,0)
        self.assertTrue(failed)

    def test_actual_edges_return_and_both_modes(self) -> None:
        for mode in ('distance','cost'):
            route,failed=build_route(self.paths,self.car,[self.job('a','A')],0,objective=mode)
            self.assertFalse(failed)
            self.assertEqual((route.actions[-1].target,route.total_distance,route.total_cost),('W',2,2))

    def test_invalid_priority_and_duplicate_jobs_rejected(self) -> None:
        with self.assertRaises(ValueError): self.job('x','A','unknown')
        job=self.job('x','A')
        with self.assertRaises(ValueError): build_route(self.paths,self.car,[job,job],0)
