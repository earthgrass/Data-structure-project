# LogiRoute — 电商物流配送路径规划系统

> 数据结构课程设计 —— 一个以有向带权图为核心的电商物流配送仿真与优化项目。

LogiRoute 模拟城市电商物流配送网络：节点表示仓库、客户与中转站，边表示实际道路，
并通过自定义图结构与（后续阶段的）路径规划算法，提供最短距离、最短时间、最低成本
与多目标优化等能力，最终面向可交互的 Web Dashboard 开放。

## 当前开发阶段

**Phase 1 — 工程初始化与核心数据结构 ✅ 已完成**

* 项目骨架、配置（pyproject.toml）、`.gitignore`、包目录结构
* 业务数据模型：`Node`、`Edge`、`Vehicle`、`Courier`、`Order`，含字段级校验
* `LogisticsGraph`：邻接表存储 + 邻接矩阵导出，节点 / 边增删与一致性维护
* 单元测试：pytest，**115 个用例全部通过**
* 项目文档与协作约束（`README.md`、`docs/*`、`AGENTS.md`）

后续 Phase 仅在收到明确指令后实施。

## 项目结构

```
数据结构课设/
├── README.md                 项目说明（必读）
├── AGENTS.md                 协作约束（面向 AI 编程助手）
├── pyproject.toml            构建 / 测试配置
├── .gitignore                忽略规则
│
├── src/logiroute/            主包（src 布局）
│   ├── core/                 业务数据模型
│   ├── graph/                LogisticsGraph 实现
│   ├── algorithms/           路径规划（Phase 2+，仅占位）
│   ├── dispatch/             配送调度（Phase 2+，仅占位）
│   ├── config/               配置加载（Phase 2+，仅占位）
│   ├── api/                  FastAPI 后端（Phase 2+，仅占位）
│   └── web/                  前端占位
│
├── tests/                    pytest 单元测试
│
└── docs/                     架构、阶段计划等文档
```

## 环境要求

| 项目  | 版本 |
| ----- | ---- |
| Python | ≥ 3.11 |
| pytest | ≥ 8.0 |

> Python 3.10 及以下将导致 dataclass `slots=True`、`match` 等语法可用性下降。推荐 3.11+。

## 安装与运行测试

仓库当前仅包含开发依赖，**不需要**额外依赖安装 —— 直接使用系统 Python 与 pip 中的 pytest
即可：

```bash
# 在项目根目录
python -m pytest
```

如需在本地构建隔离环境：

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

### 运行指定文件 / 用例

```bash
pytest tests/test_graph.py                       # 仅跑图测试
pytest -k "TestEdgeValidation"                   # 按类名筛选
pytest -m phase1                                # 仅跑 Phase 1 标记的测试
pytest --maxfail=1 -v                            # 失败即停，详尽输出
```

### 测试覆盖范围（Phase 1）

| 模块                 | 用例数 |
| -------------------- | ------ |
| Node 模型与校验       | 19 |
| Edge 模型与方向性     | 30 |
| Vehicle 模型与装卸    | 11 |
| Courier 模型与状态    | 9 |
| Order 模型与时间窗口  | 9 |
| **LogisticsGraph**   | **37** |
| **合计**             | **115** |

## 快速示例

```python
from logiroute.core import Node, Edge, NodeType
from logiroute.graph import LogisticsGraph

g = LogisticsGraph()
g.add_node(Node("W1", "主仓", NodeType.WAREHOUSE, 0.0, 0.0))
g.add_node(Node("C1", "客户1", NodeType.CUSTOMER, 1.0, 1.0))
g.add_node(Node("C2", "客户2", NodeType.CUSTOMER, 2.0, 0.0))
g.add_edge(Edge("W1", "C1", distance=1.5, travel_time=2.0, cost=1.0))
g.add_edge(Edge("C1", "C2", distance=1.0, travel_time=1.5, cost=0.8))
g.add_edge(Edge("W1", "C2", distance=2.0, travel_time=2.5, cost=1.5))

print(g)                                  # LogisticsGraph(nodes=3, edges=3)
adj = g.to_adjacency_list()
ids, matrix = g.to_adjacency_matrix(metric="distance")
```

## 文档导航

* [`docs/architecture.md`](docs/architecture.md)：系统分层架构、模块依赖、数据流
* [`docs/development-plan.md`](docs/development-plan.md)：后续 Phase 路线图与边界
* [`AGENTS.md`](AGENTS.md)：供 Claude Code / Codex 等 AI 编程助手遵循的协作约束

## 开发守则

* **测试先行 / 测试通过才能提交**：所有新增功能必须经 pytest 验证。
* **不要把后续阶段的工作提前引入**：当前处于 Phase 1。
* **数据模型与算法 / Web 框架解耦**：`core/` 不引用任何 FastAPI、NetworkX 等。
* **保持简洁**：避免无意义的设计模式与抽象层。

## 许可证

MIT（仅本项目代码；课程相关文档归原作者所有）。
