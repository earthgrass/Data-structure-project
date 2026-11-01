from __future__ import annotations
import unittest
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.traffic import Network
from logiroute.dispatch.algorithms import Paths
from logiroute.dispatch.models import Action


class TestDispatchTraffic(unittest.TestCase):
    def test_entered_edge_freezes_version_and_blocked_source_unreachable(self) -> None:
        state=make_state(42); network=Network(state.graph,state.config['traffic']); edge=next(iter(state.graph.edges))
        entered=Action('car','drive',0,edge.travel_time,*edge.key,distance=edge.distance,travel_time=edge.travel_time,cost=edge.cost)
        for outgoing in state.graph.get_neighbors(edge.source_id): network.update(*outgoing.key,'blocked')
        self.assertTrue(network.validate_entered_edge(entered))
        for metric in ('distance','cost'):
            self.assertFalse(Paths(network.snapshot(),network.version).get(*edge.key,metric).reachable)

    def test_direction_factor_and_old_snapshot(self) -> None:
        state=make_state(42); network=Network(state.graph,state.config['traffic'])
        old=network.snapshot(); edge=next(iter(old.edges))
        network.update(edge.source_id,edge.target_id,'congested')
        changed=network.snapshot().get_edge(edge.source_id,edge.target_id)
        self.assertEqual(changed.travel_time,edge.travel_time*2)
        self.assertEqual(changed.cost,edge.cost+float(state.config['traffic']['cost_per_delay'])*edge.travel_time)
        self.assertEqual(old.get_edge(edge.source_id,edge.target_id).travel_time,edge.travel_time)
        network.update(edge.source_id,edge.target_id,'clear')
        self.assertEqual(network.snapshot().get_edge(edge.source_id,edge.target_id).travel_time,edge.travel_time)
        self.assertEqual(network.version,2)

    def test_blocked_excluded_for_every_metric(self) -> None:
        state=make_state(1); network=Network(state.graph,state.config['traffic']); edge=next(iter(state.graph.edges))
        network.update(edge.source_id,edge.target_id,'blocked')
        for metric in ('distance','cost','travel_time'):
            paths=Paths(network.snapshot(),network.version)
            self.assertFalse(any(e.key==edge.key for e in paths.graph.edges))
            path=paths.get(edge.source_id,edge.target_id,metric)
            self.assertNotIn(edge.key,tuple(zip(path.path,path.path[1:])))

    def test_invalid_update_atomic_and_snapshots_isolated(self) -> None:
        state=make_state(0); network=Network(state.graph,state.config['traffic']); edge=next(iter(state.graph.edges))
        with self.assertRaises(ValueError): network.update(edge.source_id,edge.target_id,'unknown')
        with self.assertRaises(ValueError): network.update(edge.source_id,'missing','blocked')
        self.assertEqual(network.version,0)
        snapshot=network.snapshot(); snapshot.remove_edge(*edge.key)
        self.assertEqual(network.snapshot().get_edge(*edge.key).key,edge.key)
