# Nearest-Neighbor 单车闭环基线 —— Phase 3 算法文档

> 本文档是 `src/logiroute/scheduling/algorithms/nearest_neighbor.py` 的课程教学材料。
> 配套测试：`tests/test_scheduling_nearest_neighbor.py`、`tests/test_scheduling_planner.py`。

---

## 一、问题定义

给定：

* 道路网络有向带权图 $G = (V, E)$（Phase 1 路网，三种 metric）；
* 单辆配送车辆 $v$，从出发仓库 $d \in V$ 出发，容量上限 $C$；
* 订单集合 $O = \{o_1, \ldots, o_M\}$，每个订单含目的地 $\mathrm{dest}(o)$、
  需求 $\mathrm{demand}(o)$、时间窗 $[\mathrm{tw}_{\mathrm{start}}(o),
  \mathrm{tw}_{\mathrm{end}}(o)]$、优先级 $\mathrm{prio}(o) \in \{\text{URGENT},
  \text{NORMAL}\}$；
* 服务时长 $\sigma$（每站固定 $\sigma$ 分钟）；
* 出发时刻 $t_0$。

**目标**：构造一条**单车闭合**回路

$$
d = v_0 \to v_1 \to \cdots \to v_K \to v_0, \quad v_0 = d,
$$

满足：

| 约束 | 描述 |
| --- | --- |
| 闭合 | 首尾均为出发仓库 $d$ |
| 单车辆 | 调度器只允许一辆车 |
| 容量 | $\sum_{i=1}^{K} \mathrm{demand}(o_i) \le C$ |
| 时间窗 | 对每个客户站 $i \ge 1$，服务开始时刻 $\le \mathrm{tw}_{\mathrm{end}}$ |
| 可达 | 相邻站点之间的实际行驶路径由 Phase 2 Dijkstra 提供 |

**主目标**（单一，二选一）：

* `distance`：最短行驶距离；
* `cost`：最低运输成本；

行驶时间 $t$ 仅作为**附加对比列**，不作为主目标（AGENTS §3.7）。

---

## 二、为什么需要 NN？

调度问题在最一般情况下是 NP-hard 的 **TSP** 或 **VRP**。本课程阶段的目标
是构造一个**清晰、可读、确定性、可单元化**的基线，而非追求全局最优。

NN 的价值：

| 价值 | 说明 |
| --- | --- |
| **基线（baseline）** | 任意后续改进（CFI / 2-opt）必须能"击败" NN，否则不构成改进 |
| **教学性** | 结构简单，全扫描候选 → 选择最近 → 推进 → 重复 |
| **可预测性** | 同输入下输出相同，便于排查正确性 |
| **可作为 2-opt 种子** | 2-opt 本质上是在 NN 路线上做局部段反转 |

与 Phase 2 Dijkstra 的耦合：

* NN 每一轮都要为当前候选订单查最短路径；
* Dijkstra 提供"距离 / 时间 / 成本"三种独立最短路径；
* NN 仅选取"主目标维度"作为"下一站选择键"，但**行驶时间永远走 travel_time
  维度**（避免把主目标所选路径错当行驶时间）。

---

## 三、核心数据结构

### 3.1 `remaining: list[Order]`

| 项 | 内容 |
| --- | --- |
| 作用 | 尚未访问的订单列表 |
| 初始 | `eligible_orders` 的稳定排序：`(URGENT 先, id 字典序)` |
| 更新 | 每轮从末尾移除已选订单 |
| 顺序 | URGENT 先扫，NORMAL 后扫（同优先级用 id 升序） |

### 3.2 `plan_stops: list[DeliveryStop]`

| 项 | 内容 |
| --- | --- |
| 作用 | 已确定的站点事件快照（不可变元素） |
| 初始 | 第 0 站 = 出发仓库 |
| 更新 | 每轮 `append` 一个客户站，最后追加返回仓库 |
| 时间字段 | `arrival / service_start / service_end / waiting_time / order_id / demand / cumulative_load / time_window_*` |

### 3.3 `plan_legs: list[PathResult]`

| 项 | 内容 |
| --- | --- |
| 作用 | 相邻站点之间的最短路径结果（Phase 2 Dijkstra 输出） |
| 更新 | 每轮 append 主目标 leg；末段 append 回归仓库 leg |
| 数量 | 始终 `len(stops) - 1` |

### 3.4 `current_time / current_load / current_node`

| 字段 | 作用 |
| --- | --- |
| `current_time` | 上一站 `service_end`（最新时间） |
| `current_load` | 累计装载需求（用于容量硬约束） |
| `current_node` | 当前所在节点（用于下次 Dijkstra 查询的源） |

### 3.5 `PathProvider` 缓存

* 键：`(graph_version, source, target, metric)`；
* **不**写负缓存（不可达查询不缓存，避免某条边临时不可达被永久"记住"）；
* `source == target` 走零权快捷路径，不入缓存。

---

## 四、算法骨架

```python
def nearest_neighbor(ctx, eligible_orders):
    # ---- 1. 初始化 -----------------------------------------------------
    current_node = ctx.depot_id
    current_time = ctx.initial_time
    current_load = 0.0
    remaining = sorted(eligible_orders,
                       key=lambda o: (priority_rank[o.priority], o.id))
    plan_stops = [depot_start_stop(ctx)]        # seq_index = 0
    plan_legs = []

    # ---- 2. 主循环 ------------------------------------------------------
    while remaining:
        best, best_key, best_leg_main, best_leg_time = None, None, None, None

        for order in remaining:
            # 容量硬约束
            if current_load + order.demand > ctx.capacity + _TOL:
                continue

            # 主目标维度 + 时间维度（不同 Dijkstra 路径）
            leg_main = ctx.path_provider.shortest_path(
                current_node, order.destination_id, ctx.objective)
            leg_time = ctx.path_provider.shortest_path(
                current_node, order.destination_id, "travel_time")

            if not (leg_main.reachable and leg_time.reachable):
                continue

            # 时间传播
            drive_time = leg_time.cross_metrics["travel_time"]
            arrival = current_time + drive_time
            wait = max(0.0, order.time_window_start - arrival)
            service_start = arrival + wait
            if service_start > order.time_window_end + _TOL:
                continue

            # tie-break：(total_weight, order.id, len(path)) 升序
            key = (leg_main.total_weight, order.id, len(leg_main.path))
            if best_key is None or key < best_key:
                best, best_key, best_leg_main, best_leg_time = (
                    order, key, leg_main, leg_time)

        if best is None:
            break  # 剩余订单全部不可行

        # 推进：实际进入路线
        drive_time = best_leg_time.cross_metrics["travel_time"]
        arrival = current_time + drive_time
        wait = max(0.0, best.time_window_start - arrival)
        service_start = arrival + wait
        service_end = service_start + ctx.service_time
        current_time = service_end
        current_load += best.demand
        plan_stops.append(make_stop(...))
        plan_legs.append(best_leg_main)
        current_node = best.destination_id
        remaining.remove(best)

    # ---- 3. 闭合：append 回归仓库 --------------------------------------
    return_leg = ctx.path_provider.shortest_path(
        current_node, ctx.depot_id, ctx.objective)
    plan_legs.append(return_leg)
    plan_stops.append(return_depot_stop(...))

    # ---- 4. 道路序列拼接 + 累加 totals + 构造 RoutePlan -----------------
    road_seq = ctx.path_provider.road_node_sequence(
        tuple(s.node_id for s in plan_stops), ctx.objective)
    # is_feasible = check_feasibility(stops, legs, ...).is_feasible
    return RoutePlan(...)
```

**关键不变量**：

* 每轮都恰好推进到**当前候选中最优**的一站；
* URGENT 仅决定扫描顺序，不绕过容量 / 时间窗硬约束；
* 闭合段（回归仓库）的 `PathResult` 同样来自 PathProvider，复用同一份 Dijkstra。

---

## 五、复杂度分析

设：

* $V$ = 节点数，$E$ = 边数；
* $K$ = 最终路线配送站数（$K \le M$，M = 候选订单总数）；
* $M$ = 候选订单数。

### 5.1 主操作计数

| 操作 | 每次 | 调用次数 | 累计 |
| --- | --- | --- | --- |
| 全扫描 `remaining` | O(M) | 每轮一次 | O(M²) |
| `shortest_path(main)` | O((V+E) log V) 未命中；O(1) 命中 | 每候选每轮 1 次 | O(M · ((V+E) log V)) |
| `shortest_path(time)` | 同上 | 每候选每轮 1 次 | O(M · ((V+E) log V)) |
| 时间传播 / stop 构造 | O(1) | 每轮 1 次 | O(K) |
| 闭合段路径查询 | O((V+E) log V) | 1 次 | O((V+E) log V) |
| `check_feasibility` | O(K) | 1 次 | O(K) |
| 道路序列拼接 | O(L) | 1 次 | O(L) |

**总时间**：O(M · ((V + E) log V)) —— 主项是 Dijkstra 调用；M² 上界在实际场景
中远未触顶（多数候选在 M 小规模内被剪枝）。

**辅助空间**：

* `plan_stops / plan_legs / remaining` —— O(K + M)；
* `PathProvider` 缓存 —— O(K²)（同一对 stop 反复出现）；
* **合计 O(K + M + V + E)** —— 与图邻接表存储 O(V+E) 同量级。

### 5.2 与朴素实现的对比

| 候选集合 | 取最小 | 主项 | 总时间 |
| --- | --- | --- | --- |
| 每轮全扫描 + 不缓存 | O(M) | M² · Dijkstra | O(M · ((V+E) log V)) |
| **本项目（带缓存）** | O(M) | M · 命中摊销 O(1) | **O(M · ((V+E) log V))** |
| 优先队列候选 | O(log M) | M · log M · Dijkstra | O(M · log M · ((V+E) log V)) |

**实际收益**：同一对 `(current_node, order.destination_id, metric)` 在 NN 主循环
中频繁出现，PathProvider 的 O(1) 摊销查找把"主项"压缩到 M · Dijkstra 而非
M² · Dijkstra。

---

## 六、正确性论证

### 6.1 终止性

* `while remaining` 每轮必然 `pop` 一个订单（若 `best is None` 则 break）；
* `remaining` 长度严格单调下降；
* **必然在至多 M 轮后终止**。✓

### 6.2 站点序列单调

* 每轮最多追加 1 个客户站 + 1 个返回仓库站；
* `plan_stops[0] = depot`、`plan_stops[-1] = depot`（闭合段在循环外追加）；
* 序列下标单调递增，无重复。✓

### 6.3 容量与时间窗硬约束

* 每轮推进前已校验 `current_load + order.demand ≤ capacity + ε`；
* 每轮推进前已校验 `service_start ≤ order.time_window_end + ε`；
* `current_load` 单调累加、单调不超过 `capacity`，即每站都满足硬约束；
* 闭合段不需要重新校验（路径可达性已由 `return_leg.reachable` 保证）。✓

### 6.4 确定性

* `remaining` 排序键 `(priority_rank, id)` 字典序确定；
* tie-break 键 `(leg_main.total_weight, order.id, len(leg_main.path))` 字典序确定；
* 浮点容差 `_TOL = 1e-9` 固定；
* 同输入、同场景下输出必然相同。✓

### 6.5 可达性

* 任何 leg 不可达（`leg.reachable is False`）→ 跳过该候选，不进入 `best`；
* 闭合段不可达 → `RoutePlan.__post_init__` 拒绝构造，planner 上抛
  `InfeasibleSeedError` 或 unserved 标记。

---

## 七、API 设计

### 7.1 `nearest_neighbor(ctx, eligible_orders) -> RoutePlan`

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `ctx` | `PlanningContext` | 调度作用域上下文（不可变） |
| `eligible_orders` | `list[Order]` | 候选订单列表（已通过订单层校验） |

返回：闭合 `RoutePlan`，含 `served_order_ids / is_feasible / totals / legs / stops`。
**不**含 `unserved_orders`（由 `planner` 层通过 `eligible - served` 推导）。

### 7.2 异常与边界

| 边界 | 行为 |
| --- | --- |
| `eligible_orders == []` | 主循环立刻退出，返回 `(depot, depot)` 空路线 |
| 所有候选均不可行 | `break`，剩余订单由 `planner` 标 `no_feasible_next_step` |
| 闭合段不可达 | `RoutePlan.__post_init__` 抛 `ValueError`（planner 捕获后映射为 unserved） |
| `plan_stops` 长度 < 2 | `RoutePlan.__post_init__` 抛 `ValueError`（schema 不变量） |

### 7.3 主目标 / 对比列分离

| 字段 | 取值口径 |
| --- | --- |
| `total_distance` | `objective == "distance"` 时为 `sum(leg.total_weight)`；否则为 `sum(leg.cross_metrics["distance"])` |
| `total_cost` | `objective == "cost"` 时为 `sum(leg.total_weight)`；否则为 `sum(leg.cross_metrics["cost"])` |
| `total_travel_time` | 永远为 `sum(leg.cross_metrics["travel_time"])` —— 与时间传播口径一致 |
| `main_objective_total` | 对应主目标列；与 `RoutePlan.__post_init__` 第 5 项校验联动 |

---

## 八、与 Phase 2 Dijkstra 的接口

### 8.1 调用契约

* NN 在主循环每轮对**每个候选**调 `ctx.path_provider.shortest_path` 两次：

  * `shortest_path(current_node, order.destination_id, ctx.objective)`
  * `shortest_path(current_node, order.destination_id, "travel_time")`

* 闭合段调 `path_provider.shortest_path(current_node, ctx.depot_id, ctx.objective)` 一次；
* 道路序列拼接调 `path_provider.road_node_sequence(stops, ctx.objective)` 一次。

### 8.2 缓存口径

| 场景 | 行为 |
| --- | --- |
| `source == target` | 走零权快捷路径，不入缓存 |
| 命中 | O(1) 返回引用，`cache_hits++` |
| 未命中且可达 | 调 Dijkstra，结果入缓存，`cache_misses++` `dijkstra_calls++` |
| 未命中且不可达 | 调 Dijkstra，结果**不**入缓存（避免负缓存污染） |

### 8.3 拒绝重复实现

NN 不持有任何"自己算的"路径；所有 leg 必须来自 `ctx.path_provider`。
这保证：

* 调度缓存与 Phase 2 Dijkstra 缓存口径统一（用同一份 Dijkstra）；
* 后续 2-opt 反转段后重建 leg 也走同一路径来源，避免策略间口径漂移。

---

## 九、代码索引

| 概念 | 文件 | 行号 |
| --- | --- | --- |
| `nearest_neighbor` 主循环 | `src/logiroute/scheduling/algorithms/nearest_neighbor.py` | 全文 |
| 稳定排序 `(priority, id)` | 同上 | `_PRIORITY_RANK` / 初始化段 |
| 容量 / 时间窗硬约束 | 同上 | 主循环 for-order 段 |
| tie-break 三元组 | 同上 | `key = (leg_main.total_weight, order.id, len(leg_main.path))` |
| 闭合段 + 道路序列拼接 | 同上 | 循环外 |
| `RoutePlan` 装配 / `is_feasible` | 同上 | `check_feasibility` 调用段 |
| 与 `planner` 的契约（`unserved` 上提） | `src/logiroute/scheduling/planner.py` | `_unserved_for_nn` |
| PathProvider 接口 | `src/logiroute/scheduling/path_provider.py` | `shortest_path / road_node_sequence` |
| 单元测试 | `tests/test_scheduling_nearest_neighbor.py` / `tests/test_scheduling_planner.py` | 全部用例 |