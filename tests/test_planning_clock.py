"""Short planner calls must use a measured high resolution monotonic clock."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from logiroute.config import load_scenario
from logiroute.scheduling import plan_deliveries


class TestPlanningClock(unittest.TestCase):
    def test_short_elapsed_time_is_measured_without_floor(self) -> None:
        bundle = load_scenario(Path(__file__).resolve().parents[1] / 'config/scenario.json')
        ticks = (100.0, 100.000000125)
        with patch('logiroute.scheduling.planner.time.monotonic', return_value=100.0) as coarse:
            with patch('logiroute.scheduling.planner.time.perf_counter', side_effect=ticks) as precise:
                result = plan_deliveries(bundle, 'nearest_neighbor', 'distance')
        self.assertEqual(result.planning_stats.runtime_seconds, ticks[1] - ticks[0])
        self.assertGreater(result.planning_stats.runtime_seconds, 0)
        self.assertEqual(precise.call_count, 2)
        coarse.assert_not_called()
