# LogiRoute 后续开发阶段规划

> 本文件描述从 Phase 2 起的功能路线。每阶段边界清晰、可单独交付。
> 严禁在收到明确阶段切换指令前提前实施。
>
> **2026-10-15 课程约束纠偏**：教师原始题目要求**单车辆**配送路径规划——
> 从仓库出发，遍历所有待配送点后返回仓库。原先"多车辆调度"设想作废；
> 后续任何 Phase（含 Phase 4 随机场景、Phase 5 Dashboard、Phase 6 动态重规划）
> 都必须遵守单车辆约束。详见 `AGENTS.md` §3.6。

## 状态总览

| Phase | 名称                                          | 状态       |
| ----- | --------------------------------------------- | ---------- |
| 1     | 工程初始化、配置驱动与核心数据结构             | ✅ 已完成  |
| 2     | 最短距离路径规划（手写 Dijkstra + 手写堆）      | ✅ 已完成  |
| 3     | **单车辆配送路径规划（最近邻 / 可行插入 / 2-opt）** | ⏳ 待启动 |
| 4     | 随机初始化完整物流场景（仍保持单车辆）         | ⏳ 待启动 |
| 5     | 交互式 Dashboard（单车辆配送过程可视化）       | ⏳ 待启动 |
| 6     | 动态拥堵、紧急订单与重规划（单车重路由）       | ⏳ 待启动 |

---

## Phase 2 — 手写 Dijkstra 与自实现堆

**目标**：基于 `LogisticsGraph` 实现单源最短路径算法。**关键：堆必须手写，
不得使用 `heapq`；排序需要时也使用手写排序实现。**

**状态：✅ 已完成（2026-10-13）**

### 主要工作项

1. 自实现最小堆（`MinHeap[T]`）：支持 `push / pop_min / decrease_key / heapify`。
2. 自实现 Dijkstra：
   * 输入：`graph, source_id, target_id, metric='distance'`
   * 输出：`(total_cost, path: list[node_id])`
3. 单源版：`single_source_shortest_paths(...)` 返回 `{target_id -> (cost, path)}`。
4. 测试覆盖：
   * 普通图 / 强连通图 / 不连通子图 / 反向边；
   * 三种 `metric`（distance / travel_time / cost）的差异性；
   * 自环不参与（边构造已拒绝）；
   * 重复节点 ID（模型已拒绝）。

### 交付物

* `src/logiroute/algorithms/heap.py`（手写堆）—— **✅ 已交付**
* `src/logiroute/algorithms/dijkstra.py` —— **✅ 已交付**
* `tests/test_heap.py`（32 用例）—— **✅ 已交付**
* `tests/test_dijkstra.py`（31 用例）—— **✅ 已交付**
* `docs/algorithms-minheap.md` —— **✅ 已交付**
* `docs/algorithms-dijkstra.md` —— **✅ 已交付**
* `docs/phase2-teacher-defense.md` —— **✅ 已交付**
* `scripts/demo_dijkstra.py` —— **✅ 已交付**

## Phase 3 — 单车辆配送路径规划（**课程原题**）

> **车辆数 = 1**：从选定的出发仓库出发，遍历**所有**待配送订单目的地，
> 最后返回该出发仓库；不实现多车辆订单分配 / 多车 VRP / 跨车交换。
>
> 主要策略：**最短距离** 与 **最低运输成本**；**最短时间** 仅作为附加对比。

### 数据结构

* `DeliveryStop`：订单 ID / 目的地节点 / 到达时间 / 服务开始时间 /
  服务结束时间 / 等待时间 / 需求重量。
* `RoutePlan`：车辆 ID / 配送员 ID / 起止仓库（同一仓库，闭合回路）/
  已分配订单 ID 列表 / 配送站点序列 / 完整道路节点序列 / 总距离 /
  总行驶时间 / 总成本 / 出发时刻 / 返回时刻 / 当前载重 / 可行标记。
* `ScheduleResult`：场景 ID / 主目标 / 算法名 / 各车路线 /
  已服务订单 / 未服务订单及原因 / 总体距离 / 总体时间 / 总体成本 /
  总体可行性 / 计算统计（节点候选枚举次数、路径缓存命中、
  Dijkstra 调用次数、运行耗时）。

### 路径计算层

* 调度器**只**调用 Phase 2 的 `dijkstra.shortest_path` / `single_source`；
* 持有**单次调度作用域**内的路径缓存，键为
  `(graph_version, source, target, metric)`；
* 三 metric（`distance` / `travel_time` / `cost`）统一通过 `edge.weight(metric)`
  切换，禁止三份独立代码；
* 最短距离路径的实际行驶时间由该路径的 `travel_time` 累加得到，
  **不**得拿另一条"最短时间路径"的时间来顶替。

### 业务硬约束

* **车辆容量**：本阶段单车单趟配送，初始仓库一次性装全部分配订单；
  违反容量的方案**直接拒绝**并标记不可行。
* **时间窗口**：硬约束为
  `time_window_start <= service_start <= time_window_end`；
  允许提前到达并等待；不允许晚于最晚开始服务时刻。
  `service_end = service_start + service_time`；本阶段不强制
  `service_end <= time_window_end`，若课程题目另有要求，将其作为
  后续可配置策略选项，不暗中修改当前语义。
* **优先级**：`urgent` 订单优先参与候选分配，但不能越过容量与时间窗
  硬约束；优先级策略和同分规则必须确定性、可解释。
* **回仓**：车辆路线结束后使用有向图中实际合法路径返回出发仓库；
  返程距离 / 时间 / 成本计入总指标。
* **不可行订单**：若没有合法插入位置，调度器**保留**该订单并明确
  记录原因；不允许为提高完成率而违反约束；不允许将启发式无解与
  "问题数学上无解"混为一谈。

### 自主实现的算法

1. **最近邻（NN）基线**：从出发仓库起步，反复选择"评价最优"的下一站；
   评价结合实际道路最短路径、剩余容量、到达时间、时间窗、车辆归属仓库。
   多候选相同代价时按确定性的字典序 tie-break。
2. **可行插入（CFI）**：对每个未安排订单，枚举可用插入位置 → 插入 →
   重新推演完整时刻表 → 验证容量与时间窗 → 计算增量代价 →
   选取最优合法插入；继续处理剩余订单；支持以 `distance` /
   `travel_time` / `cost` 三种增量代价做对比。
3. **受约束 2-opt**：仅对已存在可行路线的车辆运行；对候选配送顺序
   重新计算有向最短路径、重新模拟服务时刻表、重新验证容量与时间窗；
   仅接受合法且**严格改善**的候选；无改善时结束；防止同一路线反复
   循环；保留优化前后指标对照。
   **不得**套用无向 TSP 的四边差值公式；必须以实际重建路线判定改善。

### 统一入口与可序列化

* 规划入口：`plan_deliveries(scenario, algorithm, objective)`；
* 输出 `ScheduleResult` 必须：可 JSON 序列化、不依赖前端 / HTTP /
  第三方求解器；含完整道路节点序列与服务时刻表。

### 交付物（Phase 3 收尾时应齐备）

* `src/logiroute/scheduling/types.py`（`DeliveryStop` / `RoutePlan` / `ScheduleResult`）
* `src/logiroute/scheduling/path_provider.py`（Dijkstra 适配 + 单次调度缓存）
* `src/logiroute/scheduling/feasibility.py`（容量 / 时间窗 / 回仓可行性）
* `src/logiroute/scheduling/algorithms/{nearest_neighbor, insertion, two_opt}.py`
* `src/logiroute/scheduling/planner.py`（`plan_deliveries` 统一入口）
* `tests/test_scheduling_*.py`（独立结果可行性检查器，**不**由调度器自证）
* `scripts/demo_phase3.py`（固定场景完整演示）
* `docs/algorithms-{nearest-neighbor,insertion,two-opt}.md`
* `docs/phase3-teacher-defense.md`（≥ 10 Q&A）
* `docs/phase3-final-review.md`

## Phase 4 — 随机初始化完整物流场景（**保持单车辆**）

* 按 `docs/architecture.md` 第 2.6 节实现随机生成器；
* **不**因场景随机而增加车辆 —— 随机节点和道路 ≠ 随机增加车辆；
* 保留 `scenario_id` / `seed`，保证场景可复现；
* 加载器强制固定场景最低规模基线：≥ 2 仓库、≥ 15 配送点、≥ 3 中转站、
  ≥ 30 节点、≥ 50 有向边；
* 多 seed 对比实验脚本；
* 生成器不得依赖第三方图算法库。

## Phase 5 — 交互式 Dashboard（**单车可视化**）

* 独立前端工程（React 18 + TypeScript + Vite）；
* 可视化一辆车的配送过程：节点坐标 / 完整路径 / 每站时刻表 /
  服务事件 / 算法统计 / 不可行订单原因；
* **可**展示多个仓库与全部网络节点；
* 不得在前端重新计算调度算法 —— 只负责输入参数、调用后端规划、
  显示结果；
* 数据通过 FastAPI（Phase 6）后端服务传输。

## Phase 6 — FastAPI 后端 + 动态事件

* `logiroute.api` 下搭建 FastAPI 应用；
* 路由：`/graphs`, `/nodes`, `/edges`, `/orders`, `/vehicles`, `/paths`；
* Pydantic 与 `core` 模型解耦：通过 `serializers` 模块转换；
* 暴露 `app: ASGIApp`；
* 动态事件：拥堵 / 阻断 / 修复 / 紧急订单；
* 增量式事件回调接口，便于 Dijkstra 重规划订阅；
* 重规划仍保持**单车**约束 —— 仅修改这一辆车的路线。

---

## 通用执行规范（持续适用）

* 任何 Phase 启动前确认上阶段全部测试通过；
* 严格使用 Conventional Commits；
* 提交前必须先跑 `python -m unittest discover`；任何失败禁止 push；
* 任何超出本阶段范围的功能请求，先与用户对齐再实施；
* 当前阶段结束后立即停止，等待用户审查。
