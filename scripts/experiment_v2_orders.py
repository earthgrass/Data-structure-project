"""Fixed Phase 2 identity/queue/load/config experiments; no fleet scheduling."""
from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

from logiroute.algorithms.order_queue import OrderPriorityQueue, OrderQueueError
from logiroute.config import load_scenario
from logiroute.core import (
    Order, OrderPriority, OrderStatus, ServiceAssignment, DeliveryLoadState,
    check_delivery_load, validate_order_coverage,
)
from logiroute.scenario_generator.validator import validate_generated_scenario
from logiroute.core.quantities import exact_sum


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    single = load_scenario(root / "config/scenario.json")
    fleet = load_scenario(root / "config/scenario_fleet.json")
    items = [Order("O1", "C12", 40, 0, 1000, OrderPriority.URGENT),
             Order("O2", "C12", 35, 0, 900), Order("O3", "C18", 25, 0, 1100)]
    scenario = replace(single, orders=items,
                       vehicles=[replace(single.vehicles[0], capacity=100)])
    assignments = [ServiceAssignment("O1", 1), ServiceAssignment("O2", 1),
                   ServiceAssignment("O3", 2)]
    witness = validate_generated_scenario(scenario, ["W1", "C12", "C18", "W1"],
                                           assignments=assignments)
    assert witness.feasible, witness.violations
    queue = OrderPriorityQueue()
    for item in reversed(items):
        queue.enqueue(item)
    head = queue.peek_next().id
    sequence = [queue.pop_next().id for _ in items]
    assert head == "O1" and sequence == ["O1", "O2", "O3"]
    state = DeliveryLoadState(100, items)
    trace = [state.to_dict()]
    for item in items:
        state.deliver(item.id)
        trace.append(state.to_dict())
    assert [row['current_load'] for row in trace] == ['100', '60', '25', '0']
    overflow = check_delivery_load(100, items[:2] + [replace(items[2], demand=26)])
    assert not overflow.feasible
    duplicate_rejected = False
    try:
        validate_order_coverage(items + [replace(items[0], demand=1)], ("O1", "O2", "O3"))
    except ValueError:
        duplicate_rejected = True
    assert duplicate_rejected
    deadlines = OrderPriorityQueue()
    deadlines.enqueue(Order("B", "C12", 1, 0, 10))
    deadlines.enqueue(Order("A", "C12", 1, 0, 10))
    deadlines.enqueue(Order("Z", "C18", 1, 0, 5))
    deadline_sequence = [deadlines.pop_next().id for _ in range(3)]
    assert deadline_sequence == ['Z', 'A', 'B']
    invalid_statuses: dict[str, bool] = {}
    for status in (OrderStatus.CANCELLED, OrderStatus.DELIVERED, OrderStatus.EXPIRED):
        try:
            OrderPriorityQueue().enqueue(Order('INVALID', 'C12', 1, 0, 10, status=status))
        except OrderQueueError:
            invalid_statuses[status.value] = True
        else:
            raise AssertionError(f"invalid queue status accepted: {status}")
    with localcontext() as context:
        context.prec = 6
        tiny = check_delivery_load(100, [Order('FULL', 'C12', 100, 0, 10),
                                         Order('TINY', 'C12', Decimal('1e-40'), 0, 10)])
    assert not tiny.feasible
    partition = validate_order_coverage(items, ('O1', 'O3'), ('O2',))
    assert partition.valid and not partition.all_orders_served
    result = {
        'same_site_orders': {'input_order_ids': [o.id for o in items],
                            'destinations': [o.destination_id for o in items],
                            'route': ['W1', 'C12', 'C18', 'W1'],
                            'assignments': [{'order_id': a.order_id, 'visit_index': a.visit_index}
                                            for a in assignments],
                            'coverage_checked': witness.coverage_checked,
                            'all_orders_covered': witness.all_orders_covered,
                            'route_coverage_ok': witness.route_coverage_ok},
        'queue': {'head': head, 'pop_sequence': sequence,
                  'deadline_then_id': deadline_sequence, 'invalid_status_rejected': invalid_statuses},
        'load_trace': trace, 'overflow_101': overflow.to_dict(),
        'tiny_overflow_low_precision': tiny.to_dict(),
        'duplicate_id_rejected': duplicate_rejected,
        'complete_partition_with_unserved': {'valid': partition.valid,
                                            'all_orders_served': partition.all_orders_served},
        'fleet_config': {'vehicles': [{'id': v.id, 'capacity': str(v.capacity_decimal),
                                      'current_load': str(v.current_load_decimal)} for v in fleet.vehicles],
                         'bindings': [{'courier_id': c.id, 'vehicle_id': c.vehicle_id} for c in fleet.couriers],
                         'orders': len(fleet.orders),
                         'total_demand': str(exact_sum(o.demand_decimal for o in fleet.orders)),
                         'allocation_performed': False},
        'single_vehicle_compatible': len(single.vehicles) == len(single.couriers) == 1,
    }
    sources = (
        'src/logiroute/core/orders.py', 'src/logiroute/core/vehicles.py',
        'src/logiroute/core/enums.py', 'src/logiroute/core/order_identity.py',
        'src/logiroute/core/quantities.py', 'src/logiroute/core/delivery_load.py',
        'src/logiroute/algorithms/order_queue.py', 'src/logiroute/config/loader.py',
        'src/logiroute/scenario_generator/validator.py',
        'src/logiroute/scenario_generator/backbone_builder.py',
    )
    result['source_sha256'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                               for name in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
