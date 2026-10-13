# LogiRoute — 电商物流配送路径规划系统

> 数据结构课程设计 —— 一个以手写有向带权图为核心的电商物流配送仿真与优化项目。
>
> **本项目仅使用 Python 标准库；所有核心数据结构与算法均手工实现，不引入
> NetworkX / NumPy / SciPy / OR-Tools 等第三方图算法库。后续 Phase 实现
> Dijkstra 时也不得使用 ``heapq`` 替代自己实现的优先队列。**

## 当前开发阶段

**Phase 1 — 工程初始化、配置驱动与核心数据结构 ✅ 已完成**

| 类别 | 内容 |
| --- | --- |
| 工程骨架 | `pyproject.toml`、`.gitignore`、包目录结构 |
| 数据模型 | `Node` / `Edge` / `Vehicle` / `Courier` / `Order` |
| 图容器 | `LogisticsGraph`（邻接表主存 + 邻接矩阵按需导出） |
| 配置层 | `config/scenario.json` + `logiroute.config.loader` |
| 固定场景 | 35 节点 / 192 有向边 / 强连通 / 4 车辆 / 4 配送员 / 20 订单 |
| 测试 | 全部用 `unittest`，共 **161 用例**，全部通过 |
| 文档 | `AGENTS.md` + `docs/architecture.md` + `docs/development-plan.md` + `docs/data-structures-and-algorithms.md` + `docs/phase1-teacher-defense.md` |

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
│   ├── algorithms/           占位（Phase 2+ 手工实现 Dijkstra）
│   ├── scheduling/           占位（Phase 4+ 配送顺序规划）
│   ├── simulation/           占位（Phase 5+，含随机生成器设计）
│   ├── api/                  占位（Phase 6+ FastAPI）
│   └── web/                  占位（前端独立工程）
│
├── tests/                    unittest 单元测试（161 用例，含队列 + 回归测试）
│
└── docs/
    ├── architecture.md       分层架构 + 随机生成器设计
    └── development-plan.md   Phase 2-7 路线图
```

## 引用清单（依赖项）

* **运行期**：仅依赖 Python 标准库（`dataclasses`、`enum`、`json`、`collections.deque`、`math`、`pathlib`、`typing`）
* **开发期**：无第三方依赖
* **测试**：`unittest`（标准库）
* **明确未引入**：NetworkX、NumPy、SciPy、OR-Tools、heapq（算法路径）、pandas、matplotlib、pytest、pydantic、fastapi

## 环境要求

| 项目  | 版本 |
| ----- | ---- |
| Python | ≥ 3.11 |

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

| 模块                          | 用例数 |
| ----------------------------- | ------ |
| tests.test_nodes              | 13 |
| tests.test_edges              | 16 |
| tests.test_vehicles           | 14 |
| tests.test_couriers           |  9 |
| tests.test_orders             |  9 |
| **tests.test_graph**          | 40 |
| **tests.test_config**         | 20 |
| **tests.test_queue** (新增)   | 16 |
| **tests.test_phase1_regression** (新增) | 24 |
| **合计**                      | **161** |

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

## 范围红线

* **禁止**使用 NetworkX / NumPy / SciPy / OR-Tools 等现成求解库；
* **禁止**使用 `heapq` 替代自己实现的优先队列（Phase 2 起 Dijkstra 必须自实现堆）；
* **禁止**使用 `sorted()` / 其它库函数替代课程需展示的排序；
* **禁止**将业务参数硬编码到 Python 源码 —— 一律走 JSON 配置；
* 后续阶段未经许可**禁止**提前启动。

## 许可证

MIT（仅本项目代码；课程相关文档归原作者所有）。
