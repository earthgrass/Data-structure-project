"""Hash complete real studio inputs and cost routes in two independent processes."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> None:
    """Two real generations/plans plus O(serialized scene bytes); never overwrite evidence."""
    root=Path(__file__).resolve().parents[1]
    target=root/'docs/experiments'/('operations-studio-reproducibility.json' if len(sys.argv)==1 else sys.argv[1])
    if target.exists():raise ValueError('existing evidence preserved; choose a fresh evidence path')
    script='''import json
from logiroute.dispatch.studio import studio_state,defaults
from logiroute.dispatch.session import Session
from logiroute.dispatch.models import json_value
s=Session(studio_state(42,defaults(),'relaxed'));p=s.prepare('cost')
full={'config':json_value(s.state.config),'nodes':json_value(list(s.state.graph.nodes)),'edges':json_value(list(s.state.graph.edges)),'orders':json_value(list(s.state.orders.values())),'vehicles':json_value(list(s.state.vehicles.values())),'positions':s.state.positions,'locations':s.state.locations,'plan':p.to_dict()}
print(json.dumps(full,ensure_ascii=False,separators=(',',':')))
'''
    rows=[]
    for seed in ('1','2'):
        env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONIOENCODING='utf-8',PYTHONPATH=str(root/'src'),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=180,check=True)
        scene=json.loads(result.stdout)
        assert scene['plan']['report']['valid'] and scene['plan']['report']['complete_all']
        rows.append({'PYTHONHASHSEED':seed,'sha256':hashlib.sha256(result.stdout.encode('utf-8')).hexdigest(),
                     'bytes':len(result.stdout.encode('utf-8')),'accepted':len(scene['plan']['accepted'])})
    assert rows[0]['sha256']==rows[1]['sha256']
    target.write_text(json.dumps({'seed':42,'profile':'bjut-studio','window_mode':'relaxed',
                                 'scope':'full config, nodes, edge metadata+geometry, orders, vehicles, positions, locations and actual cost plan',
                                 'processes':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print(rows)


if __name__=='__main__':main()
