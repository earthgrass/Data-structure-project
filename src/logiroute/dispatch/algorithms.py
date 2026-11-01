"""Handwritten feasible insertion over original Dijkstra; completion deadlines."""
from __future__ import annotations
import math
from logiroute.algorithms.dijkstra import shortest_path,PathResult
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core import Node,Edge
from logiroute.core.enums import TrafficStatus
from logiroute.core.quantities import exact_sum
from logiroute.graph import LogisticsGraph
from logiroute.dispatch.models import Job,VehicleSpec,Action,Route,RANK


class RouteUnavailableError(ValueError):
    """No safe return path for the current physical vehicle position."""


class Paths:
    """One planning-snapshot cache. No alternate shortest-path implementation.

    Graph copy O(V+E); each uncached query uses existing Dijkstra; cache O(U²V).
    Blocked edges are omitted for ALL metrics, without infinite Edge weights.
    """
    def __init__(self,graph: LogisticsGraph,version: int = 0) -> None:
        self.graph=LogisticsGraph(); self.version=version; self._cache={}; self.calls=0
        for n in graph.nodes: self.graph.add_node(Node(n.id,n.name,n.node_type,n.x,n.y))
        for e in graph.edges:
            if e.traffic_status is not TrafficStatus.BLOCKED:
                self.graph.add_edge(Edge(e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.traffic_status))

    def get(self,source: str,target: str,metric: str) -> PathResult:
        """Cached lookup O(1) average; miss uses original hand-heap Dijkstra."""
        key=(source,target,metric)
        if key not in self._cache:
            self._cache[key]=shortest_path(self.graph,source,target,metric); self.calls+=1
        return self._cache[key]


def _evaluate(paths: Paths,car: VehicleSpec,jobs: list[Job],ready: float,start: str,
              objective: str,batch: int) -> tuple[Route | None,str]:
    if exact_sum(j.demand for j in jobs)>car.capacity: return None,'capacity'
    lower=False
    for job in jobs:
        if job.priority=='critical' and lower: return None,'critical_precedence'
        if job.priority!='critical': lower=True
    actions=[]; now=ready; current=start
    for job in jobs+[None]:
        target=car.base if job is None else job.node
        path=paths.get(current,target,objective)
        if not path.reachable: return None,'return_unreachable' if job is None else 'unreachable'
        for source,destination in zip(path.path,path.path[1:]):
            edge=paths.graph.get_edge(source,destination)
            end=now+edge.travel_time
            if not math.isfinite(end): return None,'nonfinite_time'
            actions.append(Action(car.id,'drive',now,end,source,destination,
                                  distance=edge.distance,travel_time=edge.travel_time,cost=edge.cost,
                                  traffic_version=paths.version,batch=batch)); now=end
        current=target
        if job is not None:
            begin=max(now,job.earliest)
            if begin>now: actions.append(Action(car.id,'wait',now,begin,current,current,batch=batch))
            end=begin+job.duration
            if not math.isfinite(end): return None,'nonfinite_time'
            if end>job.deadline: return None,'completion_deadline'
            actions.append(Action(car.id,job.kind,begin,end,current,current,job.ids,
                                  traffic_version=paths.version,batch=batch)); now=end
    actions.append(Action(car.id,'finish',now,now,current,current,batch=batch))
    route=Route(car.id,start,car.base,tuple(actions))
    if not math.isfinite(route.total_cost) or not math.isfinite(route.total_distance): return None,'nonfinite_metrics'
    return route,''


def build_route(paths: Paths,car: VehicleSpec,jobs: list[Job],ready: float,*,
                start_node: str | None = None,objective: str = 'distance',batch: int = 0
                ) -> tuple[Route,dict[str,str]]:
    """All-job/all-position feasible insertion. Time O(M⁴D + cache misses), Space O(MD).

    Critical precedence is a feasibility rule. Urgent admission outranks normal,
    but normal may be served earlier to preserve both completion windows.
    Failed critical jobs never block feasible lower-level jobs. Return is real.
    """
    if objective not in ('distance','cost'): raise ValueError('invalid objective')
    if len({j.id for j in jobs})!=len(jobs): raise ValueError('duplicate job id')
    by_id={j.id:j for j in jobs}; pending=ordered_strings(by_id)
    selected=[]; start=car.base if start_node is None else start_node
    old,reason=_evaluate(paths,car,[],ready,start,objective,batch)
    if old is None: raise RouteUnavailableError('vehicle cannot return to base: '+reason)
    failed={}
    while pending:
        best=None; best_route=None; best_jobs=None; failed={}
        old_main=old.total_distance if objective=='distance' else old.total_cost
        for key in pending:
            job=by_id[key]
            for index in range(len(selected)+1):
                trial=selected[:index]+[job]+selected[index:]
                route,error=_evaluate(paths,car,trial,ready,start,objective,batch)
                if error: failed[key]=error; continue
                main=route.total_distance if objective=='distance' else route.total_cost
                candidate=(RANK[job.priority],job.deadline,main-old_main,job.id,index)
                better=best is None
                if best is not None:
                    for field in range(5):
                        if candidate[field]!=best[field]: better=candidate[field]<best[field]; break
                if better: best=candidate; best_route=route; best_jobs=trial
        if best is None: break
        old=best_route; selected=best_jobs; pending.remove(best[3])
    return old,{key:failed.get(key,'heuristic_incomplete') for key in pending}
