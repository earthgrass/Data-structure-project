"""Static constraints, original-test preservation and recorded experiment replay."""
from __future__ import annotations
import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from logiroute.dispatch.models import json_value
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session


def main() -> None:
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    paths=list((root/'src/logiroute/dispatch').rglob('*.py'))+[root/'src/logiroute/api/routes/dispatch.py']+list((root/'tests').glob('test_dispatch*.py'))+[root/'scripts/accept_phase6.py',root/'scripts/experiment_v2_dispatch.py',Path(__file__)]
    forbidden={'heapq','networkx','numpy','scipy','pandas','pytest','nose2','ortools','pulp','cvxpy','matplotlib','plotly','dash','igraph','networkit','Cython'}
    violations=[]; hashes={}
    for path in paths:
        source=path.read_text(encoding='utf-8'); hashes[path.relative_to(root).as_posix()]=hashlib.sha256(source.encode()).hexdigest()
        for node in ast.walk(ast.parse(source)):
            modules=[]
            if isinstance(node,ast.Import): modules=[n.name for n in node.names]
            if isinstance(node,ast.ImportFrom): modules=[node.module or '']
            if any(m.split('.')[0] in forbidden for m in modules): violations.append(str(path.relative_to(root))+':forbidden import')
            if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id in ('sorted','cmp_to_key')) or (isinstance(node.func,ast.Attribute) and node.func.attr in ('sort','cmp_to_key'))): violations.append(str(path.relative_to(root))+':builtin ordering')
    original=subprocess.run(['git','ls-tree','-r','--name-only','09616a7','--','tests'],cwd=root,check=True,capture_output=True,text=True).stdout.splitlines()
    subprocess.run(['git','diff','--exit-code','09616a7','--',*original],cwd=root,check=True,capture_output=True)
    branch=subprocess.run(['git','branch','--show-current'],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    assert branch=='feat/multivehicle-dynamic-orders'
    expected={'main':'994414753b19c51a2b0522a4fd12a48feb1f6073','feat/dashboard-ui-redesign':'eb6fee0eb67fdcaaca6abcb1ca004767a36ff998','refs/stash':'15964cc350100869942bf893ac79ff031db5b686'}
    for ref,sha in expected.items():
        assert subprocess.run(['git','rev-parse',ref],cwd=root,check=True,capture_output=True,text=True).stdout.strip()==sha
    assert not violations,violations
    evidence=json.loads((root/'docs/experiments/v2-phase6-dispatch-results.json').read_text(encoding='utf-8'))
    for row in evidence['matrix']:
        session=Session(make_state(row['seed'])); edge=next(iter(session.state.graph.edges))
        if row['profile']!='clear': session.traffic(*edge.key,row['profile'])
        assert session.state.fingerprint()==row['fingerprint']
        plan=session.prepare(row['objective']); assert plan.to_dict()==row['plan']
        session.apply(plan); session.depart()
        while session.running: session.step()
        assert json_value(session.events)==row['events'] and json_value(session.audit())==row['audit']
    for row in evidence['dynamic']:
        session=Session(make_state(row['seed'])); session.apply(session.prepare('distance')); session.depart(); session.step()
        order=next(iter(session.state.orders.values())); key=session.state.config['dynamic_prefix']+'-experiment'
        session.add_order(key,order.destination,Decimal('0.1'),session.state.now,session.state.now+float(session.state.config['automatic_window_width']),'critical')
        session.pause()
        while session.running: session.step()
        plan=session.prepare('cost'); assert plan.to_dict()==row['plan']; session.apply(plan); session.depart()
        while session.running: session.step()
        assert json_value(session.events)==row['events'] and json_value(session.audit())==row['audit']
    original_modules=[p[:-3].replace('/','.') for p in original if p.startswith('tests/test_') and p.endswith('.py')]
    original_count=unittest.defaultTestLoader.loadTestsFromNames(original_modules).countTestCases()
    new_count=unittest.defaultTestLoader.discover('tests',pattern='test_dispatch*.py',top_level_dir='.').countTestCases()
    assert original_count==728 and new_count==39,(original_count,new_count,unittest.defaultTestLoader.errors)
    report={'original_test_files_unchanged':len(original),'original_test_count':original_count,'new_test_count':new_count,
            'forbidden_violations':violations,'source_sha256':hashes,'protected_refs':expected,
            'matrix_replayed_identically':len(evidence['matrix']),'dynamic_replayed_identically':len(evidence['dynamic'])}
    (root/'docs/experiments/v2-phase6-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}),flush=True)


if __name__=='__main__': main()
