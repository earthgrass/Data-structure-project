"""Independent road-only validation; makes no delivery feasibility claim."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from logiroute.core.edges import Edge
from logiroute.graph.logistics_graph import GraphError, LogisticsGraph
from logiroute.scenario_generator.config_spec import GeneratorConfig


@dataclass(frozen=True)
class RoadValidationReport:
    """Counts use unordered endpoint pairs, never the number of directed edges."""

    valid: bool
    node_count: int
    physical_road_count: int
    bidirectional_road_count: int
    one_way_road_count: int
    directed_edge_count: int
    bidirectional_ratio: float
    target_bidirectional_ratio: float
    ratio_deviation: float
    target_directed_edge_count: int | None
    directed_edge_deviation: int | None
    skeleton_road_count: int
    skeleton_complete: bool
    reachable_and_returnable: bool
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready snapshot. Time / Space O(number of violations)."""
        return asdict(self)


def _covers(adjacency: dict[str, list[str]]) -> bool:
    """Hand-written iterative DFS. Time O(V+E); Space O(V)."""
    if not adjacency:
        return False
    start = next(iter(adjacency))
    seen = {start}
    stack = [start]
    while stack:
        for neighbor in adjacency[stack.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(adjacency)


def validate_road_network(
    graph: LogisticsGraph, config: GeneratorConfig,
) -> RoadValidationReport:
    """Recount real edges, verify metadata and traverse both directions and tree.

    No planner, generation helpers or shortest-path code is used to establish
    the structural checks. All nodes are required, stronger than just depots.
    Time O(V+E+min(V²,max_edges)); Space O(V+E).
    """
    violations: list[str] = []
    try:
        graph.validate()
    except GraphError as exc:
        violations.append(f"graph structure: {exc}")
    nodes = graph.node_ids
    forward: dict[str, list[str]] = {node: [] for node in nodes}
    reverse: dict[str, list[str]] = {node: [] for node in nodes}
    skeleton: dict[str, list[str]] = {node: [] for node in nodes}
    pairs: dict[tuple[str, str], list[Edge]] = {}
    road_pairs: dict[str, tuple[str, str]] = {}
    edge_ids: set[str] = set()
    edges = graph.get_all_edges()
    for edge in edges:
        source, target = edge.source_id, edge.target_id
        if source not in forward or target not in forward or source == target:
            violations.append("edge endpoint missing or self-loop")
            continue
        forward[source].append(target)
        reverse[target].append(source)
        pair = (source, target) if source < target else (target, source)
        pairs.setdefault(pair, []).append(edge)
        for value in (edge.distance, edge.travel_time, edge.cost):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                violations.append(f"illegal edge weight: {pair}")
        metadata = edge.metadata
        road_id, edge_id = metadata.get("road_id"), metadata.get("edge_id")
        if not isinstance(road_id, str) or not road_id:
            violations.append(f"missing road_id: {pair}")
        elif road_id in road_pairs and road_pairs[road_id] != pair:
            violations.append(f"road_id collision: {road_id}")
        else:
            road_pairs[road_id] = pair
        if not isinstance(edge_id, str) or not edge_id or edge_id in edge_ids:
            violations.append(f"missing or duplicate edge_id: {pair}")
        else:
            edge_ids.add(edge_id)
        for flag in ("bidirectional", "skeleton"):
            if not isinstance(metadata.get(flag), bool):
                violations.append(f"missing boolean {flag}: {pair}")

    two_way = one_way = skeleton_count = 0
    skeleton_ok = True
    for pair, directions in pairs.items():
        first = directions[0]
        metadata = first.metadata
        actual_two_way = len(directions) == 2 and (
            directions[0].source_id == directions[1].target_id
            and directions[0].target_id == directions[1].source_id
        )
        if actual_two_way:
            two_way += 1
        elif len(directions) == 1:
            one_way += 1
        else:
            violations.append(f"invalid direction multiplicity: {pair}")
        if metadata.get("bidirectional") != actual_two_way:
            violations.append(f"road direction does not match metadata: {pair}")
        if any(any(edge.metadata.get(key) != metadata.get(key)
                   for key in ("road_id", "bidirectional", "skeleton"))
               for edge in directions):
            violations.append(f"inconsistent direction metadata: {pair}")
            if any(edge.metadata.get("skeleton") is True for edge in directions):
                skeleton_ok = False
        if any(edge.metadata.get("skeleton") is True for edge in directions):
            skeleton_count += 1
            if not actual_two_way:
                skeleton_ok = False
            else:
                skeleton[pair[0]].append(pair[1])
                skeleton[pair[1]].append(pair[0])
    skeleton_ok = skeleton_ok and skeleton_count == len(nodes) - 1 and _covers(skeleton)
    if not skeleton_ok:
        violations.append("protected bidirectional spanning tree is incomplete")
    reachable = _covers(forward) and _covers(reverse)
    if not reachable:
        violations.append("not all nodes are reachable and returnable")
    physical = len(pairs)
    try:
        expected_physical, expected_two_way = config.road_quota(len(nodes))
        if (physical, two_way) != (expected_physical, expected_two_way):
            violations.append("physical road count or integer direction quota differs from config")
    except ValueError as exc:
        violations.append(str(exc))
    if not config.min_nodes <= len(nodes) <= config.max_nodes:
        violations.append("node count outside configured range")
    if not config.min_edges <= len(edges) <= config.max_edges:
        violations.append("directed edge count outside configured budget")
    ratio = two_way / physical if physical else 0.0
    target = config.target_directed_edge_count
    return RoadValidationReport(
        valid=not violations, node_count=len(nodes), physical_road_count=physical,
        bidirectional_road_count=two_way, one_way_road_count=one_way,
        directed_edge_count=len(edges), bidirectional_ratio=ratio,
        target_bidirectional_ratio=config.bidirectional_ratio,
        ratio_deviation=ratio - config.bidirectional_ratio,
        target_directed_edge_count=target,
        directed_edge_deviation=None if target is None else len(edges) - target,
        skeleton_road_count=skeleton_count, skeleton_complete=skeleton_ok,
        reachable_and_returnable=reachable, violations=tuple(violations),
    )
