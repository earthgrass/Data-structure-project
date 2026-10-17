# LogiRoute — 电商物流配送路径规划系统

> 数据结构课程设计 —— 一个以手写有向带权图为核心的电商物流配送仿真与优化项目。
>
> **本项目仅使用 Python 标准库；所有核心数据结构与算法均手工实现，不引入
> NetworkX / NumPy / SciPy / OR-Tools 等第三方图算法库。Dijkstra 与最小堆
> 完全手写，不使用 ``heapq``。**

## 当前开发阶段

**Phase 1 — 工程初始化、配置驱动与核心数据结构 ✅ 已完成**  
**Phase 2 — 手写最小堆 + Dijkstra 最短路径（distance / travel_time / cost） ✅ 已完成**  
**Phase 3 — 单车辆配送路径规划（NN / 可行插入 / 2-opt） ✅ 已完成**  
**Phase 4 — 随机初始化完整物流场景（保持单车辆 + 独立 validator） ✅ 已完成**  
**Phase 5 — 交互式 Dashboard（FastAPI + React + Vite）⏳ 进行中**

> 教师原始题目要求**单车辆**配送：从仓库出发，遍历所有待配送点
> 后返回仓库。历史多车辆方案作废；后续阶段（含 Phase 4 随机场景、
> Phase 5 Dashboard、Phase 6 动态重规划）均必须遵守单车辆约束。
> 详见 [`AGENTS.md`](AGENTS.md) §3.6 与 `docs/development-plan.md`。

| 类别 | 内容 |
| --- | --- |
| 工程骨架 | `pyproject.toml`、`.gitignore`、包目录结构 |
| 数据模型 | `Node` / `Edge` / `Vehicle` / `Courier` / `Order` |
| 图容器 | `LogisticsGraph`（邻接表主存 + 邻接矩阵按需导出） |
| 自实现数据结构 | `ArrayQueue`（FIFO 队列） / `MinHeap`（索引式二叉最小堆） |
| 算法 | BFS 弱连通 / 双向 DFS 强连通 / **Dijkstra 三种 metric** / **最近邻 NN** / **可行插入 CFI** / **受约束 2-opt** |
| 调度层 | `logiroute.scheduling` —— `plan_deliveries(scenario, algorithm, objective)` 统一入口；`PathProvider` 单调度缓存；`check_feasibility` 硬约束 |
| 配置层 | `config/scenario.json` + `logiroute.config.loader` |
| 固定场景 | 35 节点 / 192 有向边 / 强连通 / **严格单车辆 VH1**（容量 250 kg @ W1） / 单配送员 CO1 / 20 订单 |
| 随机场景 | `logiroute.scenario_generator` —— `generate_scenario(config, seed)` 生成完整场景（**严格单车辆**：生成器只造 VH1，loader 拒绝 `len(vehicles) != 1`）；独立 validator 七项校验 |
| 测试 | 全部用 `unittest`，共 **442 用例**，全部通过（含 Phase 4 收尾新增 2 个单车辆负向用例） |
| 文档 | `AGENTS.md` + `docs/architecture.md` + `docs/development-plan.md` + `docs/data-structures-and-algorithms.md` + `docs/algorithms-{minheap,dijkstra,nearest-neighbor,insertion,two-opt}.md` + 各阶段教师答辩 / 终评审材料 + `docs/PHASE3_SUMMARY.md` / `docs/PHASE4_SUMMARY.md`（单文件总览） |

## 项目结构

```
数据结构课设/
├── README.md                 项目入口
├── AGENTS.md                 AI 协作约束（强约束：禁止现成算法包）
├── pyproject.toml            构建配置（无运行期三方依赖）
├── .gitignore
│
├── scripts/
│   └── generate_scenario.py  固定场景 JSON 生成器（确定性）
│
├── config/
│   └── scenario.json         固定场景（35 节点 / 192 边 / 强连通）
│
├── src/logiroute/            主包（src 布局，零三方依赖）
│   ├── core/                 业务数据模型
│   │   ├── enums.py          NodeType / TrafficStatus / VehicleStatus /
│   │   │                     CourierStatus / OrderPriority / OrderStatus
│   │   ├── nodes.py          Node (frozen)
│   │   ├── edges.py          Edge (拒绝自环 / 负权 / NaN)
│   │   ├── vehicles.py       Vehicle (含 status)
│   │   ├── couriers.py       Courier
│   │   └── orders.py         Order (含 time_window)
│   ├── graph/
│   │   └── logistics_graph.py
│   │                         LogisticsGraph（邻接表 + 反向索引 + 矩阵导出）
│   ├── config/
│   │   └── loader.py         强校验的 JSON 加载器，含连通性自检
│   ├── algorithms/           MinHeap + Dijkstra（手写）
│   ├── scheduling/           Phase 3 单车辆配送调度（NN / CFI / 2-opt）
│   ├── scenario_generator/   Phase 4 随机场景生成（RandomSource / 图采样 /
│   │                         backbone / 独立 validator）
│   ├── simulation/           占位（Phase 5+）
│   ├── api/                  占位（Phase 6+ FastAPI）
│   └── web/                  占位（前端独立工程）
│
├── tests/                    unittest 单元测试（440 用例，含调度与随机场景回归）
│
└── docs/
    ├── architecture.md       分层架构 + 随机生成器设计
    ├── development-plan.md   Phase 2-7 路线图
    └── PHASE3_SUMMARY.md /
        PHASE4_SUMMARY.md     各阶段单文件总览
```

## 引用清单（依赖项）

* **运行期**：仅依赖 Python 标准库（`dataclasses`、`enum`、`json`、`collections.deque`、`math`、`pathlib`、`typing`）
* **开发期**：无第三方依赖
* **测试**：`unittest`（标准库）
* **明确未引入**：NetworkX、NumPy、SciPy、OR-Tools、heapq（算法路径）、pandas、matplotlib、pytest
* **Phase 5 后端新增运行期依赖**（**仅** Web 层，非算法核心）：`fastapi`、`uvicorn`、`pydantic`
* **Phase 5 前端新增运行期依赖**（**仅** UI 层，非算法核心）：`react`、`react-dom`（dev: `vite`、`typescript`）

## 环境要求

| 项目  | 版本 |
| ----- | ---- |
| Python | ≥ 3.11 |
| Node.js（仅 Phase 5 Dashboard 需要） | ≥ 18 |

## Phase 5 Dashboard 启动（端到端）

```bash
# 1. 终端 A —— 启动 FastAPI 后端（默认 :8000）
PYTHONPATH=src python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000

# 2. 终端 B —— 启动 Vite 前端开发服务器（默认 :5172，详见 frontend/vite.config.ts）
cd frontend
npm install   # 首次需要
npm run dev
```

打开浏览器访问 `http://localhost:5172`。

* Vite proxy 已把 `/api/*` 转发到 `http://127.0.0.1:8000`（见 `frontend/vite.config.ts`）。
* 后端单独 ``GET /docs`` 可访问 Swagger UI。
* **算法核心全部复用 Phase 1-4 已交付模块**，前端**不**重新实现
  Dijkstra / NN / CFI / 2-opt / 随机生成器（AGENTS §3.7）。

### Phase 5 前端构建产物

```bash
cd frontend
npm run build   # 输出到 frontend/dist/
```

### Phase 5 后端独立测试

```bash
PYTHONPATH=src python -m unittest tests.test_api -v
```

## 运行测试

仓库无第三方依赖，**无需安装** 任何包即可运行：

```bash
# 在项目根目录
PYTHONPATH=src python -m unittest discover -s tests -t .
```

或者在 Linux/macOS 下可忽略盘符：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

### 跑指定的测试类 / 用例

```bash
PYTHONPATH=src python -m unittest tests.test_graph
PYTHONPATH=src python -m unittest tests.test_config.TestValidationErrors.test_edge_to_unknown_node
```

### 当前测试用例分布

| 模块                                    | 用例数 |
| --------------------------------------- | ------ |
| tests.test_nodes                        | 13 |
| tests.test_edges                        | 16 |
| tests.test_vehicles                     | 14 |
| tests.test_couriers                     |  9 |
| tests.test_orders                       |  9 |
| **tests.test_graph**                    | 40 |
| **tests.test_config**                   | 22 |
| **tests.test_queue** (Phase 1)          | 16 |
| **tests.test_phase1_regression** (Phase 1) | 24 |
| **tests.test_heap** (Phase 2)           | 32 |
| **tests.test_dijkstra** (Phase 2)       | 31 |
| **tests.test_scheduling_types** (Phase 3) | 32 |
| **tests.test_scheduling_feasibility**   | 16 |
| **tests.test_scheduling_path_provider** | 21 |
| **tests.test_scheduling_nearest_neighbor** | 23 |
| **tests.test_scheduling_insertion**     | 14 |
| **tests.test_scheduling_two_opt**       | 18 |
| **tests.test_scheduling_planner**       | 16 |
| **tests.test_phase3_regression**        | 15 |
| **tests.test_phase3_10of20_regression** |  8 |
| **tests.test_scenario_generator** (Phase 4) | 11 |
| **tests.test_scenario_generator_random_source** | 12 |
| **tests.test_scenario_generator_graph_sampler** |  8 |
| **tests.test_scenario_generator_backbone_builder** |  6 |
| **tests.test_scenario_generator_validator** |  6 |
| **tests.test_phase4_regression**        | 10 |
| **合计**                                | **442** |

## 重新生成固定场景

```bash
python scripts/generate_scenario.py --force
```

该脚本使用 `seed=42` 确定性生成，**不**实现「随机路网生成器」（后者推迟到 Phase 5+）。

## 快速示例

```python
from logiroute.config import load_scenario

bundle = load_scenario("config/scenario.json")
print(bundle.graph)              # LogisticsGraph(nodes=35, edges=192)

# 邻接表（按 target_id 排序，可复现）
adj = bundle.graph.get_adjacency_list()

# 邻接矩阵（按需生成，不重复维护）
node_ids, m_distance = bundle.graph.get_adjacency_matrix(metric="distance")
node_ids, m_cost     = bundle.graph.get_adjacency_matrix(metric="cost")
node_ids, m_time     = bundle.graph.get_adjacency_matrix(metric="travel_time")
```

## 文档导航

* [`AGENTS.md`](AGENTS.md) — Claude Code / Codex 协作约束（**强约束：核心算法必须手搓**）
* [`docs/architecture.md`](docs/architecture.md) — 分层结构、模块依赖、图实现原理、随机生成器设计
* [`docs/development-plan.md`](docs/development-plan.md) — Phase 2-7 路线图
* [`docs/data-structures-and-algorithms.md`](docs/data-structures-and-algorithms.md) — 数据结构与算法专项设计（教师检查核心讲解材料）
* [`docs/phase1-teacher-defense.md`](docs/phase1-teacher-defense.md) — 第一次课程检查教师答辩材料（5 分钟讲解稿 + 17 Q&A）
* [`docs/PHASE4_SUMMARY.md`](docs/PHASE4_SUMMARY.md) — **Phase 4 单文件总览**：随机场景生成算法设计 + 实现索引 + 实测验收数据 + 教师答辩材料（5 分钟稿 + 24 Q&A）
* [`docs/PHASE3_SUMMARY.md`](docs/PHASE3_SUMMARY.md) — Phase 3 单文件总览

## 范围红线

* **禁止**使用 NetworkX / NumPy / SciPy / OR-Tools 等现成求解库；
* **禁止**使用 `heapq` 替代自己实现的优先队列（Phase 2 起 Dijkstra 必须自实现堆）；
* **禁止**使用 `sorted()` / 其它库函数替代课程需展示的排序；
* **禁止**将业务参数硬编码到 Python 源码 —— 一律走 JSON 配置；
* 后续阶段未经许可**禁止**提前启动。

## 许可证

MIT（仅本项目代码；课程相关文档归原作者所有）。
