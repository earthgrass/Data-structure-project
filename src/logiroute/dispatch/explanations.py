"""Human-readable descriptions of recorded failures; no extra planning or replay."""
from __future__ import annotations

from logiroute.dispatch.models import FailureEvidence,OrderExplanation


def explain_order(order_id: str,reason: str,attempts: tuple[FailureEvidence,...]) -> OrderExplanation:
    """Describe the last representative failure and retain every hub attempt.

    Time/Space O(attempts + mentioned IDs). Suggestions are unverified next steps,
    never promises of acceptance or permission to relax a hard constraint.
    """
    item=attempts[-1] if attempts else None
    code=item.code if item else reason.removeprefix('protected_continuation:')
    vehicle=item.vehicle if item and item.vehicle else '候选车辆'
    ids='、'.join(item.order_ids) if item and item.order_ids else '相关订单'
    summary='现有启发式尝试未找到可接纳的方案。'
    suggestions=('检查订单输入和车辆状态后重新规划；建议需经新计划独立验证。',)
    if code=='capacity' and item:
        summary=f'{vehicle} 此次候选装载 {item.load} kg，超过单车容量 {item.capacity} kg。涉及订单：{ids}。'
        suggestions=('在未执行的新场景中试算该车容量；容量变更须重新独立验证。',)
    elif code=='completion_deadline' and item:
        if item.stage=='unload':
            summary=f'{vehicle} 此候选批次卸货按最早截止 {item.deadline} 分检查，实际候选完成时刻为 {item.service_end} 分；超过各自截止的订单：{ids}。'
        else:
            summary=f'{vehicle} 候选路线使 {ids} 的签收完成时刻为 {item.service_end} 分，超过截止 {item.deadline} 分。'
        suggestions=('核对所列受影响订单的截止时间；若要调整，请在允许的场景输入中修改并重新验证。',
                     '也可试算其他运营参数；当前失败候选不证明其他路线都不可行。')
    elif code in ('unreachable','return_unreachable') and item:
        summary=f'当前道路快照中，{vehicle} 的 {item.source} → {item.target} '+('返程不可达。' if code=='return_unreachable' else '候选连接不可达。')
        suggestions=('检查该方向的封路状态及出发、服务、返仓地点，再重新规划。',)
    elif code=='critical_precedence':
        summary=f'{vehicle} 的候选服务顺序违反同批特急优先约束；涉及任务：{ids}（中转卸货可能包含混合优先级订单）。'
        suggestions=('核对优先级与时间窗的组合；不能通过跳过特急约束强行接单。',)
    elif code=='missing_protected_hub':
        summary=f'已保护任务 {ids} 缺少合法中转站归属，当前续程不能安全应用。'
    elif code=='unsupported_warehouse':
        summary=f'订单 {ids} 所在仓库不属于当前干线车辆的装货仓库。'
    elif code=='inventory_not_released':
        summary=f'订单 {ids} 的货物尚未由干线释放到末端车辆所在中转站。'
    elif code.startswith('nonfinite_'):
        summary=f'{vehicle} 候选路线的时间或指标不是合法有限数，已拒绝应用。'
    if reason.startswith('protected_continuation:'):
        summary='现有保护任务无法安全续送。'+summary
    summary+=' 这是记录的启发式候选失败，不是全局无解证明。'
    return OrderExplanation(order_id,reason,summary,'heuristic_candidate',attempts,suggestions)
