from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import json
import os
import subprocess
import sys
import unittest

from logiroute.core import Edge,Node,NodeType
from logiroute.dispatch.algorithms import Paths,build_route
from logiroute.dispatch.models import Job,Parcel,VehicleSpec
from logiroute.dispatch.planner import plan_dispatch
from logiroute.dispatch.scenario import State
from logiroute.graph import LogisticsGraph


def explanation_state(orders: list[Parcel],capacity: str = '10') -> State:
    graph=LogisticsGraph()
    for key,kind in (('W',NodeType.WAREHOUSE),('H',NodeType.TRANSFER),('A',NodeType.CUSTOMER),('B',NodeType.CUSTOMER)):
        graph.add_node(Node(key,key,kind,0,0))
    for source in graph.node_ids:
        for target in graph.node_ids:
            if source!=target:graph.add_edge(Edge(source,target,1,1,2))
    cars={'TRUNK':VehicleSpec('TRUNK','CT','trunk','W',Decimal(capacity)),
          'LOCAL':VehicleSpec('LOCAL','CL','delivery','H',Decimal(capacity))}
    return State(graph,{'warehouse_ids':['W'],'hub_ids':['H'],'timing':{'loading':0,'unloading':0,'service':1}},
                 {o.id:o for o in orders},{o.id:('warehouse','W') for o in orders},cars,
                 {k:v.base for k,v in cars.items()},0)


class TestDispatchExplanations(unittest.TestCase):
    def test_exact_capacity_evidence_and_known_manifest(self) -> None:
        state=explanation_state([Parcel('OLD','A',Decimal('0.1'),0,100,hub='H'),
                                 Parcel('NEW','B',Decimal('0.20000000000000000000000000001'),0,100)],'0.3')
        state.protected.add('OLD')
        plan=plan_dispatch(state)
        detail=next(x for x in plan.to_dict()['explanations'] if x['order_id']=='NEW')
        attempt=detail['attempts'][0]
        self.assertEqual(detail['reason'],'capacity')
        self.assertEqual(attempt['vehicle'],'TRUNK')
        self.assertEqual(attempt['order_ids'],['NEW','OLD'])
        self.assertEqual(attempt['load'],'0.30000000000000000000000000001')
        self.assertEqual(attempt['capacity'],'0.3')
        self.assertEqual(attempt['stage'],'load')
        self.assertEqual(plan.accepted,('OLD',))

    def test_new_critical_order_can_be_rejected_because_existing_order_would_miss_deadline(self) -> None:
        state=explanation_state([Parcel('OLD','A',1,0,3,hub='H'),Parcel('NEW','B',1,0,100,'critical')])
        state.protected.add('OLD')
        for objective in ('distance','cost'):
            plan=plan_dispatch(state,objective)
            detail=next(x for x in plan.to_dict()['explanations'] if x['order_id']=='NEW')
            attempt=detail['attempts'][0]
            self.assertEqual(detail['reason'],'completion_deadline')
            self.assertEqual(attempt['order_ids'],['OLD'])
            self.assertEqual(attempt['vehicle'],'LOCAL')
            self.assertEqual(attempt['stage'],'deliver')
            self.assertEqual((attempt['service_end'],attempt['deadline']),(5,3))
            self.assertIn('OLD',detail['summary'])
            self.assertEqual(plan.accepted,('OLD',))
            self.assertTrue(plan.report.safe_to_apply)

    def test_unreachable_hub_evidence_names_real_path_endpoints(self) -> None:
        state=explanation_state([Parcel('NEW','A',1,0,100)])
        for edge in list(state.graph.edges):
            if edge.target_id=='A':state.graph.remove_edge(*edge.key)
        detail=plan_dispatch(state).to_dict()['explanations'][0]
        self.assertEqual(detail['reason'],'unreachable')
        self.assertEqual(detail['attempts'][0]['source'],'H')
        self.assertEqual(detail['attempts'][0]['target'],'A')
        self.assertEqual(detail['attempts'][0]['order_ids'],['NEW'])
        self.assertEqual(detail['scope'],'heuristic_candidate')

    def test_deadline_at_exact_boundary_is_not_reported_as_failed(self) -> None:
        state=explanation_state([Parcel('EXACT','A',1,0,3)])
        plan=plan_dispatch(state)
        self.assertEqual(plan.to_dict()['explanations'],[])
        self.assertEqual(plan.accepted,('EXACT',))
        self.assertTrue(plan.report.complete_all)

    def test_diagnostics_do_not_change_route_or_old_failure_contract(self) -> None:
        state=explanation_state([])
        jobs=[Job('OLD','A','deliver',('OLD',),Decimal(1),'normal',0,2,1),
              Job('NEW','B','deliver',('NEW',),Decimal(1),'critical',0,100,1)]
        car=state.vehicles['LOCAL'];old=build_route(Paths(state.graph),car,jobs,0)
        details={}
        measured=build_route(Paths(state.graph),car,jobs,0,failure_details=details)
        self.assertEqual(old,measured)
        self.assertEqual(details['OLD'].order_ids,('OLD',))
        self.assertEqual(details['OLD'].service_end,4)

    def test_fresh_runs_are_deterministic_json_and_do_not_mutate_input(self) -> None:
        state=explanation_state([Parcel('N','A',1,0,0.1)])
        before=state.fingerprint()
        first=plan_dispatch(state).to_dict();second=plan_dispatch(state).to_dict()
        self.assertEqual(first,second)
        self.assertEqual(state.fingerprint(),before)
        self.assertEqual(json.loads(json.dumps(first,allow_nan=False)),first)
        self.assertEqual(len(first['explanations']),len(first['deferred']))
        self.assertTrue(first['explanations'][0]['suggestions'])

    def test_protected_continuation_preserves_actual_blocker(self) -> None:
        state=explanation_state([Parcel('OLD','A',1,0,0.1,hub='H'),Parcel('NEW','B',1,0,100)])
        state.protected.add('OLD')
        plan=plan_dispatch(state)
        self.assertFalse(plan.report.safe_to_apply)
        for item in plan.to_dict()['explanations']:
            self.assertTrue(item['reason'].startswith('protected_continuation:'))
            self.assertEqual(item['attempts'][0]['order_ids'],['OLD'])
            self.assertEqual(item['attempts'][0]['stage'],'unload')

    def test_same_destination_ids_and_cancelled_terminal_are_not_merged(self) -> None:
        state=explanation_state([Parcel('ONE','A',1,0,3),Parcel('TWO','A',1,0,3),
                                 Parcel('CANCELLED','A',1,0,3,status='cancelled')])
        plan=plan_dispatch(state)
        self.assertEqual(plan.accepted,('ONE',))
        self.assertEqual([x['order_id'] for x in plan.to_dict()['explanations']],['TWO'])
        self.assertNotIn('CANCELLED',dict(plan.deferred))

    def test_build_route_failure_details_are_cleared_between_calls(self) -> None:
        state=explanation_state([]);car=state.vehicles['LOCAL'];details={}
        job=Job('LATE','A','deliver',('LATE',),Decimal(1),'normal',0,0.1,1)
        build_route(Paths(state.graph),car,[job],0,failure_details=details)
        self.assertIn('LATE',details)
        build_route(Paths(state.graph),car,[replace(job,deadline=100)],0,failure_details=details)
        self.assertEqual(details,{})

    def test_unload_group_only_names_orders_that_miss_their_own_deadline(self) -> None:
        state=explanation_state([Parcel('EARLY','A',1,0,0.1,hub='H'),Parcel('MID','A',1,0,0.5,hub='H'),Parcel('LATER','B',1,0,100,hub='H')])
        state.protected.update(state.orders)
        for explanation in plan_dispatch(state).to_dict()['explanations']:
            item=explanation['attempts'][0]
            self.assertEqual(item['stage'],'unload')
            self.assertEqual(item['order_ids'],['EARLY','MID'])
            self.assertEqual(item['deadline'],0.1)
            self.assertEqual(item['service_end'],1)
            self.assertIn('最早截止 0.1',explanation['summary'])
            self.assertIn('超过各自截止',explanation['summary'])

    def test_current_vehicle_return_failure_keeps_true_endpoints(self) -> None:
        state=explanation_state([Parcel('CARGO','A',1,0,100,hub='H',status='in_transit')])
        state.locations['CARGO']=('vehicle','LOCAL');state.positions['LOCAL']='A';state.protected.add('CARGO')
        for edge in list(state.graph.edges):
            if edge.source_id=='A':state.graph.remove_edge(*edge.key)
        detail=plan_dispatch(state).to_dict()['explanations'][0]['attempts'][0]
        self.assertEqual(detail['code'],'return_unreachable')
        self.assertEqual(detail['vehicle'],'LOCAL')
        self.assertEqual((detail['source'],detail['target']),('A','H'))

    def test_refused_order_evidence_matches_across_hash_seed_processes(self) -> None:
        code='''
import hashlib,json
from tests.test_dispatch_explanations import explanation_state
from logiroute.dispatch.models import Parcel
from logiroute.dispatch.planner import plan_dispatch
s=explanation_state([Parcel('OLD','A',1,0,3,hub='H'),Parcel('NEW','B',1,0,100,'critical')])
s.protected.add('OLD')
records=[plan_dispatch(s,mode).to_dict() for mode in ('distance','cost')]
assert all(r['explanations'][0]['attempts'][0]['order_ids']==['OLD'] for r in records)
print(hashlib.sha256(json.dumps(records,separators=(',',':'),allow_nan=False).encode()).hexdigest())
'''
        fingerprints=[]
        for seed in ('1','2'):
            env={**os.environ,'PYTHONHASHSEED':seed,'PYTHONPATH':'src','PYTHONDONTWRITEBYTECODE':'1'}
            result=subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);fingerprints.append(result.stdout.strip())
        self.assertEqual(fingerprints[0],fingerprints[1]);self.assertEqual(len(fingerprints[0]),64)


if __name__=='__main__':unittest.main()
