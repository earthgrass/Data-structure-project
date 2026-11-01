"""Persist genuine full-suite evidence, including tracebacks; never edits tests."""
from __future__ import annotations
import ctypes
import io
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import unittest


def main() -> int:
    """Run twice without synthetic timing, preserve each run immediately. O(test suite)."""
    root=Path(__file__).resolve().parents[1]; os.chdir(root)
    destination=root/'docs/experiments'/('v2-phase6-acceptance.json' if len(sys.argv)==1 else sys.argv[1])
    if destination.exists(): raise ValueError('existing evidence preserved; choose a fresh evidence path')
    runs=2 if len(sys.argv)<3 else int(sys.argv[2])
    if runs<1: raise ValueError('at least one real run required')
    previous=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001) if os.name=='nt' else None
    evidence={'python':sys.version,'command':'python -B -m unittest discover -s tests -t .','runs':[]}
    try:
        for index in range(runs):
            stream=io.StringIO(); suite=unittest.defaultTestLoader.discover('tests',top_level_dir='.')
            started=perf_counter(); result=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite); elapsed=perf_counter()-started
            output=stream.getvalue().replace(str(root),'<repository>')
            record={'run':index+1,'tests':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
                    'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
                    'exit_code':0 if result.wasSuccessful() else 1,'runtime_seconds':elapsed,'output':output}
            evidence['runs'].append(record); destination.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in record.items() if k!='output'}),flush=True)
            if not result.wasSuccessful(): print(output,flush=True); return 1
    finally:
        if previous is not None: ctypes.windll.kernel32.SetThreadExecutionState(previous)
    return 0


if __name__=='__main__': raise SystemExit(main())
