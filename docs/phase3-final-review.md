# LogiRoute — Phase 3 最终验收报告

> 报告日期：2026-10-16  
> 阶段：Phase 3 — 单车辆闭环调度（NN / CFI / 受约束 2-opt + PathProvider）  
> 工作模式：自动化执行（设计 → 实现 → 测试 → 文档 → 演示 → 验收）

---

## A. 开发完成情况

### A.1 新增类 / 函数

| 名称 | 类别 | 位置 | 行数 |
| --- | --- | --- | --- |
| `DeliveryStop` / `RoutePlan` / `ScheduleResult` | 不可变结果 dataclass | `src/logiroute/scheduling/types.py` | 118–292 |
| `Violation` / `FeasibilityReport` / `PlanningStats` | 不可变报告 dataclass | 同上 | 88–365 |
| `PlanningContext` | 不可变调度作用域上下文 | 同上 | 429–464 |
| `PlanningError` + 6 子类 | 错误体系 | 同上 | 38–66 |
| `PathProvider` | Dijkstra 封装 + 单调度作用域缓存 | `src/logiroute/scheduling/path_provider.py` | 40–200 |
| `graph_identity` | 图指纹工具（缓存键前缀） | `src/logiroute/scheduling/graph_identity.py` | 31–63 |
| `check_feasibility` | 闭环硬约束纯函数 | `src/logiroute/scheduling/feasibility.py` | 74–227 |
| `_leg_drive_time` | 行驶时间口径辅助 | 同上 | 57–71 |
| `DepotChoice` / `select_depot` | 仓库 + 车辆 + 配送员选择 | `src/logiroute/scheduling/depot.py` | 28–114 |
| `nearest_neighbor` | NN 基线构造 | `src/logiroute/scheduling/algorithms/nearest_neighbor.py` | 67–285 |
| `cheapest_feasible_insertion` | CFI 调度 | `src/logiroute/scheduling/algorithms/insertion.py` | 541–696 |
| `_TourState` / `_try_insert` / `_first_feasible_seed` | CFI 内部状态机与种子 | 同上 | 64–346 |
| `constrained_two_opt` | 受约束 2-opt 局部搜索 | `src/logiroute/scheduling/algorithms/two_opt.py` | 290–397 |
| `plan_deliveries` + `_filter_eligible` + `_finalize_result` | 统一入口 | `src/logiroute/scheduling/planner.py` | 54–401 |

### A.2 新增方法

| 方法 | 复杂度 | 备注 |
| --- | --- | --- |
| `PathProvider.shortest_path` | 命中 O(1) / 未命中 O((V + E) log V) | 不写负缓存；`source == target` 零权快捷路径不入缓存 |
| `PathProvider.all_pairs` | O(K · (V + E) log V)（摊销 O(1)/leg） | 批量查相邻 leg |
| `PathProvider.road_node_sequence` | O(L)（L = 拼接后节点数） | 拼接 + 去相邻重复 |
| `PathProvider.stats` | O(1) | 计数器快照 |
| `graph_identity` | O(V + E) | 插入有序 dict 迭代，无 `sorted()` |
| `check_feasibility` | O(K) | 五项硬约束纯函数 |
| `select_depot` | O(V + 车辆数) | lex-min 确定性 |
| `nearest_neighbor` | O(K · (V + E) log V) | 全扫描 + 每候选 1~2 次 Dijkstra |
| `cheapest_feasible_insertion` | O(M · K² · (V + E) log V) | M = 候选订单总数，K = 当前路线站数 |
| `constrained_two_opt` | O(K² · K · (V + E) log V) | first-improvement + `iter_cap = K²` |
| `_first_feasible_seed` | O(M · (V + E) log V + M²) | 手写插入排序 URGENT 优先 + id 升序 |
| `_try_insert` | O(K · (V + E) log V) | 单 order × all pos 枚举 |
| `plan_deliveries` | 取决于算法 | 校验 + 装配 + 计时 |

### A.3 新增算法

| 算法 | 时间 | 空间 | 自主实现 |
| --- | --- | --- | --- |
| Nearest-Neighbor 基线构造 | O(K · ((V + E) log V)) | O(K + E) | ✅ 全部手写 |
| Cheapest Feasible Insertion（CFI） | O(M · K² · ((V + E) log V)) | O(K + (V + E)) | ✅ 全部手写（含手写插入排序种子选择） |
| 受约束 2-opt 局部搜索（first-improvement） | O(K³ · (V + E) log V) | O(K) | ✅ 全部手写；不套无向 Δ 公式，真正重建 leg |
| 图指纹（缓存键前缀） | O(V + E) | O(V + E) | ✅ 不调 `sorted()` / `heapq` |
| 单调度作用域缓存策略 | O(1) 查询 + O(V + E) 失效检测 | O(K) | ✅ 不写负缓存 |
| 可行性硬约束纯函数 | O(K) | O(K) | ✅ 纯函数（不读写全局） |

### A.4 使用的数据结构

| 概念 | 实际存储 | 证据 |
| --- | --- | --- |
| PathProvider 缓存 | Python `dict[tuple, PathResult]` | `path_provider.py:_cache` |
| 路径计数器 | Python `int`（`__slots__` 字段） | `path_provider.py:__slots__` |
| `_TourState` 站点序列 | `tuple[_StopInfo, ...]`（不可变） | `insertion.py:_TourState.stop_infos` |
| 候选插入临时集合 | `list[Order]` + `list[_StopInfo]` | `insertion.py:remaining / trial_infos` |
| RoutePlan / DeliveryStop 等 | 全部 `@dataclass(frozen=True)` | `types.py` |
| 订单回查索引（CFI / 2-opt） | `dict[str, Order]` | `two_opt.py:order_by_dest` |
| Dijkstra 复用 | Phase 2 `shortest_path` + `MinHeap` | `path_provider.py:31-35` |
| 内部确定性扫描 | 手写插入排序（URGENT 优先 + id ASC） | `insertion.py:_first_feasible_seed` |

### A.5 实际源码路径

| 模块 | 路径 |
| --- | --- |
| 调度统一入口 | `src/logiroute/scheduling/planner.py` |
| 数据类型 | `src/logiroute/scheduling/types.py` |
| 路径缓存 | `src/logiroute/scheduling/path_provider.py` |
| 图指纹 | `src/logiroute/scheduling/graph_identity.py` |
| 可行性检查 | `src/logiroute/scheduling/feasibility.py` |
| 仓库 / 车辆选择 | `src/logiroute/scheduling/depot.py` |
| NN 算法 | `src/logiroute/scheduling/algorithms/nearest_neighbor.py` |
| CFI 算法 | `src/logiroute/scheduling/algorithms/insertion.py` |
| 2-opt 算法 | `src/logiroute/scheduling/algorithms/two_opt.py` |
| 算法包初始化 | `src/logiroute/scheduling/algorithms/__init__.py` |
| 调度包初始化 | `src/logiroute/scheduling/__init__.py` |
| types 测试 | `tests/test_scheduling_types.py`（32 用例） |
| path_provider 测试 | `tests/test_scheduling_path_provider.py`（21 用例） |
| feasibility 测试 | `tests/test_scheduling_feasibility.py`（16 用例） |
| NN 测试 | `tests/test_scheduling_nearest_neighbor.py`（23 用例） |
| CFI 测试 | `tests/test_scheduling_insertion.py`（14 用例） |
| 2-opt 测试 | `tests/test_scheduling_two_opt.py`（18 用例） |
| plan_deliveries 测试 | `tests/test_scheduling_planner.py`（16 用例） |
| Phase 3 演示 | `scripts/demo_phase3.py` |
| 固定场景 | `config/scenario.json` |

---

## B. 数据类型与 dataclass 设计

### B.1 总体约束

* 全部公开类型均为 `@dataclass`；关键类型（`DeliveryStop` / `RoutePlan` / `ScheduleResult` / `Violation` / `FeasibilityReport` / `PlanningStats` / `PlanningContext`）追加 `frozen=True`，构造后不可变，确保 Hash 安全；
* 所有公开字段带类型注解；`from __future__ import annotations` 启用前向引用；
* `__post_init__` 校验闭回路 / 长度 / 可达性 / 时间数值 / 容量 / 优先级枚举等不变量；**任何构造期失败抛 `ValueError`**；
* 所有结果类型提供 `to_dict()` / `asdict()`，输出可被 `json.dumps` 直接序列化（Phase 5+ Dashboard 直接消费）。

### B.2 主要类型

| 类型 | 性质 | 关键职责 | 行号 |
| --- | --- | --- | --- |
| `DeliveryStop` | `frozen=True` | 单个 stop（仓库 / 客户）的事件快照；含 `arrival_time` / `service_start` / `service_end` / `waiting_time` / `cumulative_load` / `time_window_*` | `types.py:118–171` |
| `RoutePlan` | `frozen=True` | 单车闭合配送回路；校验 `len(stops)==len(stops_sequence)` / `len(legs)==len(stops_sequence)-1` / 全部 leg `reachable` / 主目标一致性 / `stop_sequence[0]==[-1]==depot_id`；`notes` 供 CFI 写 unserved | `types.py:179–292` |
| `ScheduleResult` | `frozen=True` | 单次 `plan_deliveries` 完整输出；`is_feasible=False` 强制当 `unserved_orders` 非空（防"伪造 100%"） | `types.py:373–421` |
| `Violation` | `frozen=True` | 单条不可行记录；`kind` 必须在 `VIOLATION_KINDS` 白名单内（`capacity_overflow` / `time_window_miss` / `unreachable_leg` / `return_unreachable` / `service_time_overflow` / `depot_mismatch` / `no_feasible_next_step` / `no_feasible_insertion` / `infeasible_seed`） | `types.py:88–111` |
| `FeasibilityReport` | `frozen=True` | `check_feasibility` 输出；`is_feasible=True` 与非空 `violations` 互斥 | `types.py:300–321` |
| `PlanningStats` | `frozen=True` | 调度计数器（`cache_hits` / `cache_misses` / `dijkstra_calls` / `paths_evaluated` / `feasibility_checks` / `iterations` / `runtime_seconds`），全为非负 | `types.py:329–365` |
| `PlanningContext` | `frozen=True` | 调度作用域内部上下文；**不在 `__all__`**；外部访问应通过 `ScheduleResult` 或显式参数 | `types.py:429–464` |
| `PlanningError` + 6 子类 | `Exception` | `NoAvailableVehicleError` / `EmptyOrdersError` / `UnknownAlgorithmError` / `InvalidObjectiveError` / `DepotNotFoundError` / `InfeasibleSeedError` | `types.py:38–66` |

### B.3 设计要点

* `DeliveryStop.is_depot_stop = (order_id is None)`，构造期强制 `demand == 0.0` 且 `time_window_*` 为 `None`；
* `RoutePlan.__post_init__` 拒绝任何不可达 leg 注入 —— 直接抛 `ValueError`；
* `ScheduleResult.__post_init__` 在 `is_feasible=True` 同时 `unserved_orders` 非空时强制改回 `False`，确保"路线可行 ≠ 全服务"的语义边界；
* `PlanningContext` 不在 `__all__` 导出，避免被外部 `import` 绕过不变量；
* `to_dict()` 对 `legs` 通过 `getattr` 读取 `source / target / metric / path / total_weight / reachable / cross_metrics` 七个字段，无循环导入风险。

---

## C. PathProvider 设计

### C.1 缓存键

```
key = (graph_version, source, target, metric)
```

* `graph_version` 由 `graph_identity(graph)` 一次性快照（`id(graph)`, `tuple(graph.node_ids)`, `edge_count`, `(source, target, d, t, c, traffic) 元组序列`）；
* 节点 / 边 / 边权变化后 `_graph_id` 立即不同，旧图查询不会误命中新图的缓存键空间。

### C.2 三条核心规则

| 规则 | 实现 | 行号 |
| --- | --- | --- |
| **不写负缓存** | 仅当 `result.reachable is True` 时写入 `_cache[key]`；不可达结果每次重新调 Dijkstra | `path_provider.py:127–128` |
| **`source == target` 快捷路径** | 返回零权 `PathResult`，**不入缓存**，**不调 Dijkstra**，`paths_evaluated += 1` | `path_provider.py:102–112` |
| **缓存键变化即失效** | `graph_identity` 把图身份与所有边权打包进元组 | `graph_identity.py:31–63` |

### C.3 公开计数器

| 字段 | 含义 | 行号 |
| --- | --- | --- |
| `cache_hits` | 缓存命中次数 | `path_provider.py:67` |
| `cache_misses` | 缓存未命中次数 | `path_provider.py:68` |
| `dijkstra_calls` | 实际调用 Dijkstra 的次数 | `path_provider.py:69` |
| `paths_evaluated` | 所有 `shortest_path` 调用成功（含缓存命中 + 未命中 + `source == target` + 不可达） | `path_provider.py:70` |
| `stats()` | O(1) 返回四字段 `dict` | `path_provider.py:189–200` |

### C.4 图指纹的"为何不用 `sorted()`"

`graph_identity` 故意利用 `LogisticsGraph` 内部插入有序 dict 的迭代顺序（`graph.node_ids` + `get_out_edges(src)`），不调任何排序工具 —— 遵守 AGENTS §2.1 禁表 + "更严标准"。

---

## D. 可行性检查器

### D.1 五条硬约束

| # | 约束 | 触发 Violation kind | 行号 |
| --- | --- | --- | --- |
| 1 | 每条 leg 必须可达（最后一条 leg 不可达用 `return_unreachable` 特例） | `unreachable_leg` / `return_unreachable` | `feasibility.py:121–139` |
| 2 | 首尾 `DeliveryStop.node_id == depot_id` | `depot_mismatch` | `feasibility.py:142–163` |
| 3 | `cumulative_load ≤ capacity` | `capacity_overflow` | `feasibility.py:166–179` |
| 4 | `service_start ≤ time_window_end`（AGENTS §3.7 本阶段不强制 `service_end ≤ window_end`） | `time_window_miss` | `feasibility.py:184–199` |
| 5 | `service_end == service_start + service_time`（仅 `order_id is not None` 的客户站） | `service_time_overflow` | `feasibility.py:204–222` |

### D.2 AGENTS §3.7 service_end 例外

> **本阶段**仅要求 `service_start ≤ time_window_end`；`service_end` 越界**不**视为违反，由后续可配置策略决定。本模块不强加此语义，避免偷偷修改规划语义（见 `types.py:22–25`）。

### D.3 行驶时间口径

* `arrival_time[i+1] = service_end[i] + drive_time`，`drive_time` **必须**取 `leg.cross_metrics['travel_time']`（≠ `leg.total_weight`）；
* 避免主目标（`distance` / `cost`）所选路径被错当行驶时间；
* `_leg_drive_time(leg)` 提供统一工具：`cross_metrics['travel_time']` 优先，否则回退到 `total_weight`（`feasibility.py:57–71`）。

### D.4 纯函数 + 幂等

* `check_feasibility` 不修改任何入参，不读写全局状态；
* 同一 `stops/legs` 调用任意次结果相同；
* Time：O(K)（K = stops 数）；Space：O(K) violations 临时数组。

### D.5 行为不变量

| 边界 | 行为 |
| --- | --- |
| `is_feasible=True` 且 `violations=()` | 唯一合法通过态（`FeasibilityReport.__post_init__` 强制） |
| `is_feasible=False` 且 `violations` 非空 | 触发至少一条违反 |
| `len(legs) != len(stops) - 1` | schema 不一致，抛 `ValueError` |
| 仓库 stop（`order_id is None`） | 不参与 capacity / time window / service_time 检查 |

---

## E. NN 算法（nearest_neighbor）

### E.1 算法骨架

1. 初始化 `current_node` / `current_time` / `current_load` 与出发仓库 `DeliveryStop`；
2. `while remaining` 全扫描剩余订单，对每个候选做：
   * 容量可行性（`current_load + demand ≤ capacity`）
   * 主目标路径可达性（`leg_main.reachable`）
   * 时间路径可达性（`leg_time.reachable`）
   * 时间窗硬约束（`service_start ≤ time_window_end`）
   * tie-break `(total_weight, order.id, len(path))`
3. 无任何候选 → 记录 `no_feasible_next_step` 并 `break`；
4. 闭合：append 回归仓库 + 末尾 depot stop；
5. `path_provider.road_node_sequence` 拼接完整道路序列；
6. 累加 `total_*`，调用 `check_feasibility`，构造 `RoutePlan`。

### E.2 tie-break 确定性

```python
key = (leg_main.total_weight, order.id, len(leg_main.path))
if best_key is None or key < best_key:
    best, best_key, best_leg_main, best_leg_time = ...
```

* `total_weight` ASC → 主目标最小优先；
* `order.id` ASC → 同距离时确定性 tie-break；
* `len(path)` ASC → 节点数最少的路径胜出（同一对节点唯一最短路径时无影响）。

### E.3 行驶时间传播口径

* 候选评估 + 路线推进 **都** 使用 `leg_time.cross_metrics['travel_time']`；
* 严禁把主目标所选路径（`distance` / `cost` 模式）的 `total_weight` 当行驶时间 —— 与 `feasibility.py` 口径一致。

### E.4 复杂度

| 维度 | 复杂度 |
| --- | --- |
| 主循环轮数 | ≤ K（K = 入站订单数） |
| 每轮扫描 | O(M) （M = 当前 remaining） |
| 每候选 | 1~2 次 Dijkstra（缓存命中摊到 O(1)） |
| **总时间** | **O(K · ((V + E) log V))** |
| 空间 | O(K + E) |

### E.5 unserved 上报通道

* NN **不**通过 `RoutePlan.notes` 注入 unserved（与 CFI 分离契约）；
* `planner._unserved_for_nn` 通过 `eligible_orders - plan.served_order_ids` 计算 unserved，统一打标 `kind="no_feasible_next_step"`（`planner.py:120–141`）。

---

## F. CFI 算法（cheapest_feasible_insertion）

### F.1 算法骨架

1. **空集合快速返回**：若 `eligible_orders` 为空 → `(depot, depot)` 零服务空路线；
2. **种子选择**：从 `eligible_orders` 筛选"首段可达 + demand ≤ 容量 + 首站 time window 不迟到"的子集；URGENT 优先 + `order.id` ASC 选一个种子；
3. **主循环**：当 `remaining` 非空且当前 plan 可行：
   * 对每个 `order ∈ remaining` 枚举配送站间所有插入位置 `pos ∈ [1, len(plan_stops) - 1)`，调 `_try_insert` 求 "delta_main 最小" 的可行 trial；
   * 若所有 order 均无可行位置 → 把剩余全部作为 `kind="no_feasible_insertion"` 的 `Violation` 收集并退出；
4. **装配 `RoutePlan`**：与 NN 同口径。

### F.2 种子选择实现要点

* `_first_feasible_seed`：O(M · (V + E) log V + M²)；
* **手写插入排序**（URGENT 优先 + id 升序），避免 `sorted()`；
* 无任何合格种子 → 抛 `InfeasibleSeedError`，错误消息列举每个候选的具体失败原因（`insertion.py:601–625`）。

### F.3 cheapness 性质

* 每次插入候选的 `delta = new_main - current_main`，**严格最小**（同 `(delta, order.id, pos)` 时取最小 `pos`）；
* 路径来源全部走 `ctx.path_provider.shortest_path`（缓存命中），禁止重写 Dijkstra；
* 内部 `_TourState` 维护可变路线快照（`stops` / `legs` / `stop_infos` / `served_order_ids`），不破坏 `RoutePlan` 不可变性。

### F.4 复杂度

| 维度 | 复杂度 |
| --- | --- |
| 种子构造 | O(M · (V + E) log V + M²) |
| 主循环轮数 | ≤ M |
| 每轮 all-order × all-pos 扫描 | O(M · K) |
| 每 trial `_try_insert` | O(K · (V + E) log V) |
| **总时间** | **O(M · K² · ((V + E) log V))** |
| 空间 | O(K + (V + E)) |

### F.5 unserved 上报通道

* CFI 通过 `RoutePlan.notes['unserved_orders']` 写 `Violation` 字典列表；
* `planner._lift_unserved_from_notes` 恢复为 `Violation` 列表（`planner.py:101–117`）。

---

## G. 2-opt 算法（constrained_two_opt）

### G.1 硬规则

* **拒绝不可行种子**：传入的 `plan_seed.is_feasible` 必须为 `True`；否则立即抛 `InfeasibleSeedError`，**不**调用 Dijkstra（`two_opt.py:317–323`）；
* **不接受空种子**：若 `len(stop_seq) - 2 < 2`，直接按种子原值重填（K < 2 时反转无意义），保持 `is_feasible=True`（`two_opt.py:330–338`）；
* **不绕过硬约束**：候选 `RoutePlan` 通过 `check_feasibility` 拒绝任何不可行；
* **每次必须真正重建 leg**：`stop_seq[i+1 : j+1]` 反转后，**必须**通过 `ctx.path_provider.all_pairs(candidate, ctx.objective)` 重新拉取全部相邻 leg，再判断是否改善。

### G.2 Δ 公式被有理拒绝

无向图常用的"反向 Δ"公式

```
Δ = d(i,j) + d(i+1,j+1) - d(i,i+1) - d(j,j+1)
```

在本项目**不**适用，理由：

1. **图是有向的** —— 反转后的 leg `(i+1, i)` 与 `(j, j+1)` 不等价于原 leg `(i, i+1)` 或 `(j, j+1)`；
2. **三 metric 不一致** —— `distance` / `travel_time` / `cost` 分别走不同最短路径，`leg.total_weight` 取决于 metric，无单一 Δ 值；
3. **违反 §3.7 多策略对比口径** —— 三个 metric 下 Δ 值不同，强行套用会偷换路径。

为此本模块**真**每次重建 leg 并比对 `cand_total vs current_total`（`two_opt.py:14–16, 296–299`）。

### G.3 iter_cap + plateau

* `iter_cap = K * K`（K = 内层站数，`len(stop_sequence) - 2`）；
* 终止条件：本轮扫描无任何改善 **`OR`** 达到 `iter_cap`（`two_opt.py:350–388`）；
* 防止 2-opt 在 plateau 路线上无限循环；
* 实际扫描轮数写入 `notes["iterations"]`，由 `planner` 装配到 `PlanningStats.iterations`。

### G.4 first-improvement

```python
for i in range(1, K):
    for j in range(i + 1, K + 1):
        candidate = current_stop_seq[: i+1] + reversed([...]) + current_stop_seq[j+1:]
        ...
        if cand_total < current_total - _EPS:
            current_stop_seq = candidate
            ...
            improved = True
            break
    if improved:
        break
```

* `i from 1 to K` / `j from i+1 to K+1`（depot 端点永不参与反转）；
* 找到首个严格改善（`cand_total < current_total - 1e-9`）立即接受，重启外层扫描。

### G.5 复杂度

| 维度 | 复杂度 |
| --- | --- |
| 反转对 | O(K²) |
| 每次重建 leg | O(K · (V + E) log V)（缓存命中摊到 O(K)） |
| 可行性检查 | O(K) / 候选 |
| 最坏层数 | O(K²) |
| **总时间** | **O(K³ · (V + E) log V)** |
| 空间 | O(K) 候选缓存 |

---

## H. 统一入口（plan_deliveries）

### H.1 签名

```python
def plan_deliveries(
    scenario: ScenarioBundle,
    algorithm: str = "nearest_neighbor",
    objective: str = "distance",
    depot_id: str | None = None,
    initial_time: float | None = None,
) -> ScheduleResult
```

* `algorithm` ∈ `{"nearest_neighbor", "insertion", "two_opt"}` —— 白名单校验；
* `objective` ∈ `{"distance", "cost"}` —— **拒绝 `travel_time` 作主目标**（AGENTS §3.7 对比列仅）；
* `depot_id` 显式指定仓库 / `None` 时自动选 lex-min IDLE 车辆所在仓库；
* `initial_time` 为空时回退 `scenario.simulation["initial_time"]`。

### H.2 处理流水线

| # | 步骤 | 行号 |
| --- | --- | --- |
| 1 | 参数白名单校验（`algorithm` / `objective` / `orders`） | `planner.py:202–213` |
| 2 | `select_depot` 自动选仓库 + 车辆 + 配送员 | `planner.py:216` + `depot.py:54–114` |
| 3 | 读取 `service_time` / `initial_time` | `planner.py:220–225` |
| 4 | `_filter_eligible` 剔除明显不可服务订单（记 `unreachable_leg` / `capacity_overflow`） | `planner.py:54–98, 228` |
| 5 | 构造 `PathProvider` + `_FeasibilityCounter` + `PlanningContext` | `planner.py:287–300` |
| 6 | 算法分派（NN / CFI / 2-opt 自身 seed + 2-opt） | `planner.py:303–320` |
| 7 | `_finalize_result` 合并 pre_unserved + extra_unserved，组装 `ScheduleResult` | `planner.py:342–401` |
| 8 | 全局 `is_feasible = plan.is_feasible and len(unserved) == 0` | `planner.py:367, 400` |

### H.3 eligibility filter（预过滤）

`_filter_eligible` 对每个订单做：

| 条件 | 处置 | Violation kind |
| --- | --- | --- |
| `Order.destination_id` 不在 `graph.node_ids` | 拒收 | `unreachable_leg` |
| `Order.demand > max(vehicle.capacity)` | 拒收 | `capacity_overflow` |

* 拒收的订单在 `ScheduleResult.unserved_orders` 顶层出现，由 planner 内部合并；
* `Order.time_window_end <= time_window_start` 已被 `Order.__post_init__` 拦截，加载阶段即失败，此处不重复。

### H.4 unserved-order lifting（提升）

各算法对 unserved 的上报方式：

| 算法 | 上报通道 | planner 提升策略 |
| --- | --- | --- |
| `nearest_neighbor` | 不主动上报 | `eligible_orders - served_order_ids`，`kind="no_feasible_next_step"` |
| `insertion` | `RoutePlan.notes['unserved_orders']` | `_lift_unserved_from_notes` 还原 `Violation` |
| `two_opt` | 沿用种子（NN）的 unserved | `seed_unserved = _unserved_for_nn(...)`；2-opt **不能增加订单** |

### H.5 全局可行性

```python
globally_feasible = plan.is_feasible and not unserved
```

* 仅当路线可行 **且** 全部订单被服务时，`ScheduleResult.is_feasible=True`；
* 即便个别情况下 `RoutePlan.is_feasible=True` 但仍有 unserved，`ScheduleResult` 也会被强制置 `False`（与 `ScheduleResult.__post_init__` 一致）。

---

## I. Phase 3 验收标准

- [x] 单车辆约束（`ScheduleResult.vehicle_id` 仅一辆）
- [x] 闭合回路 `stop_sequence[0] == stop_sequence[-1] == depot_id`
- [x] Dijkstra 来自 Phase 2，调度器未重写第二套最短路径
- [x] `PathProvider` 不写负缓存
- [x] `source == target` 走零权快捷路径，不入缓存
- [x] 时间窗检查在 `service_start ≤ time_window_end` 而非 `service_end`（AGENTS §3.7 例外）
- [x] `cross_metrics` 提供 `travel_time`，调度器不偷换路径时间口径
- [x] NN tie-break 确定性：`(total_weight, order.id, len(path))`
- [x] CFI tie-break 确定性：`(delta, order.id, pos)`
- [x] 2-opt 拒绝不可行种子（`InfeasibleSeedError`）
- [x] 2-opt 不套无向 Δ 公式，真正重建 leg
- [x] 2-opt first-improvement + iter_cap = K²
- [x] 不可达订单通过 `Violation.kind` 明确化（`unreachable_leg` / `capacity_overflow` / `no_feasible_next_step` / `no_feasible_insertion` 等 9 种）
- [x] CFI 种子来自手写插入排序（URGENT 优先 + id ASC），非 `sorted()`
- [x] `_first_feasible_seed` 抛 `InfeasibleSeedError` 时附失败原因
- [x] `RoutePlan` 构造期校验所有 leg `reachable=True`
- [x] `RoutePlan` 强制 `stop_sequence[0]==[-1]==depot_id`
- [x] `RoutePlan.main_objective_total` 与 `objective` 列严格相等
- [x] `ScheduleResult.is_feasible=False` 自动当 `unserved_orders` 非空
- [x] `select_depot` 仅返回一辆 IDLE 车辆（4 辆车模型保留但仅调度一辆）
- [x] `objective="travel_time"` 在 `plan_deliveries` 入口被拒绝（`InvalidObjectiveError`）
- [x] 至少 2 仓库 / ≥ 15 配送点 / ≥ 3 中转 / ≥ 30 节点 / ≥ 50 边（已由 `config/loader` 校验，scenario.json 实际 35 节点 / 192 边）
- [x] 全部公共类型为 frozen dataclass，含 `__post_init__` 不变量
- [x] 全部结果类提供 `to_dict()`，可被 `json.dumps` 序列化
- [x] 调度实例级 PathProvider 缓存自然随调度结束释放（不跨场景串味）
- [x] 图指纹 `graph_identity` 不调 `sorted()` / `heapq`，仅利用插入有序 dict
- [x] `planning_stats.runtime_seconds` 用 `time.monotonic()` 度量
- [x] Phase 3 新增 ≥ 80 个测试用例（实测 140：types 32 + path_provider 21 + feasibility 16 + NN 23 + CFI 14 + 2-opt 18 + planner 16）
- [x] 全套测试通过（实测 364 / 364，耗时 0.984s）
- [x] `scripts/demo_phase3.py` 可执行，覆盖 NN-distance / NN-cost / CFI-distance / 2-opt-distance 四种组合并打三算法对照表
- [x] 不引入 `sorted()` 作为算法核心（CFI 种子用手写插入排序）
- [x] 不引入 `heapq`（堆由 Phase 2 `MinHeap` 单点提供）
- [x] 不引入 `networkx` / `numpy` / `scipy` / `pulp` / `ortools`（第三方依赖数 = 0）
- [x] 不引入 FastAPI / Web 框架 / 数据库
- [x] 实测 20+ 订单 4 算法对照 < 1 秒（实测 < 1ms / 算法）
- [x] Phase 1 / Phase 2 既有测试无回归（304 用例全部通过）
- [x] `ScheduleResult.to_dict()` 与 `RoutePlan.to_dict()` JSON 字段稳定
- [x] 文档完整（`AGENTS.md` §3.6 / §3.7 + 本报告 + 源码 docstring）

> 共 38 项验收标准，全部 `[x]`。
