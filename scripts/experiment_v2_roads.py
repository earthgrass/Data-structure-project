"""Reproduce old/new road statistics in isolated processes, without switching Git refs."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


BASELINE = "eb6fee0eb67fdcaaca6abcb1ca004767a36ff998"
ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
from dataclasses import asdict
import hashlib
import json
from time import perf_counter
from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG, RandomSource, generate_scenario, sample_logistics_graph,
)
try:
    from logiroute.scenario_generator.road_validator import validate_road_network
except ModuleNotFoundError:
    validate_road_network = None

def covers(adjacency):
    stack = [next(iter(adjacency))]
    seen = set(stack)
    while stack:
        for neighbor in adjacency[stack.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(adjacency)

rows = []
for seed in (0, 1, 42, 100, 2026):
    start = perf_counter()
    initial_graph = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, RandomSource(seed))
    graph_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    bundle, backbone = generate_scenario(seed=seed)
    scenario_ms = (perf_counter() - start) * 1000
    graph = bundle.graph
    graph.validate()
    pairs = {}
    forward = {node: [] for node in graph.node_ids}
    reverse = {node: [] for node in graph.node_ids}
    for edge in graph.get_all_edges():
        a, b = edge.source_id, edge.target_id
        key = (a, b) if a < b else (b, a)
        pairs[key] = pairs.get(key, 0) + 1
        forward[a].append(b)
        reverse[b].append(a)
    two_way = sum(count == 2 for count in pairs.values())
    payload = {
        'name': bundle.name, 'mode': bundle.mode, 'random_seed': bundle.random_seed,
        'nodes': [asdict(node) for node in graph.get_all_nodes()],
        'edges': [asdict(edge) for edge in graph.get_all_edges()],
        'orders': [asdict(order) for order in bundle.orders],
        'vehicles': [asdict(vehicle) for vehicle in bundle.vehicles],
        'couriers': [asdict(courier) for courier in bundle.couriers],
        'simulation': bundle.simulation, 'optimization': bundle.optimization,
        'metadata': bundle.metadata, 'backbone': backbone,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=True,
                                            separators=(',', ':')).encode()).hexdigest()
    rows.append({
        'seed': seed, 'node_count': graph.node_count,
        'physical_road_count': len(pairs), 'bidirectional_road_count': two_way,
        'one_way_road_count': len(pairs) - two_way,
        'directed_edge_count': graph.edge_count,
        'bidirectional_ratio': two_way / len(pairs),
        'reachable_and_returnable': covers(forward) and covers(reverse),
        'skeleton_complete': None if validate_road_network is None else
            validate_road_network(graph, DEFAULT_GENERATOR_CONFIG).skeleton_complete,
        'road_validation': None if validate_road_network is None else
            validate_road_network(graph, DEFAULT_GENERATOR_CONFIG).to_dict(),
        'initial_graph_matches_scenario': initial_graph.get_all_edges() == graph.get_all_edges(),
        'scenario_sha256': fingerprint, 'graph_generation_ms': graph_ms,
        'scenario_generation_ms': scenario_ms,
    })
print(json.dumps(rows))
'''


def run_children(source_root: Path) -> list[dict]:
    """Compare three hash seeds; timing is excluded from identity checks."""
    runs = []
    for hash_seed in ("1", "2", "73"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed,
                   PYTHONPATH=str(source_root / "src"))
        result = subprocess.run([sys.executable, "-B", "-c", CHILD], cwd=source_root,
                                env=env, capture_output=True, text=True,
                                timeout=60, check=True)
        runs.append(json.loads(result.stdout))
    for index, row in enumerate(runs[0]):
        row["reproducible"] = all(
            row["scenario_sha256"] == run[index]["scenario_sha256"] for run in runs[1:]
        )
        if not row["reproducible"]:
            raise RuntimeError(f"cross-process scenario mismatch for seed {row['seed']}")
    return runs[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive = subprocess.run(["git", "archive", "--format=zip", BASELINE, "src"],
                             cwd=ROOT, capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix="logiroute-v1-roads-") as directory:
        source_root = Path(directory).resolve()
        with zipfile.ZipFile(io.BytesIO(archive)) as files:
            for member in files.infolist():
                if not (source_root / member.filename).resolve().is_relative_to(source_root):
                    raise ValueError("archive path escaped temporary directory")
            files.extractall(source_root)
        old_rows = run_children(source_root)
    new_rows = run_children(ROOT)
    source_files = (
        "src/logiroute/scenario_generator/graph_sampler.py",
        "src/logiroute/scenario_generator/config_spec.py",
        "src/logiroute/scenario_generator/road_defaults.json",
        "src/logiroute/scenario_generator/road_validator.py",
        "src/logiroute/scenario_generator/generator.py",
        "src/logiroute/scenario_generator/backbone_builder.py",
        "src/logiroute/algorithms/ordering.py",
    )
    output = {
        "baseline_commit": BASELINE, "python_version": sys.version,
        "hash_seeds": ["1", "2", "73"],
        "timing_note": "one measured run per seed, no performance superiority claim",
        "new_source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in source_files},
        "old": old_rows, "new": new_rows,
    }
    if not all(row["road_validation"]["valid"] and row["initial_graph_matches_scenario"]
               for row in new_rows):
        raise RuntimeError("new road validation or initial/scenario graph comparison failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for label, rows in (("old", old_rows), ("new", new_rows)):
        for row in rows:
            print(label, json.dumps(row, ensure_ascii=True))


if __name__ == "__main__":
    main()
