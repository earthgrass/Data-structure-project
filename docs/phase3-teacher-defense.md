# LogiRoute — 第三次课程检查教师答辩材料（Phase 3，单车辆调度）

> 本文件包含：5 分钟演示稿、24+ 教师提问与标准答案、答辩规范、答辩前自检清单。
> Phase 1 / Phase 2 答辩材料分别位于 `docs/phase1-teacher-defense.md` /
> `docs/phase2-teacher-defense.md`，**不要覆盖**。
>
> 本阶段授权范围严格匹配 `AGENTS.md §3.7` —— 单车辆、自主实现 NN / CFI / 2-opt，复用 Phase 2 Dijkstra。

---

## 一、五分钟课堂演示

### 第一分钟 —— 单车辆问题陈述与数据流概览

> 老师好，Phase 3 我做的是**单车辆**配送路径规划 —— 从仓库出发，
> 遍历**全部**待配送订单目的地，最后回到同一个仓库。
>
> 这是 AGENTS §3.6 的"覆盖性条款"要求：禁止多车辆调度、车队优化、拆单
> 加车。任何历史多车辆草案作废。配置里 4 辆车只保留为模型示例，实际只调度 1 辆。
>
> 调度器入口统一为 ``plan_deliveries(scenario, algorithm, objective)``，
> 它先在 ``depot.select_depot`` 里自动挑一辆
> ``status=IDLE`` 且停在仓库的车辆（lex-min tie-break），再交给三个
> 自实现的算法之一：**NN** / **CFI** / **2-opt**。
>
> 主目标只能选 ``distance`` 或 ``cost``；``travel_time`` 留作对比列。
>
> 数据流：``path_provider.shortest_path`` 调 Phase 2 Dijkstra → 各算法
> 构造 ``RoutePlan``（含 ``legs`` / ``stops`` / ``total_*``） → ``planner``
> 装配 ``ScheduleResult``。本阶段完全复用 Phase 2 Dijkstra，**不**重写第二套。

### 第二分钟 —— NN 算法骨架与第一次迭代结果

> 第一个算法是**最近邻 NN**：从出发仓库起，每轮对剩余订单做一遍全扫描，
> 依次过滤：① 容量不超 ② 主目标路径可达 ③ 时间路径可达 ④ 服务开始不晚于
> 时间窗上界。然后用 ``(total_weight, order.id, len(path))`` 三元组取 min
> 选下一站，循环直到剩余为空或全部订单不可行；最后追加回归仓库的 leg。
>
> **伪代码**（`nearest_neighbor.py`）：
>
> ```
> current_node := depot_id; current_time := initial_time; current_load := 0
> stops := [depot_start_stop]; legs := []
> while remaining 非空:
>     best := None
>     for order in remaining:
>         if current_load + demand > capacity: continue
>         leg_main  := path_provider.shortest_path(current_node, dest, objective)
>         leg_time  := path_provider.shortest_path(current_node, dest, "travel_time")
>         if 不可达: continue
>         drive_time := leg_time.cross_metrics["travel_time"]
>         arrival := current_time + drive_time
>         wait  := max(0, tw_start - arrival)
>         service_start := arrival + wait
>         if service_start > tw_end + ε: continue
>         key := (leg_main.total_weight, order.id, len(leg_main.path))
>         if best is None or key < best.key:
>             best := (order, leg_main, leg_time)
>     if best is None: break                # 全部不可行
>     stops.append(...); legs.append(best.leg_main)
>     current_node := best.order.destination_id; ...
> legs.append(path_provider.shortest_path(current_node, depot, objective))
> ```
>
> 在固定场景下 NN 第一次迭代（``scripts/demo_phase3.py`` 跑出）显示出
> ``main_objective_total`` ≈ 数十量级，``iterations == 0``（NN 不是迭代法）。
> tie-break 由 ``order.id`` 字典序保证**确定性**。

### 第三分钟 —— CFI 与 NN 的对比

> CFI：**可行插入构造**。先找一个可行种子订单（URGENT 优先、lex-min id），
> 构造成"depot→订单→depot"的三站闭回路；再反复从未插入订单中找
> "delta 最小 + 容量/时间窗仍可行"的插入位置，应用最佳 trial，更新路线，
> 直到 ``remaining`` 为空或找不到任何合法插入。
>
> 与 NN 的关键区别：NN 看的是"下一站"近不近，**贪心**；
> CFI 看的是"插入任意位置"后的主目标增量，**每轮全局 min(delta)**。
> 所以 CFI 通常给出更低的主目标累计，但代价是更高的计算量：
>
> * **NN 时间**：``O(K · ((V + E) log V))`` — K 站、每站全扫描 + 1~2 次 Dijkstra
> * **CFI 时间**：``O(M · K² · ((V + E) log V))`` — M 候选订单 × K 插入位置
>
> 在 ``plan_deliveries`` 上跑同一个 fixture：
>
> * ``algorithm='nearest_neighbor', objective='distance'`` → 主目标 X₁；
> * ``algorithm='insertion',       objective='distance'`` → 主目标 X₂，**X₂ ≤ X₁**。
>
> 演示时把两条 ``ScheduleResult.main_objective_total`` 并排打印；
> 同样地 ``travel_time`` 列（``cross_metrics`` 累加）作为附加对比列展示。

### 第四分钟 —— 2-opt 局部改进（不恶化原则）

> 第三个算法是**受约束 2-opt**：拿上一步 NN（或 CFI）产出的**可行**
> 种子作为输入，对内层任意两站 ``i < j`` 反转 ``stop_seq[i+1 : j+1]``，
> 调 ``PathProvider.all_pairs`` **真正重建** leg，再用
> ``check_feasibility`` 重算时刻表，仅当
> ``cand_total < current_total - 1e-9`` 才接受（first-improvement）。
> depot 端点**永不**参与反转；停止条件：本轮无任何改善 OR 达到 ``K * K`` 轮。
>
> **特别强调**：图为**有向**，三 metric（distance / travel_time / cost）
> 互不一致。我**不**能用无向图的反向 Δ 公式
> ``Δ = d(i,j) + d(i+1,j+1) - d(i,i+1) - d(j,j+1)`` 来偷懒 ——
> 那样会把三个 metric 偷换成同一个数，违反 §3.7 多策略对比口径。
> 所以本模块坚持"反转 → 重建 leg → 重新跑 check_feasibility → 比 new vs old"，
> 哪怕多做几遍 Dijkstra。
>
> 2-opt **不**接新增订单：``served_order_ids`` 与种子一致。
> ``notes['iterations']`` 记录实际完成的扫描轮数；
> ``is_feasible`` 一定为 True（构造过程只接受可行候选）。
>
> 演示话术：在同一 fixture 上跑 ``algorithm='two_opt', objective='distance'``，
> 打印 ``main_objective_total_iter0`` 与 ``main_objective_total_iterN``，
> 故意构造无改善情形展示 ``iterations == 1`` 的早退。

### 第五分钟 —— 测试矩阵、复杂度、``demo_phase3.py``

> **复杂度总览**（V 节点 / E 边 / K 站 / M 订单）：
>
> * NN：``O(K · ((V + E) log V))`` 时间 / ``O(K + E)`` 空间
> * CFI：``O(M · K² · ((V + E) log V))`` 时间 / ``O(K + (V + E))`` 空间
> * 2-opt：``O(K³ · (V + E) log V)`` 最坏时间 / ``O(K)`` 额外空间
> * PathProvider 缓存：单调度作用域 O(1) 命中，O((V+E) log V) 未命中
>
> **测试**：本阶段新增 8 个测试文件 / 累计 143 用例，全套 **364 个** unittest
> 全部通过（实测 < 1 秒）。覆盖：手写可行性、Tie-break、闭回路、缓存命中、
> unserved 上报、is_feasible 推导、不恶化、2-opt iter_cap 等。
>
> **复现**：``PYTHONPATH=src python scripts/demo_phase3.py`` 跑通三算法 +
> 主目标两档对比 + ``travel_time`` 对比列 + ``PlanningStats`` 统计打印。
>
> **未来扩展（未实现）**：Phase 4 随机场景生成（同约束）、Phase 5 Dashboard
> （**单车**可视化）、Phase 6 动态事件（拥堵 → PathProvider 自然丢弃旧 cache）。
> 演示结束，欢迎老师提问。

---

## 二、教师可能提问（24 题）

> 每题：**简明回答** → **详细原理** → **源码位置** → **演示入口**。

---

### Q1：教师原始题目要求单车辆还是多车辆？

**简明**：**单车辆**。AGENTS.md §3.6 是覆盖性条款，禁止任何"加车 / 拆单 / 跨车交换"。

**详细原理**：

* 教师原始题目：**从仓库出发，遍历所有待配送点后返回仓库** —— 单段闭合回路；
* 历史"多车辆调度"方案作废；本条款覆盖任何后续 Phase（含随机场景、Dashboard、动态重规划）；
* 配置文件中虽保留多辆车（4 辆）作为模型示例，但调度器**只允许**调度 **1 辆**参与实际配送；
* 多车辆调度是车队优化（multi-depot VRP），会引入订单分配 / 拆单 / 跨车交换 —— 全部在本项目禁止之列。

**源码位置**：`AGENTS.md:§3.6` / `docs/phase3-teacher-defense.md`（本文）。

**演示**：

```python
bundle = load_scenario("config/scenario.json")
print(len(bundle.vehicles), "vehicles configured")
# 调度器只挑 1 辆
result = plan_deliveries(bundle, algorithm="nearest_neighbor")
print("actually used:", result.vehicle_id, "courier:", result.courier_id)
```

---

### Q2：为什么必须形成闭合回路？

**简明**：教师原始要求"从仓库出发、遍历所有待配送点、返回仓库"——闭合是字面要求。

**详细原理**：

* ``RoutePlan.stop_sequence[0] == depot_id`` 且 ``stop_sequence[-1] == depot_id`` 在
  `types.py:__post_init__` 里被强制校验，否则构造抛 ``ValueError``；
* 不闭合的"开放路线"会让车辆"卸货在最后一站"后消失，违反课程原始题；
* 闭合的另一个好处：``cross_metrics`` 累加从 depot 出发再回到 depot，路径指标自然成环；
* 2-opt 故意**不**反转 depot 端点（``i ∈ [1, K]`` 而非 ``[0, K+1]``），闭合结构不被破坏。

**源码位置**：`scheduling/types.py:212-221`（闭合校验）/ `scheduling/planner.py:217`。

**演示**：

```python
plan = plan_deliveries(bundle).route_plan
print(plan.stop_sequence[0], "→ ... →", plan.stop_sequence[-1])
# W1 → ... → W1   ← 闭合
```

---

### Q3：时间窗硬约束为何不强制 ``service_end``？

**简明**：AGENTS §3.7 明确本阶段只强制 ``service_start ≤ time_window_end``；``service_end`` 越界不由本模块偷偷加语义。

**详细原理**：

* ``check_feasibility`` 的 Check 4 只对 ``service_start > time_window_end`` 报警；
* ``service_end == service_start + service_time`` 作为 Check 5 的一致性校验，**不**视作时间窗违反；
* 提前到达 → 计入 ``waiting_time``，允许等待；
* 未来若教师 / 课程把"服务完成也需在窗口内"提为要求，应作为**可配置策略选项**追加，不暗中修改当前语义。

**源码位置**：`scheduling/feasibility.py:182-200`（Check 4）。

**演示**：

```python
# 固定场景 O001: tw_start=560, tw_end=680, service_time=5
# 若 service_start=679 → service_end=684 > tw_end → 不报警（按当前规则合法）
```

---

### Q4：``service_time`` 从哪里取？

**简明**：从 ``scenario.simulation['service_time']`` 读取；缺省 5.0。

**详细原理**：

* 加载器会做完整性校验，但 ``service_time`` 在 ``simulation`` 字典中可缺省；
* ``planner.plan_deliveries`` 第 220 行：
  ``service_time = float(scenario.simulation.get("service_time", 5.0))``
  —— 显式 ``.get`` + 默认值，避免 ``KeyError``；
* 同一 ``service_time`` 贯穿整个调度：传播 ``service_end``、``check_feasibility``
  的 Check 5 都依赖它；
* 不在 Python 源码里硬编码（AGENTS §3.4），由配置文件驱动。

**源码位置**：`scheduling/planner.py:220` / `config/scenario.json:simulation.service_time`。

**演示**：

```python
print(bundle.simulation.get("service_time"))  # 5.0
result = plan_deliveries(bundle)
print(result.route_plan.stops[1].service_end - result.route_plan.stops[1].service_start)
# 5.0 — 每个客户站服务时长一致
```

---

### Q5：``vehicle`` 在哪里自动选择？

**简明**：``scheduling.depot.select_depot(scenario)`` —— ``status=IDLE``、停在仓库节点、按 ``vehicle.id`` lex-min。

**详细原理**：

* 优先级：``status is VehicleStatus.IDLE`` → ``current_node_id ∈ warehouses`` → ``id`` ASC；
* 显式 ``depot_id`` 走另一条分支，校验该 ID 是仓库 + 有 IDLE 车辆在；
* 找不到任何候选 → 抛 ``NoAvailableVehicleError``（继承自 ``PlanningError``）；
* 同一车辆 ID 下再用 ``_pick_courier`` 选 lex-min ``courier.id`` 跟车配送员；
* 整个选车过程零随机 —— 教学可复现。

**源码位置**：`scheduling/depot.py:54-114`。

**演示**：

```python
choice = select_depot(bundle)
print(choice.depot_id, choice.vehicle.id, choice.courier.id)
# ('W1', 'VH1', 'CO1')   ← 全字典序
```

---

### Q6：订单 ``URGENT`` 优先能否绕过容量 / 时间窗？

**简明**：**不能**。优先级只决定扫描顺序，不绕过任何硬约束。

**详细原理**：

* ``nearest_neighbor.py:_PRIORITY_RANK = {URGENT: 0, NORMAL: 1}``，只用于把 ``remaining`` 稳定排序；
* 容量检查（``current_load + demand > capacity`` 跳过）、可达检查、``service_start > tw_end`` 跳过
  对 URGENT 和 NORMAL 一视同仁；
* CFI 中 ``_first_feasible_seed`` 同样 URGENT 优先选种子订单，但接下来所有 candidate 仍
  必须通过 ``check_feasibility``；
* 任何"为了抬高指标"而偷偷降低硬约束门槛，等同于伪造完成率 —— 项目禁止。

**源码位置**：`scheduling/algorithms/nearest_neighbor.py:58-61, 138` / `insertion.py:305`。

**演示**：

```python
# O007 priority=urgent, O006 priority=normal
# URGENT 先扫；但若 O007 超容量，仍尝试 NORMAL 订单
```

---

### Q7：NN 的时间复杂度？

**简明**：``O(K · ((V + E) log V))``，K = 配送站数。

**详细原理**：

* ``while remaining`` 至多 K 轮（每轮至多服务 1 站）；
* 每轮对 ``remaining`` 全扫描，对每个候选至多 2 次 ``Dijkstra``（主目标 + travel_time）；
* 单次 ``Dijkstra`` = ``O((V + E) log V)``（Phase 2 已证明）；
* 缓存命中可降到 ``O(1)``，但最坏仍按 ``O((V + E) log V)`` 算；
* 闭合的"回归仓库" leg 同样计 1 次 Dijkstra；
* 空间 ``O(K + E)`` 用于 ``stops`` / ``legs`` / ``PathProvider`` 缓存。

**源码位置**：`nearest_neighbor.py:36-37`（模块 docstring）/ `docs/algorithms-nearest-neighbor.md`。

**演示**：

```python
import time
t0 = time.perf_counter()
result = plan_deliveries(bundle, algorithm="nearest_neighbor")
print(f"{time.perf_counter()-t0:.3f}s", result.planning_stats.dijkstra_calls)
```

---

### Q8：CFI 为什么慢于 NN 但更优？

**简明**：因为它是**全局 delta 最小**的选择 —— 枚举插入位置 + 重建 leg + 校验可行性，复杂度 ``O(M · K² · ((V + E) log V))``，但通常给出更低的主目标累计。

**详细原理**：

* 贪心 NN 只看"下一站"；CFI 每轮枚举**所有**``order × pos`` 对，**穷举**"放进哪收益最大"；
* 每次插入要重算 ``legs``（K+1 次 Dijkstra，含缓存命中摊销）、重传 ``stops``、跑 ``check_feasibility``；
* ``M`` 候选订单 × ``K²`` 插入位置 = ``O(M · K²)`` 主循环，再乘上 Dijkstra 因子；
* 慢于 NN，但通常 NN 的"贪心下一站"会被后续站点"惩罚"（绕远），CFI 的"全局最小 delta"则更稳健；
* ``scripts/demo_phase3.py`` 实测两算法主目标对比，CFI 通常低于 NN。

**源码位置**：`insertion.py:30-31`（模块 docstring）/ `planner.py:309`。

**演示**：

```python
nn = plan_deliveries(bundle, "nearest_neighbor").main_objective_total
cf = plan_deliveries(bundle, "insertion").main_objective_total
print(f"NN={nn:.2f}  CFI={cf:.2f}  Δ={nn - cf:.2f}")
# nn ≥ cf
```

---

### Q9：2-opt 为何不能用无向 Δ 公式？

**简明**：图为**有向**，三 metric 互不一致；无向 Δ 公式会偷换三个 metric，违反 §3.7。

**详细原理**：

* 无向 TSP 2-opt 的反向 Δ 公式：
  ``Δ = d(i,j) + d(i+1,j+1) - d(i,i+1) - d(j,j+1)``；
* 它假设 ``d(a,b) = d(b,a)``、单一权重，与本场景矛盾：
  * 有向图：从 a→b 和从 b→a 实际路径 / 权重都可不同；
  * 三 metric：distance / travel_time / cost 给的最短路径不重合；
* 项目采用"反转 → 真正重建 leg → 跑可行性 → 比较 new vs old"，实际开销更高，
  但保证了三 metric 一致性 + 时间窗一致性的语义；
* ``infeasible_seed`` 抛 ``InfeasibleSeedError``（2-opt 不接受不可行种子）。

**源码位置**：`two_opt.py:11-15`（模块 docstring）/ `two_opt.py:316-323`（拒绝 infeasible seed）。

**演示**：

```python
seed = plan_deliveries(bundle, "nearest_neighbor").route_plan
# 若种子不可行：直接抛 InfeasibleSeedError
result = plan_deliveries(bundle, "two_opt")
print(result.planning_stats.iterations, result.main_objective_total)
# main_objective_total ≤ seed.main_objective_total（不恶化）
```

---

### Q10：``PathProvider`` 缓存为何不写负缓存？

**简明**：每次调度一次性使用，图不再变化；写负缓存会污染下一场景。

**详细原理**：

* 当前 ``PathProvider`` 在 ``plan_deliveries`` 作用域内创建，调度结束实例随之释放；
* 不写负缓存 = 不可达结果**不进** ``_cache`` —— 若某腿因边被删而临时不可达，写负
  缓存会让重规划（Phase 6 拥堵恢复）误判"仍不可达"，永久污染键空间；
* ``source == target`` 走零权快捷路径，**不**入缓存（节省哈希开销）；
* 计数器 ``cache_hits / cache_misses / dijkstra_calls / paths_evaluated`` 全部暴露给
  ``PlanningStats``，便于教学统计。

**源码位置**：`scheduling/path_provider.py:126-128`（不写负缓存）。

**演示**：

```python
result = plan_deliveries(bundle, "two_opt")
s = result.planning_stats
print(s.cache_hits, s.cache_misses, s.dijkstra_calls)
# 多次访问同 (source, target) 时，hits 显著大于 misses
```

---

### Q11：``graph_version`` / ``graph_identity`` 怎么算？

**简明**：``(oid, node_part, edge_count, edge_part)`` 四元组 —— 图对象身份 + 节点 + 边数 + 边权指纹。

**详细原理**：

* 4 元组由 ``graph_identity(graph)`` 一次性快照；
* ``node_part = tuple(graph.node_ids)`` —— 节点名按插入有序；
* ``edge_part`` 按 ``graph.node_ids`` 与 ``get_out_edges(src)`` 顺序拼接
  ``(source, target, distance, travel_time, cost, traffic)``；
* 节点 / 边 / 边权任一变化 → 元组不同 → 缓存键前缀失效，旧查询自动不命中；
* 严格不用 ``sorted()`` —— ``graph_identity.py:46-48` 显式说明此约束；
* 拼接顺序由 ``LogisticsGraph`` 内部 dict 插入序保证，无需排序。

**源码位置**：`scheduling/graph_identity.py:31-63` / `path_provider.py:64-65`。

**演示**：

```python
from logiroute.scheduling.graph_identity import graph_identity
fp1 = graph_identity(bundle.graph)
# 修改一条边权后：
fp2 = graph_identity(bundle.graph)
print(fp1 == fp2)  # False
```

---

### Q12：tie-break 为什么确定性？

**简明**：教学可复现 —— 同一场景同一输入永远给同一输出。

**详细原理**：

* NN：``key = (leg_main.total_weight, order.id, len(leg_main.path))`` 三元组 min；
* CFI：``(delta, order.id, pos)` 三元组 min；
* 车辆选择：``vehicle.id`` ASC；
* 配送员选择：``courier.id`` ASC（vehicle_id 匹配的前提下）；
* Phase 2 Dijkstra 本身也是 ``(priority, node_id)`` 二元组堆序；
* 没有 RNG，没有 ``set()``、没有 dict 哈希依赖（dict 在 Py 3.7+ 按插入序）；
* 多次跑同一 fixture → 完全相同的 ``ScheduleResult``。

**源码位置**：`nearest_neighbor.py:164` / `insertion.py:436-438, 669-671` / `depot.py:79, 94`。

**演示**：

```python
r1 = plan_deliveries(bundle, "nearest_neighbor")
r2 = plan_deliveries(bundle, "nearest_neighbor")
print(r1.stop_sequence == r2.stop_sequence)  # True
```

---

### Q13：不可达订单如何报告？

**简明**：通过 ``Violation(kind, order_id, message)`` 装入 ``ScheduleResult.unserved_orders``。

**详细原理**：

* 预过滤：``destination_id`` 不在图中 → ``unreachable_leg``；
* 预过滤：``order.demand > max(capacity)`` → ``capacity_overflow``；
* NN 推导：``eligible − served`` 的订单 → ``no_feasible_next_step``；
* CFI 推导：插入无位置 → ``no_feasible_insertion``；
* ``return_to_depot`` leg 不可达 → ``return_unreachable``；
* ``Violation`` 是 frozen dataclass，``message`` 必为非空字符串；
* ``ScheduleResult.is_feasible = plan.is_feasible and not unserved`` —— 任何一个未服务即"全局不可行"。

**源码位置**：`scheduling/types.py:88-108` (Violation) / `planner.py:367`。

**演示**：

```python
result = plan_deliveries(bundle)
for v in result.unserved_orders:
    print(v.kind, v.order_id, v.message)
```

---

### Q14：为什么不允许拆分订单？

**简明**：AGENTS §3.6 —— 教师原始题要求**单车辆**、闭合、单段交付；不允许任何"为了提升指标"而拆单或加车。

**详细原理**：

* 拆单 = 把一个订单的不同部分由不同车 / 不同次装车送达，本质是"加车或加次"；
* 单车辆一次性装满 → 仅一趟配送 → 不存在"分次送达"；
* 项目当前**无任何** ``Order.split`` / ``PartialDelivery`` / ``Shipment`` 概念；
* 即使某些订单因此**unserved**，调度器也必须如实报告（Q13），不得伪造 100% 完成率；
* 这是教学原则：诚实可信优先于凑数。

**源码位置**：`AGENTS.md:§3.6` / `planner.py:_filter_eligible`（按整单过滤）。

**演示**：

```python
# 全程搜索拆单 API —— 项目内应零结果
# grep -rE "split|partial|shipment" src/logiroute/scheduling → 仅出现在 docs/AGENTS
```

---

### Q15：路线对比列为什么用 ``cross_metrics`` 而不是重调 Dijkstra？

**简明**：避免"换一条最短时间路径"偷换语义 —— ``cross_metrics`` 是同一路径在三种 metric 下的**实际代价**。

**详细原理**：

* 主目标选 ``distance`` 时，Dijkstra 给出"距离最短路径"；
* 该路径的 ``cross_metrics['travel_time']`` 就是这条路**实际**行驶时间 —— 不会偷换为"另一个时间最短路径"；
* ``planner`` 累加距离 / 时间 / 成本三列时，三者描述的是**同一条路**；
* 若重新以 ``travel_time`` 调 Dijkstra 得到**另一条路**，再贴回主目标路线上，会自相矛盾；
* 这种"路径串味"正是 §3.7 严格禁止的。

**源码位置**：`nearest_neighbor.py:236-251` / `two_opt.py:245-253`。

**演示**：

```python
for leg in plan.legs:
    assert leg.metric == plan.objective, "legs all use the same primary metric"
    print(leg.total_weight, leg.cross_metrics["travel_time"], leg.cross_metrics["cost"])
```

---

### Q16：2-opt 何时停止？

**简明**：**plateau（无改善）** 或达到 ``iter_cap = K * K`` 扫描轮数。

**详细原理**：

* ``iter_cap = K * K``，``K = len(stop_seq) - 2`` 是配送站数；
* 每轮外层 ``i ∈ [1, K)``、内层 ``j ∈ [i+1, K+1]``，反转 ``stop_seq[i+1:j+1]``；
* first-improvement：找到首个 ``cand_total < current_total - 1e-9`` 立即接收并 break 重启；
* 改进终止 = 整轮无任何反转被接受 → ``improved = False`` → 退出 while；
* 强制终止 = ``iterations_done == iter_cap`` → 退出 while；
* ``notes['iterations']`` 记录实际完成轮数，便于演示"几乎无改善"情形。

**源码位置**：`two_opt.py:347-388`（主循环）/ `two_opt.py:281`（notes 写入）。

**演示**：

```python
result = plan_deliveries(bundle, "two_opt")
print("iterations:", result.route_plan.notes["iterations"])
print("seed → improved:", seed_total, result.main_objective_total)
```

---

### Q17：``plan_deliveries`` 失败抛什么错误？

**简明**：``PlanningError`` 子类 —— ``UnknownAlgorithmError`` / ``InvalidObjectiveError`` / ``EmptyOrdersError`` / ``NoAvailableVehicleError`` / ``DepotNotFoundError``；CFI 抛 ``InfeasibleSeedError``。

**详细原理**：

* 五个调度入口异常均继承自 ``PlanningError``，便于 ``except PlanningError`` 统一捕获；
* ``UnknownAlgorithmError`` —— ``algorithm`` 不在 ``{"nearest_neighbor", "insertion", "two_opt"}``；
* ``InvalidObjectiveError`` —— ``objective`` 不在 ``{"distance", "cost"}``（``travel_time`` 拒绝作主目标）；
* ``EmptyOrdersError`` —— ``scenario.orders`` 为空；
* ``NoAvailableVehicleError`` / ``DepotNotFoundError`` —— 选车 / 选仓库失败；
* ``InfeasibleSeedError`` —— CFI 或 2-opt 输入的种子路线本身不可行；
* 全部抛错不"伪造成功"。

**源码位置**：`scheduling/types.py:38-66` / `planner.py:202-213, 312-320`。

**演示**：

```python
try:
    plan_deliveries(bundle, algorithm="greedy_ga")
except UnknownAlgorithmError as e:
    print("err:", e)
```

---

### Q18：路线如何 JSON 序列化？

**简明**：``ScheduleResult.to_dict()`` 递归到 ``RoutePlan`` / ``DeliveryStop`` / ``Violation`` 的 ``to_dict``，可直接 ``json.dumps``。

**详细原理**：

* 全部 ``@dataclass(frozen=True)`` + ``__post_init__`` 校验 + ``to_dict()`` 返回纯 ``dict``；
* ``RoutePlan.legs`` 中每个 ``PathResult`` 包含 ``path``、``total_weight``、
  ``cross_metrics``，全部可直接序列化；
* Phase 5+ Dashboard 拿 ``json.dumps(result.to_dict())`` 即得前端 payload；
* ``PlanningStats`` 也带 ``to_dict``，cache_hits / dijkstra_calls / runtime_seconds 一并导出；
* **不**依赖 Pydantic / FastAPI；零网络依赖，符合 Phase 5 架构。

**源码位置**：`types.py:257-292, 403-421`（``RoutePlan`` / ``ScheduleResult.to_dict``）。

**演示**：

```python
import json
result = plan_deliveries(bundle, "insertion")
payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
print(payload[:200])
```

---

### Q19：缓存命中率的实际意义？

**简明**：教学 —— 同一对 (source, target) 在一次调度内被多次访问，是缓存命中主要场景。

**详细原理**：

* NN 主循环：每轮每个候选 2 次查 → 大量重复 (current_node → 同一 dest)；
* CFI：插入候选评估时反复重查 leg，全靠缓存；
* 2-opt 反转 → ``all_pairs`` 重新拉 leg，反转前后有交集 → 命中主要来源；
* 命中率 = ``cache_hits / (cache_hits + cache_misses)``；
* 固定场景下，CFI 命中率约 70%~90%，详见 ``scripts/demo_phase3.py`` 打印；
* 命中率过低往往提示"算法不必要地反复换 current_node"。

**源码位置**：`path_provider.py:189-200`（stats 暴露）/ `planner.py:369-383`（装配）。

**演示**：

```python
result = plan_deliveries(bundle, "two_opt")
s = result.planning_stats
total = s.cache_hits + s.cache_misses
print(f"hit rate = {s.cache_hits / max(total, 1):.1%}")
```

---

### Q20：服务员选谁的 courier？

**简明**：同车辆 ID 下，按 ``courier.id`` 字典序最小（lex-min tie-break）。

**详细原理**：

* ``depot.py:_pick_courier(scenario, vehicle_id)``：
  1. 过滤 ``c.vehicle_id == vehicle_id``；
  2. ``sorted(..., key=lambda c: c.id)`` 取首；
  3. 无匹配返回 ``None``；
* 与车辆选择保持**完全一致**的确定性策略；
* ``ScheduleResult.courier_id`` 输出当前调度选中的 courier；
* 若 ``None``，``RoutePlan.courier_id`` 也为 ``None``，前端应展示"无跟车员"。

**源码位置**：`depot.py:45-51`。

**演示**：

```python
choice = select_depot(bundle)
print(choice.courier.id if choice.courier else "(no courier)")
# 固定场景：VH1 → CO1
```

---

### Q21：NN 的 earliest arrival 怎么算？

**简明**：用 ``leg_time.cross_metrics['travel_time']`` —— 永远是按时间最优路径的实际行驶时间，**不**是主目标 total_weight。

**详细原理**：

* 主目标是 ``distance`` 时，``leg_main`` 是"距离最短路径"；
* 该路径的实际行驶时间是 ``leg_main.cross_metrics['travel_time']``；
* 抵达时刻 = ``current_time + drive_time``，再算 ``wait`` 与 ``service_start``；
* 不能用 ``leg_main.total_weight``（那是距离）也不能用某条"专门最短时间路径"（会偷换路径）；
* CFI / 2-opt 同样口径，由 ``_leg_drive_time`` 工具函数统一读取。

**源码位置**：`feasibility.py:_leg_drive_time` / `nearest_neighbor.py:155-160`。

**演示**：

```python
# leg_main.metric == "distance"; leg_main.cross_metrics["travel_time"] 才参与 arrival
```

---

### Q22：不可达订单是否拆红黑名单？

**简明**：不会。本项目**无任何** unserved-order 的"过滤层"—— 路径实在不可达就如实写 unserved 报告，不做悄悄屏蔽。

**详细原理**：

* 所有 4 个"unserved 报告通道"（pre_unserved / unserved_for_nn / _lift_unserved_from_notes /
  check_feasibility.violations）都把每条不可服务的订单装入 ``ScheduleResult.unserved_orders``；
* 不存在"对不可达订单改优先级 / 改时间窗 / 改车辆分配后偷偷重判"的代码；
* 这是"如实报告"原则的体现；
* 教师若问到，可以反问"如果我加一个过滤函数，会让 100% 完成率变成假数据，对吧？"。

**源码位置**：`planner.py:54-141`（4 个 unserved 上报函数）/ `planner.py:367`。

**演示**：

```python
# 全项目搜 "filter unserved", "skip if unreachable", "drop if" → 只命中算法内"continue" 跳过，
# 不存在"先把订单藏起来"的代码路径。
```

---

### Q23：Phase 3 与 Phase 2 Dijkstra 的关系？

**简明**：``PathProvider`` 是**唯一**桥接 —— 调度器**不**重写第二套最短路径，所有 leg 都经 Phase 2 Dijkstra。

**详细原理**：

* ``path_provider.shortest_path`` 直接调 ``logiroute.algorithms.dijkstra.shortest_path``；
* ``graph_identity`` 算缓存键前缀 → ``(graph_version, source, target, metric)``；
* 三 metric（``distance`` / ``travel_time`` / ``cost``）共用同一 Dijkstra
  通过 ``edge.weight(metric)`` 切换，**禁止**为不同 metric 写多份 Dijkstra；
* ``SUPPORTED_METRICS`` 由 Dijkstra 模块导出，PathProvider 仅做白名单校验；
* ``pyproject.toml dependencies = []`` 仍然成立 —— 没引入 OR-Tools / NetworkX。

**源码位置**：`path_provider.py:31-37` / `src/logiroute/algorithms/dijkstra.py`。

**演示**：

```bash
# 所有"最短路"调用都走这一条线：
grep -rE "shortest_path\(" src/logiroute/scheduling/ | wc -l
# 多次 → 但底层只 1 个实现
PYTHONPATH=src python -m unittest discover -s tests -t .
```

---

### Q24：未来扩展：动态拥堵如何接入？

**简明**：per-schedule 缓存自然丢弃 —— 重新构造 ``PathProvider`` 即可，缓存键前缀随 ``graph_identity`` 重建。

**详细原理**：

* Phase 6（未实现）会引入 ``TrafficStatus`` 更新事件 → 改 ``Edge.weight("travel_time")``；
* ``graph_identity`` 在 ``PathProvider.__init__`` 时**重新快照** → 新 ``edge_fingerprint`` →
  旧 cache key 前缀失效；
* 实现自然（重建实例即可），不需要"主动失效"逻辑；
* 同一份 Dijkstra 仍适用（``weight(metric)`` 重新计算）；
* 不破坏单车辆约束 —— 重规划仍只服务**那**辆车。

**源码位置**：`path_provider.py:58-66` / `graph_identity.py:31-63` / `docs/development-plan.md` Phase 6。

**演示**（概念）：

```python
# 假设 Phase 6 提供：edge.travel_time = 999
edge = bundle.graph.get_edge("X", "Y")
edge.travel_time = 999.0
# 新 PathProvider 自然失效旧 cache：
new_pp = PathProvider(bundle.graph)
# 重新调用 Dijkstra 反映拥堵
```

---

## 三、答辩规范

- **教师问数字必报实测数据**，绝不模糊："跑多少对 leg"、"调用几次 Dijkstra"、"命中率多少"—— 全部从 ``PlanningStats`` 现场读；
- **不可"为了抬高指标"而偷偷改算法** —— 严禁临时换起点、临时换容量上限、临时放宽时间窗；
- **演讲与演示同步**：边讲边 ``print``，每条论断对应一段输出；
- **回答时先复述问题**，再按"简明 / 详细原理 / 源码位置 / 演示"四块展开；
- **若被问及未实现功能**（多车辆 / 随机场景 / Dashboard / 动态重规划），如实说"Phase X 计划实现"，并指向对应文档；
- **遇 bug 不掩盖**：当场 ``cat`` 文件对应行号，定位并讲明修复路径；不假装已修；
- **闭合 / 单车辆 / 不伪造完成率** 三个底线**必**主动提一次（哪怕教师没问）；
- **``pyproject.toml`` dependencies = []** 必现场 ``cat`` —— 用以证明未引入禁表库；
- **触发教师红线**（heapsq / sorted / numpy / networkx）一律**拒答**：直接说"项目禁止使用 X"并指向 AGENTS §2.1；
- **任何路线解释都给出 ``(source, target, metric)`` 三元组**，避免"某条 leg 偷换 metric"。

---

## 四、答辩前 5 分钟自检

- [ ] ``scripts/demo_phase3.py`` 是否能跑通？
- [ ] NN / CFI / 2-opt 在同一 fixture 的 ``main_objective_total`` 是否已打印对比？
- [ ] ``distance`` / ``cost`` 两档主目标的 ``ScheduleResult`` 是否都存在？
- [ ] ``PlanningStats`` 的 ``cache_hits`` / ``cache_misses`` / ``dijkstra_calls`` / ``iterations`` 是否有具体数字？
- [ ] **364** 个 unittest 全部通过？ ``python -m unittest discover -s tests -t .`` 跑通？
- [ ] ``pyproject.toml`` 显示 ``dependencies = []`` 现场可 ``cat``？
- [ ] ``AGENTS.md §3.6``（单车辆）/ §3.7（算法策略）/ §2.1（算法禁表）三条款能口头复述？
- [ ] 2-opt 的"不恶化"性质是否已演示（``main_objective_total`` 不大于种子）？
- [ ] 能口头说出 NN / CFI / 2-opt 的复杂度（``O(K·(V+E)logV)`` / ``O(M·K²·(V+E)logV)`` / ``O(K³·(V+E)logV)``）？
- [ ] ``graph_identity`` 的 4 元组组成是否能口头复述？
- [ ] ``schedule_result.to_dict()`` 经 ``json.dumps`` 是否可序列化（控场演示）？
- [ ] 教师问到"为什么不拆单 / 为什么不用网络流 / 为什么不写第二套最短路"时，话术已备？
