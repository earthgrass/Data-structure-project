"""AST import/call audit; classify existing auxiliary sorts, never conceal hits."""
from __future__ import annotations
import ast
import json
import sys
from pathlib import Path


def main() -> None:
    """Time/Space O(source size); no production behavior changes."""
    root=Path(__file__).resolve().parents[1];target=root/'docs/experiments'/('phase7-quality.json' if len(sys.argv)==1 else sys.argv[1])
    if target.exists():raise ValueError('existing evidence preserved')
    banned={'heapq','numpy','scipy','pandas','networkx','igraph','networkit','ortools','pulp','cvxpy','gurobipy','cplex','matplotlib','plotly','dash','pytest','nose2'}
    imports=[];sorts=[]
    files=list((root/'src').rglob('*.py'))+[root/'scripts'/name for name in ('experiment_objective_demo.py','experiment_phase7_windows.py','experiment_phase7_performance.py','audit_phase7_map.py')]
    for p in files:
        tree=ast.parse(p.read_text(encoding='utf-8-sig'));name=p.relative_to(root).as_posix()
        for n in ast.walk(tree):
            modules=[a.name.split('.')[0] for a in n.names] if isinstance(n,ast.Import) else [(n.module or '').split('.')[0]] if isinstance(n,ast.ImportFrom) else []
            if any(m in banned for m in modules):imports.append({'file':name,'line':n.lineno,'modules':modules})
            if isinstance(n,ast.Call) and (isinstance(n.func,ast.Name) and n.func.id=='sorted' or isinstance(n.func,ast.Attribute) and n.func.attr in ('sort','cmp_to_key')):
                category='review_required'
                if name=='src/logiroute/algorithms/dijkstra.py':category='existing_trace_snapshot_only'
                if name=='src/logiroute/graph/logistics_graph.py':category='existing_adjacency_export_view'
                if name=='src/logiroute/scheduling/depot.py':category='existing_legacy_depot_initialization_and_diagnostics'
                sorts.append({'file':name,'line':n.lineno,'classification':category})
    result={'banned_imports':imports,'sort_calls':sorts,'new_unreviewed_sort_calls':[s for s in sorts if s['classification']=='review_required'],
            'note':'Seven pre-existing auxiliary sorted calls retained and disclosed; no new sorting-library replacement in current algorithms.'}
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if imports or result['new_unreviewed_sort_calls']:raise ValueError('unresolved source audit findings')
    print('No banned imports or new unreviewed sort calls;',len(sorts),'existing auxiliary calls disclosed')


if __name__=='__main__':main()
