"""Run actual isolated objectives; preserve raw plans, measurements and reference."""
from __future__ import annotations
import json
from pathlib import Path
from logiroute.dispatch.controlled_demo import objective_demo


def main() -> None:
    """Time dominated by two production plans; no evidence overwrites."""
    target=Path(__file__).resolve().parents[1]/'docs/experiments/phase7-objectives.json'
    if target.exists():raise ValueError('existing original evidence preserved')
    result=objective_demo();target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print([(r['objective'],r['distance'],r['cost'],r['travel_time']) for r in result['runs']])


if __name__=='__main__':main()
