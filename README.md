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
**Phase 5 — 交互式 Dashboard（FastAPI + React + Vite）✅ 已完成（课程检查冻结版）**

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
| 测试 | 全部用 `unittest`，共 **495 用例**，全部通过（含 seed=42 跨进程复现回归） |
| 文档 | `AGENTS.md` + `docs/architecture.md` + `docs/development-plan.md` + `docs/data-structures-and-algorithms.md` + `docs/algorithms-{minheap,dijkstra,nearest-neighbor,insertion,two-opt}.md` + 各阶段教师答辩 / 终评审材料 + `docs/PHASE3_SUMMARY.md` / `docs/PHASE4_SUMMARY.md`（单文件总览） |

## 课程检查冻结基线（2026-10-17）

> 本轮为周一课程检查冻结版本：只做稳定性验证，**不**接入真实道路 / 实时交通 /
> 动态订单，也**不**启动 Phase 6。

### 实测验收结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| Python 全量测试 | `PYTHONPATH=src python -m unittest discover -s tests -t .` | **495 用例，OK，退出码 0** |
| 前端类型检查 | `cd frontend && npm run typecheck` | **0 错误，退出码 0** |
| 前端生产构建 | `cd frontend && npm run build` | **成功（44 modules，输出 `frontend/dist/`）** |
| 后端端到端 | `TestClient` + 真实 uvicorn / Vite 代理 | health / random / plan / compare 全部 200 |
| seed=42 跨进程复现 | 不同 `PYTHONHASHSEED` 子进程 | 图、订单、distance / cost 路线与总额完全一致 |

### 固定演示场景（seed=42，随机生成的假设物流场景）

| 指标 | distance 模式 | cost 模式 |
| --- | --- | --- |
| 是否可行 | True | True |
| 送达订单 | 20 / 20 | 20 / 20 |
| 单车辆 | VH1（250 kg） | VH1（250 kg） |
| 闭合回路 | W1 → … → W1 | W1 → … → W1 |
| 总距离 | 1887.917 | 1808.696 |
| 总成本 | 4475.234 | 4128.650 |
| 总行驶时间（仅对比列） | 2512.982 | 2390.511 |
| 峰值载重 | 194.9 / 250.0 | 194.9 / 250.0 |

> 上述数字来自 `plan_deliveries(..., objective=...)` 的实际输出；每条 leg 的
> `cross_metrics` 累加与 `total_distance / total_cost / total_travel_time` 一致，
> 未做任何人工修正。

### 当前数据与地图口径（答辩时必须说明）

* **场景是随机生成的假设物流场景**：`POST /api/scenario/random {seed:42}` 由
  Phase 4 生成器构造；`config/scenario.json` 是另一份手工确定性固定场景。
  两者都**不是**真实电商订单或真实道路数据。
* **地图是示意底图**：前端北京 16 区 GeoJSON / 抽象坐标投影仅用于示意节点与
  路线，不是 OSM 瓦片，也不提供真实道路导航。
* **没有接入实时交通**：`travel_time` / `cost` 来自生成器的规则采样；
  `traffic_status` 默认 `clear`，不含实时拥堵数据。
* **严格单车辆**：只有 VH1 参与配送，路线必须从仓库出发并回到同一仓库。
* **启发式而非全局最优**：统一规划器 = 可行插入（CFI）+ 受约束 2-opt；
  不保证全局最优，也不承诺 distance 模式在所有指标上支配 cost 模式。
* **已知现象（如实报告）**：在 seed=42 上，cost 模式得到的路线恰好在距离与
  成本两项都更小。原因是两种主目标的 CFI 构造种子不同，2-opt 各自落入不同的
  可行局部最优；这**不是**指标串味 —— 已逐 leg 校验两种模式各自只使用自己的
  metric，且累计值一致；并对两条路线分别枚举 190 个可行反转，均无单段反转能
  改善各自主目标，确认已到达 2-opt 局部最优。
* **尚未实现**：真实道路网络、实时交通、动态订单、多车辆、跨车调度。

### 下一阶段（设计存档，本轮未实施）

基于 BJUT 周边真实道路网络的物流规划设计见
[`docs/phase6-bjut-road-network-design.md`](docs/phase6-bjut-road-network-design.md)。
本轮**没有**下载或接入任何真实道路 / 交通数据。

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
│   ├── simulation/           占位（后续阶段）
│   ├── api/                  FastAPI 场景 / 规划 / 比较路由（Phase 5）
│   └── web/                  预留入口（前端工程位于 frontend/）
│
├── tests/                    unittest 单元测试（495 用例，含调度、随机场景与跨进程复现回归）
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

**一键启动（推荐）**：

| 系统 | 命令 |
| --- | --- |
| Windows (cmd / PowerShell) | `scripts\dev.bat` |
| Unix / Git Bash / WSL | `bash scripts/dev.sh` |

脚本会自动开两个窗口分别跑后端 (`:8000`) 与前端 (`:5172`)，并按需执行 `npm install`。

**手动分终端启动**：

```bash
# 1. 终端 A —— 启动 FastAPI 后端（默认 :8000）
PYTHONPATH=src python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000

# 2. 终端 B —— 启动 Vite 前端开发服务器（默认 :5172，详见 frontend/vite.config.ts）
cd frontend
npm install   # 首次需要
npm run dev
```

打开浏览器访问 `http://localhost:5172`。

> **重要**：浏览器打开前**必须**先确保两个服务都在运行。后端未启动时，
> Vite 代理会返回空 body 的 HTTP 500；前端会以红色横幅提示
> `⚠ 场景生成失败 [proxy_error] Vite 代理未能连接后端服务` 并附带
> 启动命令。

* Vite proxy 已把 `/api/*` 转发到 `http://127.0.0.1:8000`（见 `frontend/vite.config.ts`）。
* 后端单独 ``GET /docs`` 可访问 Swagger UI。
* **算法核心全部复用 Phase 1-4 已交付模块**，前端**不**重新实现
  Dijkstra / NN / CFI / 2-opt / 随机生成器（AGENTS §3.7）。

> Windows PowerShell 下等价启动命令：
>
> ```powershell
> $env:PYTHONPATH="src"
> python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000
> ```
>
> 若 5172 已被之前的 Vite 进程占用，直接复用该进程即可（Vite 读取当前源码）。

### 课程检查演示步骤（固定 seed=42）

1. 启动后端（终端 A）与前端（终端 B），浏览器打开 `http://localhost:5172`。
2. 侧边栏 **seed 保持 42**，点击「生成场景」；确认校验面板显示
   `feasible=True`、20 单、50 节点 / 157 边。
3. 选择 **distance** 主目标点击「运行规划」；记录总距离 / 总成本 / 送达数。
4. 切换到 **cost** 主目标再次运行；使用「双目标比较」并排查看。
5. 检查结果面板：单车辆 VH1、首尾均为 W1、20/20 送达、峰值载重 ≤ 250 kg。
6. 可选命令行复核：

   ```bash
   PYTHONPATH=src python -m unittest discover -s tests -t .      # 495 OK
   PYTHONPATH=src python -m unittest tests.test_seed_reproducibility -v
   ```

> 演示口径：场景是随机生成的**假设**物流场景，地图是**示意**底图，
> **没有**接入真实道路导航或实时交通数据；规划器是启发式，**不**保证全局最优。

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
| **tests.test_scheduling_unified** (Phase 5) | 17 |
| **tests.test_phase5_stress** (Phase 5, 20 seed × 2 obj) |  6 |
| **tests.test_phase5_objective_tradeoff** (Phase 5, distance vs cost) | 10 |
| **tests.test_api** (Phase 5 FastAPI) | 19 |
| **tests.test_seed_reproducibility** (Phase 5, 跨进程 seed=42) |  1 |
| **合计**                                | **495** |

## 重新生成固定场景

```bash
python scripts/generate_scenario.py --force
```

该脚本使用 `seed=42` 确定性生成固定场景。随机场景生成器已在 Phase 4 实现
（`logiroute.scenario_generator`），本脚本不承担随机生成职责。

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
* [`docs/phase5-teacher-defense.md`](docs/phase5-teacher-defense.md) — **Phase 5 课程检查答辩说明**（演示脚本 + 数据边界 + 常见提问）
* [`docs/phase6-bjut-road-network-design.md`](docs/phase6-bjut-road-network-design.md) — **下一阶段设计存档**：BJUT 周边真实道路网络（本轮未实施）

## 范围红线

* **禁止**使用 NetworkX / NumPy / SciPy / OR-Tools 等现成求解库；
* **禁止**使用 `heapq` 替代自己实现的优先队列（Phase 2 起 Dijkstra 必须自实现堆）；
* **禁止**使用 `sorted()` / 其它库函数替代课程需展示的排序；
* **禁止**将业务参数硬编码到 Python 源码 —— 一律走 JSON 配置；
* 后续阶段未经许可**禁止**提前启动。

## 许可证

MIT（仅本项目代码；课程相关文档归原作者所有）。
