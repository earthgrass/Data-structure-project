# Phase 3 — 单车辆配送路径规划 / 总览

> 单文件 Phase 3 总览文档。包含交付物、commit hash、文件清单、测试统计、demo 演示结果、约束合规清单与下一步入口。

---

## 1. 交付范围（与 `AGENTS.md` §3.6 / §3.7 一致）

- 单车辆、闭合回路、不拆单；
- 主要优化目标：**最短距离** 或 **最低运输成本**；**最短时间** 仅作对比列；
- 三个自实现调度算法：**NN** / **可行插入 CFI** / **受约束 2-opt**；
- 所有相邻站点路径统一调用 Phase 2 的 `dijkstra.shortest_path`，**不重写**第二套最短路；
- 路径缓存键 `(graph_version, source, target, metric)`，调度结束自然丢弃；
- 不可行订单如实记录 `Violation(kind, message)`，**绝不伪造 100%**。

---

## 2. 8 个 Commit 落地清单

| # | Commit   | 摘要 |
| --- | --- | --- |
| 1 | `06745cd` | `feat(scheduling): add Phase 3 types, graph identity, and single-vehicle guardrails` |
| 2 | `04fc90d` | `feat(scheduling): add PathProvider with per-schedule Dijkstra cache` |
| 3 | `dabf444` | `feat(scheduling): add feasibility checker (capacity, time window, return-to-depot)` |
| 4 | `4e4767e` | `feat(scheduling): add Nearest-Neighbor algorithm` |
| 5 | `4c82823` | `feat(scheduling): add Cheapest Feasible Insertion algorithm` |
| 6 | (略，见 `git log`) | `feat(scheduling): add constrained 2-opt local search` |
| 7 | (略，见 `git log`) | `feat(scheduling): add unified plan_deliveries entry + depot selector` |
| 8 | `926b144` | `test(scheduling): phase3 regression suite + demo + 5 docs` |

分支：`feat/phase3-scheduling`（本地领先 `origin` 8 个 commit）。

---

## 3. 文件清单

### 3.1 新增实现（10 文件）

| 路径 | 内容 |
| --- | --- |
| `src/logiroute/scheduling/__init__.py` | 包入口；导出 `plan_deliveries`、类型、错误子类 |
| `src/logiroute/scheduling/types.py` | `DeliveryStop` / `RoutePlan` / `ScheduleResult` / `Violation` / `FeasibilityReport` / `PlanningStats` / `PlanningContext` / `PlanningError(+6 子类)` |
| `src/logiroute/scheduling/graph_identity.py` | `graph_identity(graph) -> tuple` —— **不调 `sorted()`**（AST 扫描验证） |
| `src/logiroute/scheduling/path_provider.py` | `PathProvider` —— 单调度缓存（不写负缓存、`source==target` 走捷径、4 个公开计数器） |
| `src/logiroute/scheduling/feasibility.py` | `check_feasibility(...)` + `_leg_drive_time` —— 5 类硬约束；`service_end ≤ window_end` **不强制**（AGENTS §3.7） |
| `src/logiroute/scheduling/depot.py` | `select_depot(scenario, depot_id=None)` —— 单车辆 lex-min 选择 |
| `src/logiroute/scheduling/planner.py` | `plan_deliveries(scenario, algorithm, objective, ...)` —— 统一入口 |
| `src/logiroute/scheduling/algorithms/__init__.py` | `ALGORITHM_NAMES = ("nearest_neighbor", "insertion", "two_opt")` |
| `src/logiroute/scheduling/algorithms/nearest_neighbor.py` | `nearest_neighbor(ctx, eligible_orders) -> RoutePlan` |
| `src/logiroute/scheduling/algorithms/insertion.py` | `cheapest_feasible_insertion(ctx, eligible_orders)` |
| `src/logiroute/scheduling/algorithms/two_opt.py` | `constrained_two_opt(plan_seed, ctx)` |

### 3.2 新增测试（8 文件 / +155 用例）

| 路径 | 用例数 |
| --- | --- |
| `tests/test_scheduling_types.py` | 32 |
| `tests/test_scheduling_path_provider.py` | 21 |
| `tests/test_scheduling_feasibility.py` | 16 |
| `tests/test_scheduling_nearest_neighbor.py` | 23 |
| `tests/test_scheduling_insertion.py` | 14 |
| `tests/test_scheduling_two_opt.py` | 18 |
| `tests/test_scheduling_planner.py` | 16 |
| `tests/test_phase3_regression.py` | 15 |
| **小计** | **155**（总计 **379 测试通过**） |

### 3.3 新增脚本与文档（5+1 文件）

| 路径 | 用途 |
| --- | --- |
| `scripts/demo_phase3.py` | 固定场景端到端对照表 |
| `docs/algorithms-nearest-neighbor.md` | NN 算法文档（9 节模板） |
| `docs/algorithms-insertion.md` | CFI 算法文档 |
| `docs/algorithms-two-opt.md` | 2-opt 算法文档 |
| `docs/phase3-teacher-defense.md` | 5 分钟演示 + 24 Q&A + 答辩规范 + 自检 |
| `docs/phase3-final-review.md` | A–I 节终评审 + 38 项验收清单 |

### 3.4 文档随 commit 1 / commit 8 变更（既有）

- `AGENTS.md` —— 新增 §3.6「单车辆覆盖性条款」 + §3.7「Phase 3 算法策略」
- `README.md` —— Phase 3 状态切到 `✅ 已完成`；测试数 224 → 379；新增调度层 / 5 份文档说明
- `docs/development-plan.md` —— 与 README 同步

---

## 4. 测试统计

| 类别 | 数量 |
| --- | --- |
| Phase 1 既有 | 96 |
| Phase 2 既有（minheap + dijkstra） | 128 |
| Phase 3 新增 | 155 |
| **总计** | **379 全部通过** |

执行命令：

```bash
PYTHONPATH=src python -m unittest discover -s tests -t .
# Ran 379 tests in 3.682s — OK
```

---

## 5. 端到端 Demo 结果（`config/scenario.json`，20 订单，distance 主目标）

```
label                        served  unserved   distance  travel_time       cost  dijkstra  runtime(ms)
(1) NN + distance                10        10     20.385       58.866     33.001        289        31.00
(3) insertion + distance         10        10     36.421      112.709     58.179        330       141.00
(4) two_opt + distance           10        10     20.312       58.902     33.105        307        47.00
```

要点：

- **two_opt 不恶化 NN**：20.385 → 20.312 ✓ 严格满足 cheapness 性质
- **未服务订单如实报告**：10 条带 `kind="no_feasible_next_step"` 与详细 message，绝不伪造 100%

复跑命令：

```bash
PYTHONPATH=src python scripts/demo_phase3.py
```

---

## 6. 约束合规清单

| 约束（来自 `AGENTS.md`） | 状态 | 证据 |
| --- | --- | --- |
| §2.1 不引入 `heapq` / `sorted()` / `numpy` / NetworkX / OR-Tools | ✅ | `graph_identity` 内 AST 扫描验证无 `sorted()` 引用 |
| §2.1 配置驱动、不硬编码节点数 / 默认容量 | ✅ | `select_depot` / `plan_deliveries` 全从 `ScenarioBundle` 读取 |
| §3.3 图层不被其他层反向依赖 | ✅ | `scheduling` 仅 import `graph` 与 `algorithms` 子集，不写 |
| §3.6 单车辆 | ✅ | `ScheduleResult.vehicle_id` 唯一；4-vehicle 仅为模型保留 |
| §3.6 闭合回路 | ✅ | `RoutePlan.__post_init__` 强制 `stop_sequence[0] == stop_sequence[-1] == depot_id` |
| §3.6 如实报告不可行订单 | ✅ | `Violation.kind ∈ {"capacity_overflow", "time_window_miss", "unreachable_leg", "no_feasible_next_step", ...}` |
| §3.7 路径复用 Phase 2 Dijkstra | ✅ | `PathProvider.shortest_path` 是唯一桥接；`cross_metrics` 复用避免重算 |
| §3.7 路径缓存键 `(graph_version, source, target, metric)` | ✅ | `graph_identity` + `_graph_id` 前缀；调度结束实例被 GC |
| §3.7 不强制 `service_end ≤ time_window_end` | ✅ | `feasibility.py:182-200` 注释；测试 `test_service_end_overflow_not_a_violation` 验证 |
| §3.7 主目标 ∈ {distance, cost}，`travel_time` 仅对比列 | ✅ | `planner.ALLOWED_OBJECTIVES`；`InvalidObjectiveError` 拒绝 `travel_time` |
| §4 类型注解 / `from __future__ import annotations` | ✅ | 所有公开接口 |
| §5 测试仅用 `unittest` | ✅ | 0 引入 pytest |

---

## 7. 端到端验证命令

```bash
# 全部单元测试
PYTHONPATH=src python -m unittest discover -s tests -t .

# 仅 Phase 3 调度层
PYTHONPATH=src python -m unittest tests.test_scheduling_planner -v
PYTHONPATH=src python -m unittest tests.test_phase3_regression -v

# 演示
PYTHONPATH=src python scripts/demo_phase3.py
```

---

## 8. 已知边界 / 后续 Phase 入口

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Phase 4 — 随机场景生成（仍单车） | ⏳ 待启动 | 详见 `docs/development-plan.md` |
| Phase 5 — React Dashboard（单车可视化） | ⏳ 待启动 | 数据通过 Phase 6 FastAPI 传输 |
| Phase 6 — FastAPI + 动态事件（单车重路由） | ⏳ 待启动 | 增量事件接口；重规划仍保持单车 |

按 `AGENTS.md` §8「完成每一阶段后立即停止，等待审查」，本阶段到此终止，等待用户审查与下一步指令。
