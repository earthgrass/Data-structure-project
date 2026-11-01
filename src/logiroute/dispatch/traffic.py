"""Versioned simulated traffic; edge factors always apply to original weights."""
from __future__ import annotations
from copy import deepcopy
import math
from typing import Any
from logiroute.core import Node,Edge
from logiroute.core.enums import TrafficStatus
from logiroute.graph import LogisticsGraph
from logiroute.dispatch.models import Action


def copy_graph(graph: LogisticsGraph) -> LogisticsGraph:
    """Independent adjacency and scalar objects. Time/Space O(V+E)."""
    result=LogisticsGraph()
    for n in graph.nodes: result.add_node(Node(n.id,n.name,n.node_type,n.x,n.y,deepcopy(n.metadata)))
    for e in graph.edges: result.add_edge(Edge(e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.traffic_status,deepcopy(e.metadata)))
    return result


class Network:
    """No cross-version path cache or mutable snapshot aliases. Storage O(T*(V+E))."""
    def __init__(self,graph: LogisticsGraph,config: dict[str,Any]) -> None:
        factors=config['factors']
        if set(factors)!={s.value for s in TrafficStatus} or factors['blocked'] is not None: raise ValueError('invalid traffic states')
        for state,factor in factors.items():
            if state!='blocked' and (isinstance(factor,bool) or not math.isfinite(float(factor)) or float(factor)<1): raise ValueError('invalid traffic factor')
        delay=float(config['cost_per_delay'])
        if not math.isfinite(delay) or delay<0: raise ValueError('invalid delay cost')
        self._base=copy_graph(graph); self._config=deepcopy(config); self._states={e.key:'clear' for e in graph.edges}
        self.version=0; self._history={0:self._build(self._states)}

    def _build(self,states: dict[tuple[str,str],str]) -> LogisticsGraph:
        graph=copy_graph(self._base)
        for e in graph.edges:
            status=states[e.key]; factor=self._config['factors'][status]
            if factor is not None:
                time=e.travel_time*float(factor); cost=e.cost+float(self._config['cost_per_delay'])*(time-e.travel_time)
                graph.remove_edge(*e.key); graph.add_edge(Edge(*e.key,e.distance,time,cost,TrafficStatus(status),deepcopy(e.metadata)))
            else: e.traffic_status=TrafficStatus.BLOCKED
        return graph

    def update(self,source: str,target: str,status: str) -> int:
        """Validate/build first, commit last. Time/Space O(V+E)."""
        if (source,target) not in self._states or status not in self._config['factors']: raise ValueError('unknown road/traffic status')
        trial={**self._states,(source,target):status}; snapshot=self._build(trial)
        self.version+=1; self._states=trial; self._history[self.version]=snapshot
        return self.version

    def snapshot(self,version: int | None = None) -> LogisticsGraph:
        """Caller-owned snapshot. Time/Space O(V+E)."""
        return copy_graph(self._history[self.version if version is None else version])

    def validate_entered_edge(self,action: Action) -> bool:
        """Frozen entered action still uses its original version. Time O(1)."""
        if action.kind!='drive' or action.traffic_version not in self._history: return False
        graph=self._history[action.traffic_version]
        if not graph.has_edge(action.source,action.target): return False
        e=graph.get_edge(action.source,action.target)
        return e.traffic_status is not TrafficStatus.BLOCKED and (action.distance,action.travel_time,action.cost)==(e.distance,e.travel_time,e.cost) and action.end==action.start+e.travel_time
