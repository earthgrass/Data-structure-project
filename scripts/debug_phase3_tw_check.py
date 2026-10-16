"""Time-window feasibility check for the fixed scenario with 20 orders.

Greedy simulation: from depot W1, sort orders by time_window_start ASC and try
to visit each; record any time-window miss and total elapsed time.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.config import load_scenario


def main() -> int:
    bundle = load_scenario(ROOT / "config" / "scenario.json")
    g = bundle.graph
    init = float(bundle.simulation["initial_time"])
    svc = float(bundle.simulation["service_time"])
    depot = "W1"

    orders = sorted(bundle.orders, key=lambda o: o.time_window_start)

    cur = depot
    cur_t = init
    total_d = 0.0
    misses = 0
    last_window_end = 0.0
    print(f"init cur={cur} cur_t={cur_t}")
    for o in orders:
        leg = shortest_path(g, cur, o.destination_id, "travel_time")
        if not leg.reachable:
            print(f"UNREACHABLE: {o.id} from {cur}")
            return 1
        arrival = cur_t + leg.total_weight
        wait = max(0.0, o.time_window_start - arrival)
        service_start = arrival + wait
        miss = service_start > o.time_window_end + 1e-9
        if miss:
            misses += 1
        total_d += o.demand
        end = o.time_window_end
        print(
            f"  {o.id:6s} from {cur:3s} drive={leg.total_weight:5.2f} "
            f"arr={arrival:6.1f} wait={wait:4.1f} start={service_start:6.1f} "
            f"end={end:6.1f} miss={miss} cum={total_d:6.1f}"
        )
        cur = o.destination_id
        cur_t = service_start + svc
        last_window_end = end

    return_leg = shortest_path(g, cur, depot, "travel_time")
    print(f"\nreturn leg travel_time={return_leg.total_weight:.2f} arrive_back={cur_t + return_leg.total_weight:.2f}")
    print(f"TOTAL cumulative demand = {total_d}")
    print(f"TIME-WINDOW MISSES = {misses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
