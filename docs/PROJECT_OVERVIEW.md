# LogiRoute — 项目综合说明（三维分层）

> 单文件覆盖 LogiRoute 电商物流配送路径规划系统的**项目定位 / 系统能力 / 当前现状**三个层面。
>
> 适用于：教师答辩、跨阶段交接、回到本项目时的快速回忆。

---

## 总体说明（一句话）

LogiRoute 是**面向"电商物流配送路径规划系统"课程设计**的手写算法仓储：**一个 Python 包** + **一个固定场景 JSON** + **一份端到端调度演示** + **多份配套文档 / 测试**，覆盖有向带权图建模、单源最短路与单车辆闭合回路配送调度，是课程验收阶段的核心成品（Phase 1–3 完成，Phase 4–6 待启动）。

---

## 第一层 — 项目定位

### 1.1 课程与题目

| 项 | 内容 |
| --- | --- |
| 课程 | 数据结构课程设计 |
| 题目 | 第 2 题「电商物流配送路径规划系统」 |
| 工作目录 | `数据结构课设`（Linux / WSL 下即 `Data-structure-project`） |
| Python 版本 | ≥ 3.11 |
| 教师原始要求 | **单车辆**配送——从仓库出发，遍历全部待配送点后返回仓库；多车辆方案被覆盖性否决（见 `AGENTS.md` §3.6） |
| 仓库地址 | `https://github.com/earthgrass/Data-structure-project.git` |

### 1.2 设计底线（不可妥协）

| 维度 | 规则 |
| --- | --- |
| 算法 | 核心数据结构与算法**全部手写**——不调 `heapq`、`sorted()`、NetworkX、NumPy、OR-Tools 等 |
| 依赖 | 仅 Python 标准库（`dataclasses` / `enum` / `json` / `pathlib` / `unittest` / `math` / `collections.deque`） |
| 测试 | 仅 `unittest`（**禁用** pytest / nose2） |
| 配置 | 节点数、容量、订单需求、服务时间等业务参数**全部从 JSON 配置驱动**——源代码内不硬编码默认值 |
| 不可行订单 | **如实记录**——`Violation(kind, message)`，绝不伪造 100% 完成率 |

### 1.3 当前快照

| 指标 | 数值 |
| --- | --- |
| 测试数 | **379 全过**（`unittest discover`） |
| 固定场景规模 | 35 节点 / 192 有向边 / 4 车辆 / 4 配送员 / 20 订单（含 2 urgent） |
| 模块文件 | Phase 1–3 共 11 个生产模块 + 8 个测试模块 + 6 份文档 + 1 个演示脚本 |
| 已发布阶段 | Phase 1 ✅ / Phase 2 ✅ / Phase 3 ✅ |
| 待启动阶段 | Phase 4（随机场景） / Phase 5（Dashboard） / Phase 6（FastAPI + 动态事件） |
| 当前分支 | `feat/phase3-scheduling`（领先 `main` 8 个 commit） |

---

## 第二层 — 系统能力清单

### 2.1 模块分层（自下而上）

```
┌────────────────── Phase 5+ Web UI（React, 未启动）─────────────────────┐
│                                                                       │
│  ┌───── Phase 6+ HTTP API（FastAPI, 未启动）─────────────────────────┐ │
│  │                                                                   │ │
│  │  ┌────── Phase 3+ 调度 (Scheduling) ──────────────────────────┐  │ │
│  │  │  plan_deliveries / PathProvider / check_feasibility       │  │ │
│  │  │  Nearest-Neighbor / CFI / 受约束 2-opt                   │  │ │
│  │  └────────────────────────┬──────────────────────────────────┘  │ │
│  │                           ▼                                     │ │
│  │  ┌──── Phase 2 算法（Algorithms） ─────────────────────────────┐ │ │
│  │  │  shortest_path / dijkstra_single_source / MinHeap        │ │ │
│  │  └────────────────────────┬──────────────────────────────────┘ │ │
│  │                           ▼                                     │ │
│  │  ┌──── Phase 1 图容器（Graph） ────────────────────────────────┐ │ │
│  │  │  LogisticsGraph（邻接表主存 + 邻接矩阵按需导出）           │ │ │
│  │  └────────────────────────┬──────────────────────────────────┘ │ │
│  │                           ▼                                     │ │
│  │  ┌──── Phase 1 核心数据模型（Core） ────────────────────────────┐│ │
│  │  │  Node / Edge / Vehicle / Courier / Order（frozen 语义）    ││ │
│  │  └────────────────────────┬──────────────────────────────────┘│ │
│  │                           ▼                                     │ │
│  │  ┌──── Phase 1 配置加载（Config） ─────────────────────────────┐│ │
│  │  │  load_scenario + 强校验（弱 + 强连通性、引用完整性）       ││ │
│  │  └────────────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────┘
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责速查

| 模块 | 公开能力 | 何时调用 |
| --- | --- | --- |
| `logiroute.core` | `Node` / `Edge` / `Vehicle` / `Courier` / `Order` 数据模型；`NodeType` / `OrderPriority` / `TrafficStatus` 等枚举 | 任何层；下层依赖 |
| `logiroute.graph` | `LogisticsGraph`（邻接表主存 + 邻接矩阵按需导出） | 图操作；强连通性检测；Demo |
| `logiroute.algorithms` | `dijkstra.shortest_path` / `dijkstra_single_source` / `compare_metrics`；自实现 `MinHeap` | Phase 2 唯一最短路 |
| `logiroute.config` | `load_scenario(path)` → `ScenarioBundle` 强校验 | 任何调度入口之前 |
| `logiroute.scheduling` | `plan_deliveries(scenario, algorithm, objective)` —— **本项目的最终业务入口**；`PathProvider` / `check_feasibility` / `select_depot` 内部支撑 | Phase 3 主流程 |
| `logiroute.simulation` / `logiroute.api` / `logiroute.web` | 占位（Phase 4–6 待启动） | — |

### 2.3 端到端调度流程

```
config/scenario.json
    │
    ▼  logiroute.config.load_scenario
ScenarioBundle {graph, vehicles, couriers, orders, simulation, optimization}
    │
    ▼  plan_deliveries(scenario, algorithm, objective)
    │
    ├─ select_depot        : 单车辆 lex-min 选择
    ├─ PathProvider        : 单调度作用域缓存，键 (graph_identity, src, tgt, metric)
    ├─ algorithm ∈ {NN, CFI, 2-opt}
    │     │
    │     ▼  check_feasibility  (5 类硬约束)
    │     │
    │     └─ RoutePlan (closed tour, all legs reachable)
    │
    ▼
ScheduleResult
    ├─ route_plan              : 闭合回路 + 全部 legs 重建 + 三指标总和 + 服务时刻表
    ├─ served_order_ids        : 已配送订单
    ├─ unserved_orders         : 未配送订单（带 Violation 原因）
    ├─ total_{distance,travel_time,cost}  : 含对比列
    ├─ planning_stats          : cache_hits / cache_misses / dijkstra_calls / runtime 等
    └─ is_feasible             : 全局可行性（含 unserved 是否为空）
```

### 2.4 关键契约

| 契约 | 文档位 | 说明 |
| --- | --- | --- |
| **场景规模基线** | `config/loader.py:ScenarioLimits` | ≥ 2 仓库 / ≥ 15 配送点 / ≥ 3 中转 / ≥ 30 节点 / ≥ 50 有向边 —— 加载器强校验 |
| **单车闭环** | `scheduling/planner.py` | `ScheduleResult.vehicle_id` 唯一；`RoutePlan.stop_sequence` 首尾同 depot |
| **路径单一来源** | `scheduling/path_provider.py` | 所有相邻站点路径只能走 `ctx.path_provider.shortest_path` |
| **时间窗硬约束** | `scheduling/feasibility.py:182-200` | 仅 `service_start > time_window_end` 视为违规；`service_end` 不强制（`AGENTS §3.7`） |
| **`travel_time` 仅对比列** | `scheduling/planner.py:ALLOWED_OBJECTIVES` | `travel_time` 作主目标抛 `InvalidObjectiveError` |
| **不可行报告完整性** | `scheduling/types.py:Violation` | 9 类 `kind` 枚举；`message` 必非空 |

---

## 第三层 — 现状与下一步

### 3.1 已发布阶段（Phase 1 / 2 / 3）

| 阶段 | 内容 | 关键产出 | 测试数 |
| --- | --- | --- | --- |
| **Phase 1** | 工程初始化 + 配置驱动 + 核心数据结构 | `Node` / `Edge` / `Vehicle` / `Courier` / `Order`；`LogisticsGraph`；`ArrayQueue`；强校验 loader；固定场景 `config/scenario.json`（35 节点 / 192 边） | **96** |
| **Phase 2** | 手写 Dijkstra + 手写堆 | `MinHeap`（索引式二叉最小堆）；`dijkstra.shortest_path` / `dijkstra_single_source` / `compare_metrics`；`PathResult` 含 `cross_metrics`；三种 metric（distance / travel_time / cost） | **+32 → 128** |
| **Phase 3** | 单车辆闭环调度 | `DeliveryStop` / `RoutePlan` / `ScheduleResult` 等 8 个 dataclass；`PathProvider` 单调度缓存；5 类硬约束 `check_feasibility`；NN / CFI / 受约束 2-opt 三算法；`plan_deliveries` 统一入口；`scripts/demo_phase3.py` 跑通；3 算法文档 + 教师答辩 + 终评审报告 | **+155 → 379** |

### 3.2 Phase 3 自检（demo 实测）

```
label                        served unserved  distance  travel_time      cost  dijkstra runtime(ms)
(1) NN + distance                10       10    20.385       58.866    33.001       289       31.00
(3) insertion + distance         10       10    36.421      112.709    58.179       330      141.00
(4) two_opt + distance           10       10    20.312       58.902    33.105       307       47.00
```

- two_opt 不恶化 NN（20.385 → 20.312）—— cheapness 性质成立 ✓
- 未服务订单如实记录（每条带 `kind="no_feasible_next_step"` + 详细 message）—— 不伪造 100% ✓

### 3.3 待启动阶段（Phase 4 / 5 / 6）

| 阶段 | 内容 | 与已交付的衔接 |
| --- | --- | --- |
| **Phase 4** | 随机初始化完整物流场景（**仍保持单车辆**） | 沿用 `logiroute.config.loader` 的 `ScenarioLimits`；新增 `mode="random"` 模式 + 固定 `seed` 可复现 |
| **Phase 5** | 交互式 Dashboard（单车配送过程可视化） | 复用 Phase 3 `RoutePlan` / `ScheduleResult.to_dict()`；React 前端只读显示，不重算 |
| **Phase 6** | FastAPI 后端 + 动态拥堵 / 紧急订单 / 重规划 | 增量事件回调；重规划仍保持单车；`PathProvider` 自然丢弃 → 重建 |

### 3.4 提交历史（feat/phase3-scheduling 分支）

```
06745cd  feat(scheduling): add Phase 3 types, graph identity, and single-vehicle guardrails
04fc90d  feat(scheduling): add PathProvider with per-schedule Dijkstra cache
dabf444  feat(scheduling): add feasibility checker (capacity, time window, return-to-depot)
4e4767e  feat(scheduling): add Nearest-Neighbor algorithm
4c82823  feat(scheduling): add Cheapest Feasible Insertion algorithm
<略>     feat(scheduling): add constrained 2-opt local search
<略>     feat(scheduling): add unified plan_deliveries entry + depot selector
926b144  test(scheduling): phase3 regression suite + demo + 5 docs
157879b  docs(scheduling): add single-file Phase 3 summary report
```

完整 hash 与 message 用 `git log feat/phase3-scheduling --oneline` 查看。

### 3.5 阅读地图

| 角色 | 推荐先读 | 后读 |
| --- | --- | --- |
| 课程教师 | `README.md` + `AGENTS.md` + `docs/phase3-teacher-defense.md` | `docs/phase3-final-review.md` + `docs/PHASE3_SUMMARY.md` |
| 接手开发下一阶段 | `docs/PROJECT_OVERVIEW.md`（本文档） | `docs/architecture.md` + `docs/development-plan.md` |
| 复习算法 | `docs/algorithms-{minheap,dijkstra,nearest-neighbor,insertion,two-opt}.md` | 对应源码 |
| 验证现场 | `scripts/demo_dijkstra.py` + `scripts/demo_phase3.py` | `docs/PHASE3_SUMMARY.md` |

---

## 附：随项目进入下一阶段的最小动作清单

1. `git checkout -b feat/phase4-random-scenario`（建议新分支）
2. 实施前读 `AGENTS.md` 强约束 → `docs/development-plan.md` Phase 4 节
3. Phase 4 启动前**先跑** `PYTHONPATH=src python -m unittest discover -s tests -t .` 确认 379 测试仍全过
4. 沿用 `feat/phase3-scheduling` 的 8 commit 节奏（数据 / 算法 / 入口 / 测试分阶段）
5. 遵循 `AGENTS.md` §8：完成每一阶段立即停止，等待审查
