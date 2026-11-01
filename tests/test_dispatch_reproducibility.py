from __future__ import annotations
import json
import os
import subprocess
import sys
import unittest
from logiroute.dispatch.generation import generate_state,GenerationError
from logiroute.dispatch.scenario import load_config


class TestDispatchReproducibility(unittest.TestCase):
    def test_five_seeds_full_scenes_routes_and_history_across_processes(self) -> None:
        code='''
import hashlib,json
from logiroute.dispatch.generation import generate_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.models import json_value
rows=[]
for seed in (0,1,42,100,2026):
 state,attempts=generate_state(seed)
 for mode in ('distance','cost'):
  session=Session(state if mode=='distance' else generate_state(seed)[0])
  plan=session.prepare(mode); session.apply(plan); session.depart()
  while session.running: session.step()
  assert session.audit().complete_all
  rows.append([seed,mode,plan.fingerprint,plan.to_dict(),json_value(session.events)])
print(hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest())
'''
        outputs=[]
        for seed in ('1','2'):
            env=os.environ.copy(); env['PYTHONHASHSEED']=seed; env['PYTHONPATH']='src'; env['PYTHONDONTWRITEBYTECODE']='1'
            result=subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr); outputs.append(result.stdout.strip())
        self.assertEqual(outputs[0],outputs[1]); self.assertEqual(len(outputs[0]),64)

    def test_exhaustion_retains_every_attempt(self) -> None:
        c=load_config(); c['timing']['window_end']=0.01; c['max_generation_attempts']=2
        with self.assertRaises(GenerationError) as caught: generate_state(42,c)
        self.assertEqual(len(caught.exception.attempts),2)
        self.assertTrue(all(not r['report']['complete_all'] for a in caught.exception.attempts for r in a['plans']))
