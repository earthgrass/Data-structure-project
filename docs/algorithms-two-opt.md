# 受约束 2-opt 局部搜索 —— Phase 3 算法文档

> 本文档是 `src/logiroute/scheduling/algorithms/two_opt.py` 的课程教学材料。
> 配套测试：`tests/test_scheduling_two_opt.py`、`tests/test_scheduling_planner.py`。

---

## 一、问题定义

同 `nearest_neighbor` / `insertion` 的单车闭合调度问题（见
`algorithms-nearest-neighbor.md` §一、`algorithms-insertion.md` §一）：

* 单车辆从出发仓库 $d$ 出发遍历所有待配送订单后**返回** $d$；
* 容量 / 时间窗 / 可达性硬约束同 NN / CFI；
* 主目标 `distance` / `cost` 二选一，行驶时间仅作对比列（AGENTS §3.7）。

**与 NN/CFI 的差异**：2-opt 是**局部搜索**，从一个**已可行的种子路线**
出发，反复对内层配送站子段做反转，直到主目标不再下降为止；**不**增加订单、
**不**减少订单，只重排订单访问顺序。

---

## 二、为什么需要 2-opt？

NN / CFI 都是**构造式**算法，从空集合开始逐步增加订单。其结构性偏差：

| 偏差 | 说明 |
| --- | --- |
| 早期决策锁定 | NN 一旦选错首单就回不去 |
| 缺乏跨段调整 | CFI 不会主动重排已插入订单 |
| 局部极小值 | 容易陷局部最优 |

2-opt 的改进：

* 反转某段子路径 `s[i+1 : j+1]`（`1 ≤ i < j ≤ K`），depot 端点永不参与反转；
* 重新计算反转后的主目标；严格变好才接受（first-improvement 策略）；
* 反复扫描，直到整轮无改善或达到扫描上限。

**计算代价**：2-opt 内部需要**真正重建 leg**——图为有向、三 metric 不一致，
不可套无向 Δ 公式。这意味着每次 trial 都需要 K 段 Dijkstra 调用。

---

## 三、核心数据结构

### 3.1 `plan_seed: RoutePlan`

| 项 | 内容 |
| --- | --- |
| 作用 | 局部搜索的起点（来自 NN / CFI） |
| schema | 闭合、`is_feasible=True`、含 K ≥ 2 个配送站 |

### 3.2 `current_stop_seq: tuple[str, ...]`

| 项 | 内容 |
| --- | --- |
| 作用 | 当前路线的**站点序列**（K+2，含首尾 depot） |
| 形态 | `(depot, s1, s2, ..., sK, depot)` |
| 索引 | depot 端点固定在 0 和 K+1；内层配送站位于 1..K |

### 3.3 `current_legs: tuple[PathResult, ...]`

| 项 | 内容 |
| --- | --- |
| 作用 | 当前路线对应的相邻 leg（K+1 条，来自 PathProvider） |
| 更新 | 接受新候选后整体替换（不能"差分"更新——有向多 metric 无差分元） |

### 3.4 `current_total: float`

| 项 | 内容 |
| --- | --- |
| 作用 | 当前路线的**主目标累计** |
| 度量 | `sum(leg.total_weight for leg in current_legs)` |
| 比较 | 任何 `new_total < current_total - ε` 即视为严格改善 |

### 3.5 `iterations_done: int`

* 每次往返统计到一次"内层双重循环完整扫描"；
* 写入 `RoutePlan.notes['iterations']`，供 `PlanningStats.iterations` 读取。

---

## 四、算法骨架

```python
def constrained_two_opt(plan_seed, ctx):
    # ---- 硬规则：拒绝不可行种子 ----------------------------------------
    if not plan_seed.is_feasible:
        raise InfeasibleSeedError(...)

    stop_seq = plan_seed.stop_sequence
    K = len(stop_seq) - 2
    iter_cap = K * K                          # 扫描轮上限

    # K < 2 → 2-opt 无意义，直接重填
    if K < 2:
        return _route_plan_from_state(...)

    pp = ctx.path_provider
    current_stop_seq = stop_seq
    current_legs = tuple(plan_seed.legs)
    current_total = float(plan_seed.main_objective_total)
    current_stops = plan_seed.stops
    iterations_done = 0
    improved = True

    while improved and iterations_done < iter_cap:
        improved = False
        iterations_done += 1

        for i in range(K):                    # 0..K-1；首个客户也可参与反转
            for j in range(i + 1, K + 1):     # i+1..K
                # ---- 反转段 stop_seq[i+1 : j+1] -------------------------
                candidate = (
                    current_stop_seq[: i + 1]
                    + tuple(reversed(current_stop_seq[i + 1 : j + 1]))
                    + current_stop_seq[j + 1 :]
                )
                candidate_order_ids = (
                    tuple(s.order_id for s in current_stops[: i + 1])
                    + tuple(s.order_id for s in reversed(current_stops[i + 1 : j + 1]))
                    + tuple(s.order_id for s in current_stops[j + 1 :])
                )

                # ---- 重建 leg（必须！有向 + 多 metric） -------------------
                cand_legs_list = pp.all_pairs(candidate, ctx.objective)
                if any(not leg.reachable for leg in cand_legs_list):
                    continue
                cand_legs = tuple(cand_legs_list)
                cand_stops = _rebuild_stops_with_timing(
                    candidate, candidate_order_ids, cand_legs, ctx
                )

                # ---- 可行性 + 主目标评估 --------------------------------
                if not check_feasibility(
                    cand_stops, cand_legs, ctx.capacity,
                    ctx.service_time, ctx.initial_time, ctx.depot_id,
                ).is_feasible:
                    continue

                cand_total = _main_total(cand_stops, cand_legs, ctx.objective)
                if cand_total < current_total - _EPS:
                    current_stop_seq = candidate
                    current_stops  = cand_stops
                    current_legs   = cand_legs
                    current_total  = cand_total
                    improved = True
                    break               # first-improvement：跳出内层
            if improved:
                break                  # first-improvement：跳出外层

    return _route_plan_from_state(
        stop_seq=current_stop_seq,
        legs=current_legs,
        stops=current_stops,
        total=current_total,
        iterations_done=iterations_done,
        ctx=ctx,
    )
```

**关键策略**：

* **first-improvement** —— 找到首个严格改善立即接受并重启外层；
* **订单身份不丢失** —— 反转时同时移动订单 ID；同一配送节点的多个订单仍各自计数；
* **plateau 检测** —— 整轮无改善即 `improved=False`，主循环退出；
* **iter 上限** —— `iter_cap = K * K`，防止极端退化输入下无限循环。

---

## 五、复杂度分析

设：

* $V$ = 节点数，$E$ = 边数；
* $K$ = 当前路线内层配送站数（`K = len(stop_seq) - 2`）；
* `iter_cap` = `K²`（默认扫描轮上限）。

### 5.1 主操作计数

| 操作 | 每次 | 调用次数 | 累计 |
| --- | --- | --- | --- |
| `(i, j)` 双重循环 | O(K²) | 每轮 1 次 | O(K²) |
| 重建 leg（all_pairs） | O(K · ((V+E) log V)) | 每 trial 1 次 | O(K³ · ((V+E) log V)) |
| `_rebuild_stops_with_timing` | O(K) | 每 trial 1 次 | O(K³) |
| `check_feasibility` | O(K) | 每 trial 1 次 | O(K³) |
| 主目标比较 | O(1) | 每 trial 1 次 | O(K²) |

**总时间**：每轮最多 K² 个候选、每候选最多 K 条 leg、最多 K² 轮；
保守上界 O(K⁵ · ((V+E) log V))。可达站点对命中缓存时，重复查询为 O(1)。

但**实际平均**由于 first-improvement 提前退出 + plateau 检测，绝大多数轮次
提前终止；课程实测在 K=10 ~ 20 范围内 2-opt 主项 ~K³ · Dijkstra。

**辅助空间**：

* trial 候选（`candidate / cand_legs / cand_stops`）—— O(K + L)；
* PathProvider 缓存 —— O(K²)（在内部反复反转后）；
* **合计 O(K² + L + V + E)**，含单次调度的路径缓存。

### 5.2 与 NN / CFI 的对比

| 维度 | NN | CFI | 2-opt |
| --- | --- | --- | --- |
| 时间上界 | O(M² · ((V+E) log V)) | O(M · K² · ((V+E) log V)) | O(K⁵ · ((V+E) log V)) |
| 解的质量 | 贪心基线 | 不保证优于 NN | 对给定种子只接受严格改善 |
| 单调可行性 | 构造中保证 | 构造中保证 | **接受候选** 才允许（拒绝 `is_feasible=False` 种子） |
| 是否新增订单 | 是 | 是 | 否 |

---

## 六、正确性论证

### 6.1 终止性

* `iterations_done` 单调递增；
* 主循环条件 `iterations_done < iter_cap` 强制上界；
* `improved=False` 时主循环退出；
* **必然在有限步内终止**。✓

### 6.2 硬规则：拒绝不可行种子

* 入参 `plan_seed.is_feasible is False` → 立即抛 `InfeasibleSeedError`；
* **不**调 Dijkstra，避免无谓计算；
* 2-opt 不构造新种子；只能改进已有可行路线。

### 6.3 接受候选的可行性不变量

* 每个 candidate 都先重建 leg、再过 `check_feasibility`；
* `check_feasibility` 不通过 → `continue`，**不**进入 `current_*` ；
* 因此**最终 `RoutePlan.is_feasible == True`**。✓

### 6.4 主目标单调不增

* 只在 `cand_total < current_total - _EPS` 时才接受候选；
* `_EPS = 1e-9` 避免浮点抖动造成的伪反复；
* `current_total` 单调不增 → 主循环在有限步后必收敛。✓

### 6.5 显式拒绝无向 Δ 公式

* 无向图 Δ 公式：$\Delta = d(i,j) + d(i+1,j+1) - d(i,i+1) - d(j,j+1)$；
* 本图**有向**：$d(i,j) \neq d(j,i)$；三 metric 不一致：同一对 stop 在
  `distance` / `cost` 下两个分数不同；
* Δ 公式会把三 metric 偷换成一个数，违反 AGENTS §3.7；
* **必须每次真正重建 leg**，由 `PathProvider.all_pairs` 提供。✓

### 6.6 闭合不变量

* 反转操作只发生在 `stop_seq[1 : K+1]`（内层配送站），depot 端点永不参与；
* 因此 `stop_seq[0] == stop_seq[-1] == depot_id` 始终成立。✓

### 6.7 plateau 与 iter 上限

* plateau（一轮无改善）→ 主循环退出，结果对应**当前最优**解；
* iter 上限（退化情形）→ 主循环退出，结果**不**保证最优，但有明确上界；
* `iterations_done` 写入 `notes`，便于诊断退化情形。

---

## 七、API 设计

### 7.1 `constrained_two_opt(plan_seed, ctx) -> RoutePlan`

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `plan_seed` | `RoutePlan` | NN / CFI 产出的可行闭合路线 |
| `ctx` | `PlanningContext` | 调度作用域上下文（不可变） |

返回：闭合 `RoutePlan`，`is_feasible=True`，`main_objective_total` 不大于种子；
`notes["iterations"]` 记录实际完成的扫描轮数。

### 7.2 异常

| 异常 | 触发 |
| --- | --- |
| `InfeasibleSeedError` | `plan_seed.is_feasible is False`（硬规则） |

### 7.3 边界

| 边界 | 行为 |
| --- | --- |
| `K < 2` | 短路返回：以种子为基础重新填充 `RoadNodeSequence / total_* / notes["iterations"] = 1` 后直接返回 |
| 所有反转均被拒 | `improved` 全程 `False`，主循环在 1 次扫描后退出 |
| iter 上限触发 | 退出；结果对应**当前最优**，但不一定全局最优 |

### 7.4 与 planner 的契约

* `planner` 先用 `nearest_neighbor` 构造 seed，再调 `constrained_two_opt`；
* 2-opt 不增加订单，**沿用** NN 的 `unserved`（`no_feasible_next_step`）；
* `iterations` 自 `RoutePlan.notes["iterations"]` 读取，写入 `PlanningStats`。

---

## 八、与 Phase 2 Dijkstra 的接口

### 8.1 调用契约

* 每次 candidate 重建 leg 都调 `ctx.path_provider.all_pairs(candidate, ctx.objective)`；
* `all_pairs` 内部对每对相邻站点调 `shortest_path`，自动复用 PathProvider 缓存；
* 不调 `travel_time` 维度（2-opt 只在主目标维度评估改善），
  但 `_rebuild_stops_with_timing` 通过 `leg.cross_metrics['travel_time']`
  读行驶时间，与 NN / CFI 口径一致。

### 8.2 缓存复用

| 场景 | 行为 |
| --- | --- |
| 反转前后多数相邻站点对路径未变 | 缓存命中，`cache_hits++` |
| 反转引入新相邻对 | 缓存未命中，调 Dijkstra，结果入缓存（仅可达） |

### 8.3 拒绝重复实现

* 2-opt 不持有任何"自己算的"路径；
* 所有 leg 必须来自 `ctx.path_provider`；
* 禁止在 2-opt 内重写最短路径子例程（AGENTS §3.5、§3.7）；
* 这是"同一份 Dijkstra"硬约束的最终防线。

---

## 九、代码索引

| 概念 | 文件 | 行号 |
| --- | --- | --- |
| `constrained_two_opt` 主入口 | `src/logiroute/scheduling/algorithms/two_opt.py` | 全文 |
| 硬规则：拒绝不可行种子 | 同上 | `InfeasibleSeedError` 抛出段 |
| K < 2 短路 | 同上 | 入口段 |
| 反转段 + first-improvement 主循环 | 同上 | while 段 |
| `_rebuild_stops_with_timing`（时间传播） | 同上 | 函数体 |
| `_main_total`（主目标累加） | 同上 | 函数体 |
| `_route_plan_from_state`（最终组装） | 同上 | 函数体 |
| 与 `planner` 的契约（seed → 2-opt） | `src/logiroute/scheduling/planner.py` | `nearest_neighbor` + `constrained_two_opt` 调用段 |
| PathProvider 接口 | `src/logiroute/scheduling/path_provider.py` | `shortest_path / all_pairs / road_node_sequence` |
| 单元测试 | `tests/test_scheduling_two_opt.py` / `tests/test_scheduling_planner.py` | 全部用例 |
