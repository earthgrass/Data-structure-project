"""JSON policy adapter; window construction algorithms live in algorithms/."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from logiroute.algorithms.window_calibration import calibrate_windows,WindowGenerationError


def load_window_policy(config: dict[str,Any]) -> dict[str,Any]:
    """Read explicit opt-in policy. Time/Space O(policy bytes)."""
    return json.loads((Path(__file__).resolve().parents[3]/config['time_window_policy_file']).read_text(encoding='utf-8'))


__all__=['load_window_policy','calibrate_windows','WindowGenerationError']
