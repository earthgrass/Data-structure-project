"""Handwritten feasible insertion over original Dijkstra; completion deadlines."""
from __future__ import annotations
import math
from logiroute.algorithms.dijkstra import shortest_path,PathResult
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core import Node,Edge
from logiroute.core.enums import TrafficStatus
from logiroute.core.quantities import exact_sum
from logiroute.graph import LogisticsGraph
from logiroute.dispatch.models import Job,VehicleSpec,Action,Route,RANK,FailureEvidence
from logiroute.dispatch.deadlines import lateness_score


class RouteUnavailableError(ValueError):
    """No safe return path for the current physical vehicle position."""

    def __init__(self,message: str,detail: FailureEvidence | None = None) -> None:
        super().__init__(message)
        self.detail=detail


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
              objective: str,batch: int,details: list[FailureEvidence] | None = None,
              soft_lower: bool = False) -> tuple[Route | None,str]:
    def reject(code: str,stage: str,*,ids: tuple[str,...] = (),source: str | None = None,
               target: str | None = None,service_end: float | None = None,
               deadline: float | None = None) -> tuple[None,str]:
        if details is not None:
            details.append(FailureEvidence(code,stage,vehicle=car.id,order_ids=ids,
                           load=load if code=='capacity' else None,capacity=car.capacity if code=='capacity' else None,
                           service_end=service_end,deadline=deadline,source=source,target=target))
        return None,code
    load=exact_sum(j.demand for j in jobs)
    if load>car.capacity:return reject('capacity','load',ids=tuple(oid for j in jobs for oid in j.ids))
    lower=False
    for job in jobs:
        if job.priority=='critical' and lower:return reject('critical_precedence','priority',ids=job.ids)
        if job.priority!='critical': lower=True
    actions=[]; now=ready; current=start
    for job in jobs+[None]:
        target=car.base if job is None else job.node
        path=paths.get(current,target,objective)
        if not path.reachable:return reject('return_unreachable' if job is None else 'unreachable',
                                           'return' if job is None else 'travel',ids=() if job is None else job.ids,source=current,target=target)
        for source,destination in zip(path.path,path.path[1:]):
            edge=paths.graph.get_edge(source,destination)
            end=now+edge.travel_time
            if not math.isfinite(end):return reject('nonfinite_time','travel',source=source,target=destination)
            actions.append(Action(car.id,'drive',now,end,source,destination,
                                  distance=edge.distance,travel_time=edge.travel_time,cost=edge.cost,
                                  traffic_version=paths.version,batch=batch)); now=end
        current=target
        if job is not None:
            begin=max(now,job.earliest)
            if begin>now: actions.append(Action(car.id,'wait',now,begin,current,current,batch=batch))
            end=begin+job.duration
            if not math.isfinite(end):return reject('nonfinite_time',job.kind,ids=job.ids)
            if end>job.deadline and job.hard_deadline and (not soft_lower or job.priority=='critical'):
                return reject('completion_deadline',job.kind,ids=job.ids,service_end=end,deadline=job.deadline,source=current,target=current)
            actions.append(Action(car.id,job.kind,begin,end,current,current,job.ids,
                                  traffic_version=paths.version,batch=batch)); now=end
    actions.append(Action(car.id,'finish',now,now,current,current,batch=batch))
    route=Route(car.id,start,car.base,tuple(actions))
    if not math.isfinite(route.total_cost) or not math.isfinite(route.total_distance):return reject('nonfinite_metrics','route')
    return route,''


def build_route(paths: Paths,car: VehicleSpec,jobs: list[Job],ready: float,*,
                start_node: str | None = None,objective: str = 'distance',batch: int = 0,
                failure_details: dict[str,FailureEvidence] | None = None,soft_lower: bool = False
                ) -> tuple[Route,dict[str,str]]:
    """All-job/all-position feasible insertion. Time O(M⁴D + cache misses), Space O(MD).

    Critical precedence is a feasibility rule. Urgent admission outranks normal,
    but normal may be served earlier when the route improves higher-tier deadlines.
    Pressure mode compares urgent then normal late counts and minutes before the
    route main objective. Historical strict mode keeps every deadline hard.
    Failed critical jobs never block feasible lower-level jobs. Return is real.
    Optional evidence retains only the last rejected insertion for each failed job;
    it does not participate in candidate comparison. Extra space O(M²) for IDs.
    """
    if objective not in ('distance','cost'): raise ValueError('invalid objective')
    if len({j.id for j in jobs})!=len(jobs): raise ValueError('duplicate job id')
    if failure_details is not None:failure_details.clear()
    by_id={j.id:j for j in jobs}; pending=ordered_strings(by_id)
    selected=[]; start=car.base if start_node is None else start_node
    initial=[] if failure_details is not None else None
    old,reason=_evaluate(paths,car,[],ready,start,objective,batch,initial,soft_lower)
    if old is None:raise RouteUnavailableError('vehicle cannot return to base: '+reason,initial[0] if initial else None)
    failed={}
    while pending:
        best=None; best_route=None; best_jobs=None; failed={}; recorded={}
        old_main=old.total_distance if objective=='distance' else old.total_cost
        for key in pending:
            job=by_id[key]
            for index in range(len(selected)+1):
                trial=selected[:index]+[job]+selected[index:]
                evidence=[] if failure_details is not None else None
                route,error=_evaluate(paths,car,trial,ready,start,objective,batch,evidence,soft_lower)
                if error:
                    failed[key]=error
                    if evidence:recorded[key]=evidence[0]
                    continue
                main=route.total_distance if objective=='distance' else route.total_cost
                late=lateness_score(route,trial) if soft_lower else ()
                expedited_end=next((a.end for a in route.actions if a.kind=='deliver' and a.ids==job.ids),0.0) if job.priority=='critical' and not job.hard_deadline else 0.0
                candidate=(RANK[job.priority],job.deadline,expedited_end,*late,main-old_main,job.id,index)
                better=best is None
                if best is not None:
                    for field in range(len(candidate)):
                        if candidate[field]!=best[field]: better=candidate[field]<best[field]; break
                if better: best=candidate; best_route=route; best_jobs=trial
        if best is None: break
        old=best_route; selected=best_jobs; pending.remove(best[-2])
    if failure_details is not None:
        for key in pending:
            if key in recorded:failure_details[key]=recorded[key]
    return old,{key:failed.get(key,'heuristic_incomplete') for key in pending}
