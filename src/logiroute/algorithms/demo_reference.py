"""Independent tiny reference: enumerate simple outbound and return paths, no Dijkstra."""
from __future__ import annotations
from typing import Any
from logiroute.graph import LogisticsGraph


def enumerate_demo(graph: LogisticsGraph,warehouse: str,hub: str,customer: str) -> dict[str,Any]:
    """Tiny one-order/one-hub scope only. Time exponential in V, space O(V+output).

    Enumerate each simple directed hub/customer path in both directions; combine
    all pairs and the fixed warehouse/hub shuttle. Positive weights mean cycles
    cannot improve either objective. No general multi-order optimality claim.
    """
    def paths(start: str,end: str) -> list[dict[str,Any]]:
        result=[]
        def visit(node: str,seen: list[str],d: float,t: float,c: float) -> None:
            if node==end:
                result.append({'nodes':seen,'distance':d,'travel_time':t,'cost':c});return
            for edge in graph.edges:
                if edge.source_id==node and edge.target_id not in seen:
                    visit(edge.target_id,seen+[edge.target_id],d+edge.distance,t+edge.travel_time,c+edge.cost)
        visit(start,[start],0,0,0);return result
    out=paths(hub,customer);back=paths(customer,hub)
    shuttle=[graph.get_edge(warehouse,hub),graph.get_edge(hub,warehouse)]
    rows=[{'out':a['nodes'],'back':b['nodes'],**{m:a[m]+b[m]+sum(getattr(e,m) for e in shuttle) for m in ('distance','travel_time','cost')}} for a in out for b in back]
    return {'scope':'one order, one hub, fixed trunk shuttle, positive weights; no general fleet optimum claim',
            'enumerated_closed_routes':len(rows),'minimum_distance':min(r['distance'] for r in rows),
            'minimum_cost':min(r['cost'] for r in rows),'routes':rows}
