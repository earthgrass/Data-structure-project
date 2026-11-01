from __future__ import annotations
from dataclasses import replace
import json
import os
import subprocess
import sys
import unittest
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scenario_generator.road_validator import validate_road_network


class TestLocalRoads(unittest.TestCase):
    def config(self) -> GeneratorConfig:
        return GeneratorConfig(min_nodes=35,max_nodes=35,topology='local',nearest_neighbor_count=3)

    def test_five_seeds_local_sparse_bidirectional_and_connected(self) -> None:
        for seed in (0,1,42,100,2026):
            with self.subTest(seed=seed):
                c=self.config(); g=sample_logistics_graph(c,RandomSource(seed)); report=validate_road_network(g,c)
                self.assertTrue(report.valid,report.violations)
                self.assertTrue(report.reachable_and_returnable and report.skeleton_complete)
                self.assertLess(report.physical_road_count,90)
                self.assertEqual(report.bidirectional_road_count,int(report.physical_road_count*.95+.5))
                for start in g.nodes:
                    for target in g.nodes:
                        if start.id==target.id: continue
                        d=(start.x-target.x)**2+(start.y-target.y)**2
                        closer=sum(1 for o in g.nodes if o.id!=start.id and ((start.x-o.x)**2+(start.y-o.y)**2<d or ((start.x-o.x)**2+(start.y-o.y)**2==d and o.id<target.id)))
                        if closer<3: self.assertTrue(g.has_edge(start.id,target.id) or g.has_edge(target.id,start.id))
                for e in g.edges:
                    if e.metadata['skeleton']: continue
                    def rank(a: str,b: str) -> int:
                        n=g.get_node(a); target=g.get_node(b); distance=(n.x-target.x)**2+(n.y-target.y)**2
                        return sum(1 for other in g.nodes if other.id!=a and ((n.x-other.x)**2+(n.y-other.y)**2<distance or ((n.x-other.x)**2+(n.y-other.y)**2==distance and other.id<b)))
                    self.assertTrue(rank(e.source_id,e.target_id)<3 or rank(e.target_id,e.source_id)<3)

    def test_budget_conflict_refused_not_trimmed(self) -> None:
        c=replace(self.config(),max_edges=70)
        with self.assertRaises(ValueError): sample_logistics_graph(c,RandomSource(42))

    def test_invalid_k_and_mode(self) -> None:
        for k in (0,True,35,1.5,None):
            with self.assertRaises(ValueError): replace(self.config(),nearest_neighbor_count=k)
        with self.assertRaises(ValueError): replace(self.config(),topology='unknown')
        with self.assertRaises(ValueError): GeneratorConfig(nearest_neighbor_count=3)

    def test_explicit_count_conflict_and_legacy_default(self) -> None:
        c=self.config()
        with self.assertRaises(ValueError): sample_logistics_graph(replace(c,physical_road_count=100),RandomSource(42))
        old=sample_logistics_graph(GeneratorConfig(min_nodes=35,max_nodes=35),RandomSource(42))
        self.assertEqual(len(old.edges),220)

    def test_prim_ties_are_explicit_and_clusters_are_bridged(self) -> None:
        from logiroute.algorithms.spatial_roads import local_road_pairs
        self.assertEqual(local_road_pairs([('W',0,0),('b',1,0),('a',0,1),('z',1,1)],1),[(0,2),(0,1),(2,3)])
        pairs=local_road_pairs([('a',0,0),('b',1,0),('c',100,0),('d',101,0)],1)
        self.assertEqual(pairs[:3],[(0,1),(1,2),(2,3)])

    def test_validator_rejects_long_additional_road(self) -> None:
        from logiroute.core import Edge
        c=self.config(); g=sample_logistics_graph(c,RandomSource(42))
        # Replace one nonskeleton physical road by a distant pair; preserve count.
        original=next(e for e in g.edges if not e.metadata['skeleton'] and e.metadata['bidirectional'])
        g.remove_edge(original.source_id,original.target_id); g.remove_edge(original.target_id,original.source_id)
        pair=None; far=-1.0
        for a in g.nodes:
            for b in g.nodes:
                d=(a.x-b.x)**2+(a.y-b.y)**2
                if a.id!=b.id and not g.has_edge(a.id,b.id) and not g.has_edge(b.id,a.id) and d>far: pair=(a.id,b.id); far=d
        for a,b in (pair,pair[::-1]):
            g.add_edge(Edge(a,b,1,1,1,metadata={'road_id':'forged','edge_id':a+'>'+b,'skeleton':False,'bidirectional':True}))
        report=validate_road_network(g,c)
        self.assertFalse(report.valid)
        self.assertTrue(any('nonlocal' in v for v in report.violations))

    def test_cross_process_full_graph_fingerprint(self) -> None:
        code="""
import hashlib,json
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
rows=[]
for seed in (0,1,42,100,2026):
 g=sample_logistics_graph(GeneratorConfig(min_nodes=35,max_nodes=35,topology='local',nearest_neighbor_count=3),RandomSource(seed))
 rows.append([[(n.id,n.x,n.y) for n in g.nodes],[(e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.metadata) for e in g.edges]])
print(hashlib.sha256(json.dumps(rows).encode()).hexdigest())
"""
        outputs=[]
        for hash_seed in ('1','2'):
            r=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,env={**os.environ,'PYTHONHASHSEED':hash_seed},timeout=180)
            self.assertEqual(r.returncode,0,r.stderr); outputs.append(r.stdout)
        self.assertEqual(outputs[0],outputs[1])
