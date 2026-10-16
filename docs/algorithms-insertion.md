# Cheapest Feasible Insertion 单车闭合构造 —— Phase 3 算法文档

> 本文档是 `src/logiroute/scheduling/algorithms/insertion.py` 的课程教学材料。
> 配套测试：`tests/test_scheduling_insertion.py`、`tests/test_scheduling_planner.py`。

---

## 一、问题定义

同 `nearest_neighbor` 的单车闭合调度问题（见 `algorithms-nearest-neighbor.md`
§一）：

* 单车辆从出发仓库 $d$ 出发遍历所有待配送订单后**返回** $d$；
* 容量 / 时间窗 / 可达性硬约束同 NN；
* 主目标 `distance` / `cost` 二选一，行驶时间仅作对比列（AGENTS §3.7）。

**与 NN 的差异**：构造顺序不同——CFI 从一个**种子**开始，反复把剩余订单以"成本增量最小且仍可行"的位置**插入**到当前路线中；NN 则每轮从头选"下一站"。

---

## 二、为什么需要 CFI？

NN 的问题：

| 问题 | 说明 |
| --- | --- |
| 贪心易陷局部最优 | 早期选的最近订单把后续订单挤到时间窗外 → 后续大批不可服务 |
| 时间窗违反累积 | 后期单点违反滚雪球 |
| 不"借"已有路线 | 没法利用"绕一下更便宜"的全局结构 |

CFI 的改进：

* 每个新订单插入**已有路线**的某个位置，使得"总成本增加最少"——这天然考虑
  了**绕路**（相比"另起一段"更便宜的情形）；
* 每插入一步都要做**完整可行性校验**，不接受任何会让路线不可行的插入；
* 配合手写"argmin 插入位置"扫描，能在不调用 `sorted()` / `heapq` 等禁表
  工具的情况下达到较好的局部解。

**计算代价**：CFI 比 NN 慢——每插入一个订单需要枚举所有插入位置（O(K) 个）
× 所有候选订单（O(M) 个）= O(M·K) 次 trial，叠加 Dijkstra 开销。

---

## 三、核心数据结构

### 3.1 `_TourState`

```python
class _TourState:
    stops: tuple[DeliveryStop, ...]      # K+2（含首尾 depot）
    legs: tuple[PathResult, ...]          # K+1 车辆腿
    stop_sequence: tuple[str, ...]       # 仅节点 ID
    stop_infos: tuple[_StopInfo, ...]    # (node_id, Order | None)
    served_order_ids: tuple[str, ...]    # 从 stop_infos 派生
```

| 项 | 内容 |
| --- | --- |
| 作用 | CFI 主循环维护的**可变**路线快照；避免反复重建 `RoutePlan` |
| schema | `len(stops) == len(legs) + 1`，`len(stop_infos) == len(stops)` |
| depot 端点 | `stop_infos[0].order is None and stop_infos[-1].order is None` |
| 中间站 | `stock_order.id == stop.order_id` 对应订单 ID |

### 3.2 `_StopInfo`（namedtuple）

```python
_StopInfo = namedtuple("_StopInfo", ["node_id", "order"])
```

| 字段 | 含义 |
| --- | --- |
| `node_id` | 节点 ID（与 `stops[i].node_id` 一致） |
| `order` | 对应订单；`None` 表示仓库端点 |

### 3.3 PathProvider（与 NN 共享同一缓存）

* 调度实例化一次性构造；
* 所有插入 trial 的 leg 全部从 `path_provider.shortest_path(s, t, metric)` 取；
* 单调度作用域自然丢弃缓存，避免跨场景串味（AGENTS §3.7）。

---

## 四、算法骨架

### 4.1 主入口

```python
def cheapest_feasible_insertion(ctx, eligible_orders):
    # 0. 空集合
    if not eligible_orders:
        return _build_route_plan(ctx, _build_empty_state(ctx))

    # 1. 种子选择：URGENT 优先 + id ASC + 首段可达 + 容量合法
    seed = _first_feasible_seed(ctx, eligible_orders)
    if seed is None:
        raise InfeasibleSeedError(...)

    current = _build_seed_state(ctx, seed)
    remaining = [o for o in eligible_orders if o.id != seed.id]
    unserved = []

    # 2. 主循环
    while remaining:
        # 当前路线若已不可行 → 剩余全部归类为 no_feasible_insertion
        if not check_feasibility(current).is_feasible:
            unserved += [_make_unserved(v) for v in remaining]
            break

        # 2.1 对每个候选订单，找最佳插入位置
        best_state, best_delta, best_order_id, best_pos = None, +inf, "", 0
        for order in remaining:
            tried = _try_insert(current, ctx, order)
            if tried is None:
                continue
            new_state, delta, pos = tried
            if (delta, order.id, pos) < (best_delta, best_order_id, best_pos):
                best_state, best_delta, best_order_id, best_pos = \
                    new_state, delta, order.id, pos

        if best_state is None:
            unserved += [_make_unserved(v) for v in remaining]
            break

        current = best_state
        remaining.remove(best_order_id)

    return _build_route_plan(ctx, current, unserved_orders=tuple(unserved))
```

### 4.2 `_try_insert`：单订单插入位置枚举

```python
def _try_insert(state, ctx, candidate_order):
    candidate_info = _StopInfo(candidate_order.destination_id, candidate_order)
    best_state, best_pos, best_delta = None, -1, +inf

    for pos in range(1, len(state.stop_infos)):  # 配送站之间
        trial_infos = (state.stop_infos[:pos]
                       + (candidate_info,)
                       + state.stop_infos[pos:])
        trial_legs = tuple(
            ctx.path_provider.shortest_path(s, t, ctx.objective)
            for s, t in zip(trial_sequence[:-1], trial_sequence[1:])
        )
        if any(not leg.reachable for leg in trial_legs):
            continue

        trial_stops = _rebuild_stops_with_timing(trial_infos, trial_legs, ctx)
        if not check_feasibility(...).is_feasible:
            continue

        delta = _main_total(trial_legs, ctx.objective) - current_main
        if delta < best_delta or (delta == best_delta and pos < best_pos):
            best_state, best_delta, best_pos = new_state, delta, pos

    return (best_state, best_delta, best_pos) if best_state else None
```

**关键步骤**：

1. **插入位置枚举** —— `pos ∈ [1, K+1)`，仅配送站之间；depot 端点永不参与反转；
2. **重建 leg** —— 通过 `PathProvider` 取所有相邻最短路（缓存复用）；
3. **可达性剪枝** —— 任一 leg 不可达 → 跳过该位置；
4. **可行性校验** —— `check_feasibility(stops, legs, ...)` 拒绝任何时间窗 / 容量违反；
5. **手写线性扫描 argmin** —— `(delta, pos)` 二元组 ASC，保证确定性；
6. **返回 `(new_state, delta_min, pos_chosen)`** 或 `None`（无可行位置）。

---

## 五、复杂度分析

设：

* $V$ = 节点数，$E$ = 边数；
* $M$ = 候选订单总数；
* $K$ = 当前路线配送站数（$K \le M$，随插入单调）。

### 5.1 主操作计数

| 操作 | 每次 | 调用次数 | 累计 |
| --- | --- | --- | --- |
| 候选订单外层循环 | O(M) | 每轮 1 次 | O(M²) |
| 插入位置内层枚举 | O(K) | 每候选 1 次 | O(M · K) |
| 重建 leg | O(K · (V+E) log V) | 每位置 1 次 | O(M · K² · ((V+E) log V)) |
| 时间传播 / `check_feasibility` | O(K) | 每位置 1 次 | O(M · K² · K) = O(M · K³) |
| `_rebuild_stops_with_timing` | O(K) | 每位置 1 次 | O(M · K³) |

**总时间**：O(M · K² · ((V + E) log V)) —— 主项是位置 × trial 的 Dijkstra 调用，
叠加 K² 个候选 stop 之间的 leg 重建。

**辅助空间**：

* `_TourState` —— O(K)；
* trial 候选（短生命周期）—— O(K)；
* PathProvider 缓存 —— O(M · K)；
* **合计 O(K · M + V + E)**。

### 5.2 与 NN 的对比

| 维度 | NN | CFI |
| --- | --- | --- |
| 时间上界 | O(M · ((V+E) log V)) | O(M · K² · ((V+E) log V)) |
| 解的质量 | 贪心、近邻可选、解质量中等偏上 | 可比 NN 更优，但仍有局部性 |
| 空间上界 | O(K + M + V + E) | O(K · M + V + E) |

> 在固定场景（35 节点 / ~177 边 / 20 订单）实测：CFI 比 NN 慢一个量级
> （~125ms vs ~47ms），但平均 `main_objective_total` 通常与 NN 相当或更优。
> 真正能跑赢 NN 的是 2-opt（基于 NN 种子做局部反转）。

---

## 六、正确性论证

### 6.1 终止性

* `while remaining` 每轮必然 `pop` 一个订单（若 `best_state is None` 则 break）；
* `remaining` 长度严格单调下降；
* **必然在至多 M 轮后终止**。✓

### 6.2 闭合不变量

* 初始 `_TourState` 含 `(depot, seed, depot)`，三段两 leg；
* 主循环每次插入到 `pos ∈ [1, K+1)`，depot 端点永不参与反转；
* `_build_route_plan` 在装配 `RoutePlan` 时由 schema 强制 `stop_sequence[0] ==
  stop_sequence[-1] == depot_id`；
* **闭合不变量始终成立**。✓

### 6.3 可行性不变量

* `_try_insert` 中每个 trial 都先经 `check_feasibility` 校验；
* `current_state` 在主循环每轮开头都重新校验一次；
* 任何 trial 不通过 → 不进入 `best_state` 候选；
* 因此**最终 `RoutePlan.is_feasible == check_feasibility(state).is_feasible`**。✓

### 6.4 不可行订单如实报告

* 当前路线已不可行 → 剩余订单**全部**归类为 `no_feasible_insertion`；
* 单订单 `best_state is None`（无可行插入位置）→ 同上处理；
* `unserved` 写入 `RoutePlan.notes['unserved_orders']`，planner 上提至
  `ScheduleResult.unserved_orders`；
* **永不伪造 100% 完成率**（AGENTS §3.6）。✓

### 6.5 确定性

* tie-break 键 `(delta, order.id, pos)` 字典序确定；
* 种子选择按 `(URGENT, id ASC)` 确定；
* 手写线性 argmin，无 `heapq` / `sorted` 等禁表带来的实现差异。✓

### 6.6 主目标 / 对比列分离

* `_main_total(trial_legs, ctx.objective)` 累计 `leg.total_weight`（主目标列）；
* 装配 `RoutePlan` 时 `total_distance / total_cost` 按主目标 / 对比列分别累加；
* `main_objective_total` 与 `RoutePlan.__post_init__` 第 5 项校验联动。✓

---

## 七、API 设计

### 7.1 `cheapest_feasible_insertion(ctx, eligible_orders, seed_algorithm="nearest_neighbor") -> RoutePlan`

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `ctx` | `PlanningContext` | 调度作用域上下文 |
| `eligible_orders` | `Sequence[Order]` | 候选订单列表（已通过订单层校验） |
| `seed_algorithm` | `str` | 种子算法标识；当前仅 `"nearest_neighbor"` 合法 |

返回：闭合 `RoutePlan`，含 `served_order_ids / is_feasible / totals`；
**不可行订单**写入 `RoutePlan.notes['unserved_orders']`（`to_dict()` 序列化友好）。

### 7.2 异常

| 异常 | 触发 |
| --- | --- |
| `ValueError` | `seed_algorithm` 不在白名单 |
| `InfeasibleSeedError` | `eligible_orders` 中无任何"首段可达 + 容量合法 + 首站时间窗不迟到"订单 |

### 7.3 边界

| 边界 | 行为 |
| --- | --- |
| `eligible_orders == []` | 返回 `(depot, depot)` 空路线 |
| 全部订单无可行插入 | 返回含全部 unserved 的 RoutePlan |
| 闭合段不可达 | `RoutePlan.__post_init__` 抛 `ValueError`（planner 捕获） |

---

## 八、与 Phase 2 Dijkstra 的接口

### 8.1 调用契约

* 每个 trial 调用 `ctx.path_provider.shortest_path(s, t, ctx.objective)` 对每个
  相邻站点对一次；
* 主目标维度始终是 `ctx.objective`（`distance` 或 `cost`）；
* `travel_time` 不作为主目标维度，仅在 `_rebuild_stops_with_timing` 通过
  `leg.cross_metrics['travel_time']` 读取行驶时间（与 NN 一致）。

### 8.2 缓存复用与口径统一

| 场景 | 行为 |
| --- | --- |
| trial leg 命中 | O(1) 返回引用，`cache_hits++` |
| trial leg 未命中 | 调 Dijkstra，结果入缓存（仅可达） |
| `_try_insert` 内部反复试同一对 stop | PathProvider 摊销到 O(1) |

### 8.3 拒绝重复实现

* CFI 不持有任何"自己算的"路径；
* 所有 leg 必须来自 `ctx.path_provider`；
* 禁止在 CFI 内重写最短路径子例程（AGENTS §3.5、§3.7）。

---

## 九、代码索引

| 概念 | 文件 | 行号 |
| --- | --- | --- |
| `cheapest_feasible_insertion` 主入口 | `src/logiroute/scheduling/algorithms/insertion.py` | 全文 |
| `_TourState`（可变路线快照） | 同上 | 类定义段 |
| `_StopInfo`（namedtuple） | 同上 | namedtuple 定义段 |
| `_first_feasible_seed`（手写插入排序） | 同上 | 函数体 |
| `_build_seed_state` / `_build_empty_state` | 同上 | 函数体 |
| `_try_insert`（位置枚举 + trial 校验） | 同上 | 函数体 |
| `_rebuild_stops_with_timing`（时间传播） | 同上 | 函数体 |
| `_make_unserved_violation`（写 notes 通道） | 同上 | 函数体 |
| 与 `planner` 的契约（notes → `ScheduleResult`） | `src/logiroute/scheduling/planner.py` | `_lift_unserved_from_notes` |
| PathProvider 接口 | `src/logiroute/scheduling/path_provider.py` | `shortest_path / road_node_sequence` |
| 单元测试 | `tests/test_scheduling_insertion.py` / `tests/test_scheduling_planner.py` | 全部用例 |