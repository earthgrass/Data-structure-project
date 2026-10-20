"""Small in-memory algorithm fixtures; production loader limits are unchanged."""
from __future__ import annotations
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Node, Edge, Order, Vehicle, Courier, NodeType
from logiroute.graph import LogisticsGraph


def toy(orders: list[Order] | None = None, capacities: tuple = (10,),
        homes: tuple[str, ...] | None = None) -> ScenarioBundle:
    homes = homes if homes is not None else tuple('W' for _ in capacities)
    graph = LogisticsGraph()
    nodes = ('W', 'A', 'B', 'W2') if 'W2' in homes else ('W', 'A', 'B')
    for node in nodes:
        graph.add_node(Node(node, node, NodeType.WAREHOUSE if node in ('W', 'W2')
                            else NodeType.CUSTOMER, 0, 0))
    for source in nodes:
        for target in nodes:
            if source != target:
                graph.add_edge(Edge(source, target, 1, 1, 1))
    return ScenarioBundle('toy', 'fixed', 0, graph,
        [Vehicle(f'V{i+1}', capacity, current_node_id=homes[i])
         for i, capacity in enumerate(capacities)],
        [Courier(f'D{i+1}', f'D{i+1}', f'V{i+1}') for i in range(len(capacities))],
        orders if orders is not None else [Order('O1', 'A', 1, 0, 100),
                                          Order('O2', 'B', 1, 0, 100)],
        {'initial_time': 0, 'service_time': 1})
