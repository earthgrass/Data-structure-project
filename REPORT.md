# 《电商物流配送路径规划系统 LogiRoute》

## 数据结构课程设计报告 —— Phase 1

---

| 项 | 内容 |
| --- | --- |
| 项目名称 | **LogiRoute — 电商物流配送路径规划系统** |
| 课程 | 数据结构课程设计 |
| 报告阶段 | **Phase 1 —— 工程初始化、配置驱动与核心数据结构** |
| 提交日期 | 2026-10-12 |
| 仓库 | `https://github.com/earthgrass/Data-structure-project` |
| 工作目录 | `数据结构课设` |
| Python 版本要求 | ≥ 3.11 |
| 第三方依赖 | **0 个**（仅使用 Python 标准库） |

---

## 摘要

LogiRoute 是一个用于模拟城市电商物流配送网络的有向带权图系统，使用 Python
手写全部核心数据结构与算法，**不依赖任何第三方图算法库**。本阶段（Phase 1）完成了：

1. 项目骨架、目录约定、`.gitignore`、`pyproject.toml` 等基础设施；
2. 业务数据模型 `Node` / `Edge` / `Vehicle` / `Courier` / `Order`；
3. 有向带权图容器 `LogisticsGraph`（邻接表为唯一可变状态，邻接矩阵按需导出）；
4. 配置加载层 `logiroute.config.loader`，含连通性自检与字段级校验；
5. 固定标准场景 `config/scenario.json`（35 节点 / 192 边 / 强连通 / 4 车辆 / 20 订单）；
6. 121 个 `unittest` 单元测试，全部通过；
7. 完整的项目文档、协作约束、提交记录与 GitHub 远程同步。

> **重要原则**：本项目严格遵循「教师要求」—— 所有核心数据结构与算法均**手工实现**，
> 禁止调用 `networkx`、`numpy`、`scipy`、`ortools` 等现成求解库；后续 Phase 2 实现
> Dijkstra 时也禁止使用 `heapq`、`sorted()` 等已封装好的工具。

---

## 一、项目背景与目标

### 1.1 业务背景

随着电商业务快速发展，城市配送网络日益复杂。实际物流系统需要支持：

* 多仓库 / 客户点 / 中转站的有向道路建模；
* 道路的距离、时间、成本三个互不相关的度量；
* 车辆 / 配送员 / 订单三类资源的多对多映射；
* 时间窗口、载重约束、优先级等业务规则；
* 后续阶段的动态交通与重规划。

### 1.2 课程目标

本课程设计要求学生：

* 自主设计并实现核心数据结构（**禁止**使用现成图算法库）；
* 自主实现路径规划算法（**禁止**使用 `heapq`、`sorted` 等封装好的排序 / 堆工具替代课程展示内容）；
* 通过**配置驱动**取代硬编码业务参数；
* 在 Git / GitHub 上完成多阶段提交、推送与代码审查。

### 1.3 总体路线

| Phase | 内容 | 状态 |
| --- | --- | --- |
| 1 | 工程初始化、配置驱动、核心数据结构 | ✅ 已完成 |
| 2 | 手写最小堆 + 手写 Dijkstra | ⏳ |
| 3 | 多目标综合优化（距离 / 时间 / 成本线性加权） | ⏳ |
| 4 | TSP / VRP 配送顺序 + 时间窗口硬约束 | ⏳ |
| 5 | 随机场景生成器 + 动态交通 + 增量式重规划 | ⏳ |
| 6 | FastAPI 后端 API | ⏳ |
| 7 | React + TypeScript 前端 Dashboard | ⏳ |

---

## 二、系统分层与模块设计

### 2.1 分层架构

```
+-----------------------------------------------------------------+
|  Web Frontend  (Phase 7，独立工程)                                |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  FastAPI Service  (Phase 6)                                      |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Scheduling / Simulation  (Phase 4-5)                            |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Algorithms  (Phase 2+  手工实现 Dijkstra 等)                    |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Config Loader —— JSON -> ScenarioBundle -> LogisticsGraph       |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Core + Graph  (零三方依赖)                                      |
+-----------------------------------------------------------------+
```

依赖箭头单向向下；下层不感知上层。

### 2.2 模块清单与职责

| 包 / 模块 | 职责 | 依赖 | Phase 1 状态 |
| --- | --- | --- | --- |
| `logiroute.core` | 业务数据模型：Node / Edge / Vehicle / Courier / Order + 6 个枚举 | stdlib | ✅ 完整 |
| `logiroute.graph` | 有向带权图容器 LogisticsGraph | `core` | ✅ 完整 |
| `logiroute.config` | JSON 场景配置加载与校验 | `core` / `graph` | ✅ 完整 |
| `logiroute.algorithms` | 路径规划（**手工实现**） | `core` / `graph` | ⏳ 占位 |
| `logiroute.scheduling` | 配送调度 | `core` / `graph` / `algorithms` | ⏳ 占位 |
| `logiroute.simulation` | 随机场景 / 动态事件 | `core` / `graph` | ⏳ 占位 |
| `logiroute.api` | FastAPI 后端 | `core` / `graph` / `config` | ⏳ 占位 |
| `logiroute.web` | 前端 Dashboard 占位 | - | ⏳ 占位 |

---

## 三、核心数据结构详细设计

### 3.1 Node —— 不可变节点

```python
@dataclass(frozen=True)
class Node:
    id: str
    name: str
    node_type: NodeType
    x: float
    y: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

* `id` —— 唯一标识；
* `node_type` —— `NodeType.WAREHOUSE` / `CUSTOMER` / `TRANSFER`；
* `(x, y)` —— 二维示意坐标，与地图投影 / 真实地理解耦；
* 不可变（`frozen=True`）—— 任何"改坐标"语义都应是"删 + 增"，避免与图索引失同步。

**校验**：`id` / `name` 非空；`x` / `y` 必须是有限数（非 NaN / inf）。

**便利方法**：`distance_to(other)` 提供与同图节点的欧氏距离。

### 3.2 Edge —— 有向带权边

```python
@dataclass
class Edge:
    source_id: str
    target_id: str
    distance: float
    travel_time: float
    cost: float
    traffic_status: TrafficStatus = TrafficStatus.CLEAR
    metadata: dict[str, Any] = field(default_factory=dict)
```

* **方向性**：`A → B` 存在不代表 `B → A` 自动存在；课程要求保留方向信息；
* **三类权重解耦**：`distance / travel_time / cost` 独立存储，独立参与算法度量切换；
* **状态字段**：`traffic_status` 用于后续动态交通的扩展，Phase 1 仅作为可观测属性。

**校验**：`source_id` / `target_id` 非空且不相等；三种权重均 ≥ 0 且为有限数。

**便利方法**：

```python
@property
def key(self) -> tuple[str, str]:
    return (self.source_id, self.target_id)

def weight(self, metric: str) -> float:
    if metric == "distance":     return self.distance
    if metric == "travel_time":  return self.travel_time
    if metric == "cost":         return self.cost
    raise ValueError(f"unknown weight metric: {metric!r}")
```

### 3.3 Vehicle —— 配送车辆

```python
@dataclass
class Vehicle:
    id: str
    capacity: float
    current_load: float = 0.0
    current_node_id: str = ""
    status: VehicleStatus = VehicleStatus.IDLE
    metadata: dict[str, Any] = field(default_factory=dict)
```

* `capacity` —— 最大载重（业务单位 kg / 件数等由调用方约定）；
* `current_load` —— 当前载重，构造时必须 `≤ capacity`；
* `status` —— 状态机：`IDLE / LOADING / DELIVERING / RETURNING / MAINTENANCE`；
* 车辆与配送员相互独立：同一辆车不同时刻可由不同配送员驾驶。

**行为**：含 `load / unload / can_load / remaining_capacity` 等装卸货校验；`mark_delivering`
从非 `MAINTENANCE` 状态进入；从 `MAINTENANCE` 转入 `DELIVERING` 一律拒绝。

### 3.4 Courier —— 配送员

```python
@dataclass
class Courier:
    id: str
    name: str
    vehicle_id: str           # 字符串引用，避免与 Vehicle 循环组合
    status: CourierStatus = CourierStatus.IDLE
    metadata: dict[str, Any] = field(default_factory=dict)
```

* 状态机：`IDLE / DELIVERING / RESTING / OFFLINE`；
* `is_dispatchable` 在 `IDLE / DELIVERING` 时为 `True`，便于调度；
* `assign_vehicle(new_vehicle_id)` 支持人员 / 车辆再分配。

### 3.5 Order —— 配送订单

```python
@dataclass
class Order:
    id: str
    destination_id: str
    demand: float
    time_window_start: float
    time_window_end: float
    priority: OrderPriority = OrderPriority.NORMAL
    status: OrderStatus = OrderStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
```

* `destination_id` —— 客户节点 ID；
* `time_window_*` —— 送达时间窗口（分钟，相对于当日零点）；
* `priority` —— `NORMAL / URGENT`；
* `status` —— 状态机：`PENDING / IN_TRANSIT / DELIVERED / EXPIRED`。

**校验**：`start < end` 且均为有限数；`demand ≥ 0`。

**便利方法**：`is_within_window(arrival_minute)` 闭区间判定；`time_window_length` 取窗口长度。

### 3.6 枚举

| 枚举 | 取值 |
| --- | --- |
| `NodeType` | `warehouse` / `customer` / `transfer` |
| `TrafficStatus` | `clear` / `light` / `moderate` / `congested` / `blocked` |
| `VehicleStatus` | `idle` / `loading` / `delivering` / `returning` / `maintenance` |
| `CourierStatus` | `idle` / `delivering` / `resting` / `offline` |
| `OrderPriority` | `normal` / `urgent` |
| `OrderStatus` | `pending` / `in_transit` / `delivered` / `expired` |

所有枚举继承 `str, Enum`，既具备类型安全，又便于 JSON 序列化。

---

## 四、图结构 —— LogisticsGraph

### 4.1 设计理由

课程要求"邻接表"作为主要存储结构；同时为后续路径算法（特别是矩阵化的 Floyd）保留
**按需生成邻接矩阵**的导出能力。本设计权衡了：

* **内存效率**：邻接表只存储真实存在的边（V+E），适合稀疏路网；
* **查询效率**：节点 / 邻接 / 边存在性均可 O(1) 命中；
* **维护一致性**：通过反向邻接索引（`_in_edges`）支持 O(deg) 的节点删除；
* **避免双份状态**：邻接矩阵按需从邻接表生成，不重复维护，避免双源状态同步问题。

### 4.2 内部存储

```python
__slots__ = ("_nodes", "_out_edges", "_in_edges")

_nodes     : Dict[node_id, Node]                                  O(1) 节点查找
_out_edges : Dict[source_id, Dict[target_id, Edge]]               出边邻接表
_in_edges  : Dict[target_id, Dict[source_id, Edge]]               反向邻接表
```

> `__slots__` 收紧实例内存，便于在大规模网络下减少 Python 对象开销。

### 4.3 关键操作与复杂度

| 方法 | Time | Space | 行为 |
| --- | --- | --- | --- |
| `add_node(node)` | O(1) avg | O(1) | 加入新节点，ID 重复抛 `DuplicateNodeError` |
| `remove_node(id)` | O(deg_in + deg_out) | O(1) | 原子化清理双向邻接后删除节点 |
| `add_edge(edge)` | O(1) avg | O(1) | 端点不存在抛 `UnknownNodeError`；同对重复抛 `DuplicateEdgeError` |
| `remove_edge(s, t)` | O(1) avg | O(1) | 边不存在抛 `GraphError` |
| `get_node(id)` / `try_get_node` | O(1) avg | O(1) | 节点查询 |
| `get_neighbors(id)` | O(deg_out) | O(deg_out) | 出边列表 |
| `get_in_edges(id)` | O(deg_in) | O(deg_in) | 入边列表 |
| `get_all_nodes()` / `get_all_edges()` | O(V) / O(E) | O(V) / O(E) | 全量快照 |
| `get_adjacency_list()` | O(V + E) | O(V + E) | 序列化字典，按 target_id 升序 |
| `get_adjacency_matrix(metric)` | O(V + E) | O(V²) | 矩阵按需生成；无直接边 = `inf` |
| `validate()` | O(V + E) | O(V) | 内部一致性自检 |

### 4.4 自环与多边策略

* **自环**：`Edge.__post_init__` 与 `LogisticsGraph.add_edge` 双重拒绝；
* **多边**（同对 source/target 多条边）：**Phase 1 暂不支持**，重复添加抛 `DuplicateEdgeError`。
  引入多道路并联的语义复杂度属于 Phase 5+ 的议题。

### 4.5 删除节点的边清理（核心逻辑）

```python
def remove_node(self, node_id: str) -> None:
    if node_id not in self._nodes:
        raise UnknownNodeError(node_id)
    # 1) 删除作为 source 的所有出边
    for target_id, edge in list(self._out_edges.get(node_id, {}).items()):
        self._in_edges.get(target_id, {}).pop(node_id, None)
    self._out_edges.pop(node_id, None)
    # 2) 删除作为 target 的所有入边
    for source_id in list(self._in_edges.get(node_id, {}).keys()):
        self._out_edges.get(source_id, {}).pop(node_id, None)
    self._in_edges.pop(node_id, None)
    # 3) 删除节点
    self._nodes.pop(node_id, None)
```

* 仅扫描与该节点直接相连的边，时间复杂度 O(deg_in + deg_out)；
* 双向索引同步更新，确保 `validate()` 在删除后仍然通过。

### 4.6 邻接矩阵输出语义

```python
node_ids, matrix = graph.get_adjacency_matrix(metric="distance")
# matrix[i][j] == 边权 (source = node_ids[i], target = node_ids[j])
# matrix[i][j] == float('inf')  # 无直接边（默认占位）
# matrix[i][i] == float('inf')  # 自环
```

* 哨兵值 `float('inf')` 是图论 / 矩阵运算标准做法，便于 Phase 2 Dijkstra 直接消费；
* 行列顺序可通过 `node_order=` 参数指定，默认按插入顺序。

### 4.7 自定义异常

| 异常 | 触发条件 |
| --- | --- |
| `GraphError` | 通用图操作错误基类 |
| `DuplicateNodeError` | 节点 ID 重复 |
| `DuplicateEdgeError` | 同对节点边重复 |
| `UnknownNodeError` | 访问不存在的节点 |

---

## 五、配置驱动层

### 5.1 配置文件结构

`config/scenario.json` 顶层 7 个段：

```jsonc
{
  "scenario":    { "name", "mode", "random_seed" },
  "network":     { "directed", "nodes", "edges" },
  "vehicles":    [ {"id", "capacity", "current_load", "current_node_id", "status"}, ... ],
  "couriers":    [ {"id", "name", "vehicle_id", "status"}, ... ],
  "orders":      [ {"id", "destination_id", "demand",
                     "time_window_start", "time_window_end",
                     "priority", "status"}, ... ],
  "simulation":  { "initial_time", "traffic_update_interval",
                   "congestion_threshold", "service_time" },
  "optimization":{ "default_objective", "weights",
                   "late_penalty_per_minute", "expiry_grace_minutes" }
}
```

**已落地固定场景摘要**

| 指标 | 值 |
| --- | --- |
| 节点数 | 35（≥30 ✓） |
| 仓库数 | 2（≥2 ✓） |
| 客户数 | 29（≥15 ✓） |
| 中转站数 | 4（≥3 ✓） |
| 边数 | 192（≥50 ✓） |
| 强连通 | 是（手写 Kosaraju 验证） |
| 车辆 | 4 辆（容量 100 / 150 / 120 / 200） |
| 配送员 | 4 人 |
| 订单 | 20 个（覆盖 20 个客户） |
| Seed | 42（保证可复现） |

### 5.2 加载器校验

`logiroute.config.loader.load_scenario_from_dict(data)` 依次执行：

1. 段存在性检查（scenario / network / vehicles / couriers / orders / simulation / optimization）；
2. 课程下界指标检查（`ScenarioLimits`，frozen dataclass）；
3. `mode` 必须是 `"fixed"`（随机生成推迟至 Phase 5+）；
4. 节点 / 边 / 车辆 / 配送员 / 订单 ID 唯一性；
5. 跨段引用完整性（`current_node_id` / `vehicle_id` / `destination_id`）；
6. 边权非负、有限；自环、重复边、未知端点拒绝；
7. 时间窗口合法性；
8. **连通性自检（手写 Kosaraju 双 DFS）**：弱连通 + 强连通；
9. `default_objective ∈ {distance, travel_time, cost}`；
10. 状态枚举 / 优先级枚举取值集合合法。

**任何校验失败均抛 `ConfigError`，附带字段路径（如 `network.edges[3].distance`）便于定位。**

### 5.3 配置 vs 代码 —— 思维定式

| 项 | 必须配置 | 允许在代码 |
| --- | :---: | :---: |
| 节点 / 边 ID | ✅ | ❌ |
| 边权（距离 / 时间 / 成本） | ✅ | ❌ |
| 节点坐标 | ✅ | ❌ |
| 车辆容量 / 起始位置 / 状态 | ✅ | ❌ |
| 订单时间窗口 / 需求量 | ✅ | ❌ |
| 默认优化权重 | ✅ | ❌ |
| 状态机迁移规则 | ❌ | ✅ |
| 基础校验逻辑 | ❌ | ✅（与模型共存） |

### 5.4 手写强连通性自检

```python
def _is_strongly_connected(graph, nodes) -> bool:
    node_ids = [n.id for n in nodes]
    fwd = {n: [] for n in node_ids}
    rev = {n: [] for n in node_ids}
    for src in node_ids:
        for edge in graph.get_neighbors(src):
            fwd[src].append(edge.target_id)
            rev[edge.target_id].append(src)
    start = node_ids[0]
    if not _dfs(start, fwd, set(node_ids)):
        return False
    if not _dfs(start, rev, set(node_ids)):
        return False
    return True

def _dfs(start, adjacency, all_ids) -> bool:
    visited, stack = set(), [start]
    while stack:
        u = stack.pop()
        if u in visited: continue
        visited.add(u)
        for v in adjacency.get(u, []):
            if v not in visited: stack.append(v)
    return visited == all_ids
```

> **完全基于 Python 内置数据结构**（`list` / `set` / `dict`），**未**调用任何算法库。

---

## 六、测试体系

### 6.1 测试框架

* **使用标准库 `unittest`**，未引入 pytest；
* 测试文件命名 `tests/test_<module>.py`；
* 使用 `setUp` / 工厂函数管理 fixture，不依赖第三方 fixture 机制。

### 6.2 用例分布

| 测试文件 | 用例数 | 关注点 |
| --- | --- | --- |
| `tests/test_nodes.py` | 13 | 节点创建、冻结、校验、欧氏距离 |
| `tests/test_edges.py` | 16 | 边创建、校验、自环、负权、方向性、权重切换 |
| `tests/test_vehicles.py` | 15 | 默认值、容量、装卸、状态机 |
| `tests/test_couriers.py` | 9 | 创建、状态机、可派单性 |
| `tests/test_orders.py` | 10 | 时间窗口、优先级 |
| `tests/test_graph.py` | 35 | 节点 / 边增删、自环、负权、ID 唯一、边清理、邻接表 / 矩阵导出、**大型场景形状检查** |
| `tests/test_config.py` | 21 | 加载、字段校验、连通性、错误路径、限制默认值 |
| **合计** | **121** | |

### 6.3 测试运行

```bash
PYTHONPATH=src python -m unittest discover -s tests -t .
# → Ran 121 tests in 0.04s — OK
```

### 6.4 关键测试用例示例

#### 6.4.1 节点 ID 唯一性

```python
def test_add_duplicate_node_raises(self):
    g = LogisticsGraph()
    g.add_node(_make_node("A"))
    with self.assertRaises(DuplicateNodeError):
        g.add_node(_make_node("A", name="alias"))
```

#### 6.4.2 自环拒绝

```python
def test_self_loop_rejected(self):
    with self.assertRaises(ValueError):
        Edge(source_id="A", target_id="A",
             distance=1.0, travel_time=1.0, cost=1.0)
```

#### 6.4.3 删除节点后的边清理

```python
def test_remove_node_clears_incoming(self):
    g = _sample_graph()
    g.remove_node("C2")
    self.assertNotIn("C2", g)
    self.assertEqual(g.edge_count, 3)
    g.validate()  # 内部一致性自检
```

#### 6.4.4 邻接矩阵权重

```python
def test_distance_matrix(self):
    g = _sample_graph()
    node_ids, matrix = g.get_adjacency_matrix(metric="distance")
    a, t1, t2, c1, c2 = (node_ids.index(x) for x in ("A", "T1", "T2", "C1", "C2"))
    self.assertEqual(matrix[a][t1], 1.0)  # 边权
    self.assertEqual(matrix[t1][a], math.inf)  # 反向：无边
    self.assertEqual(matrix[a][a], math.inf)    # 自环
```

#### 6.4.5 配置加载失败路径

```python
def test_edge_to_unknown_node(self):
    data = self._base()
    data["network"]["edges"][0]["target"] = "ZZZ"
    with self.assertRaises(ConfigError):
        load_scenario_from_dict(data)
```

---

## 七、Git 与协作管理

### 7.1 提交规范

* **Conventional Commits** 风格：`feat(core): ...` / `fix(graph): ...` / `docs: ...` / `refactor(modules): ...` / `test!: ...`；
* 一次逻辑改动 = 一次提交；
* 提交前必须先跑测试；任何 red test 禁止 push；
* 未经授权**禁止** `force push` / `reset --hard` / 删除他人分支 / 覆盖其他提交。

### 7.2 本阶段提交历史

| Hash | Message |
| --- | --- |
| `8eaa4a2` | chore: initialize project skeleton |
| `25a9ad2` | feat(core): add Node / Edge / Vehicle / Courier / Order models |
| `5cb71a0` | feat(graph): implement LogisticsGraph with adjacency-list storage |
| `c16b52a` | test: add 115 unit tests covering Phase 1 data structures |
| `40952ba` | docs: add project documentation for Phase 1 |
| `86a77e0` | feat(core)!: align model fields with Phase 1 spec |
| `e93fa85` | feat(graph): rename exports to get_* and document complexity |
| `06632fe` | refactor(modules): rename dispatch → scheduling and add simulation |
| `ee0fca9` | feat(config): add strongly-validated scenario loader + fixed scene |
| `d251106` | test!: migrate 121 tests from pytest to unittest stdlib |
| `2b05b43` | docs: refresh Phase 1 docs around hand-rolled / config-driven rules |

**HEAD 哈希**：`2b05b43320a8451811cb6c8f12117d734e99dc7e`
**远程分支**：`origin/main`，与本地 HEAD 完全一致 → **推送成功**。

### 7.3 协作约束（节选自 `AGENTS.md`）

* **禁止**调用 `networkx` / `numpy` / `scipy` / `ortools` 等现成图算法库；
* **禁止**使用 `heapq` 替代自实现优先队列（Phase 2 起）；
* **禁止**使用 `sorted()` 替代课程需展示的排序实现；
* **禁止**硬编码业务参数（节点 ID、容量、时间窗口等）到 Python 源码；
* 任何修改现有文件前**先 Read** 再 Edit / Write；
* 重大重构前**先与用户对齐方案**。

---

## 八、依赖清单

### 8.1 实际引用（仅 9 个标准库模块）

```python
# src/logiroute/core/* 与 graph/* 中可见的全部外部 import：
from __future__ import annotations                       # 标准库内置
from dataclasses import dataclass, field                # 标准库
from enum import Enum                                    # 标准库
from typing import Any                                   # 标准库

# src/logiroute/config/loader.py 中可见的额外 import：
from collections import Counter, deque                   # 标准库
from pathlib import Path                                 # 标准库

# scripts/generate_scenario.py 中可见的额外 import：
import argparse                                          # 标准库
import json                                              # 标准库
import math                                              # 标准库
import random                                            # 标准库
```

### 8.2 测试

```python
import unittest                                          # 标准库（替代 pytest）
```

### 8.3 明确**未**引用

| 类别 | 已禁止 |
| --- | --- |
| 图算法 | `networkx` / `igraph` / `graph-tool` / `networkit` |
| 数值 / 矩阵 | `numpy` / `scipy` / `pandas` / `sympy` / `cython` |
| 路径 / 规划 | `ortools` / `pulp` / `gurobipy` / `cvxpy` |
| 排序 / 堆 | `heapq`（仅在 Phase 2+ 由解释器隐式使用） / `sortedcontainers` / `bisect`（核心算法路径） |
| 测试 | `pytest` / `pytest-cov` / `nose2` |
| Web / 框架 | `fastapi` / `flask` / `uvicorn` / `pydantic`（**直到** Phase 6 授权） |
| 可视化 | `matplotlib` / `plotly` / `vispy`（**直到** Phase 7 授权） |

**净效果**：Phase 1 的全部源代码合并外部 import 列表，仅包含 **9 个 Python 标准库模块**。零第三方运行时 / 开发期依赖。

---

## 九、复杂度分析汇总

### 9.1 图容器

参见 §4.3。

### 9.2 配置加载

| 阶段 | 复杂度 | 备注 |
| --- | --- | --- |
| 字段解析 | O(V + E + |V| + |C| + |O|) | 单次遍历 |
| 节点 / 边下界 | O(1) | 与下限值比较 |
| ID 唯一性 | O(V · k) | `set` 插入均摊 O(1) |
| 跨段引用完整性 | O(V · n) | dict 查找 |
| **强连通性自检** | **O(V + E)** | **手写 Kosaraju 双 DFS** |
| 邻接矩阵导出 | O(V + E) | 单次填充 |

### 9.3 测试

* 单测总耗时 < 0.05s（121 用例）；
* 加载器校验 35 节点 / 192 边 < 1ms。

---

## 十、当前阶段遗留问题

* **算法层空仓**：所有路径规划、调度、优化功能尚未实现 —— 这是 Phase 2+ 的本职；
* **三种 metric 的差异性**尚未被验证（需要 Phase 2 Dijkstra 跑通后断言）；
* **配置加载器对部分字段（如 `simulation.*`）只做最浅校验**，更细粒度校验留到 Phase 5+；
* **无性能基准**：30 节点 / 192 边是合理演示规模，大规模（如 1000+ 节点）需要 Phase 5 之后压测；
* **未提供随机场景**：仅固定场景（`config/scenario.json`）落地；随机生成器设计已在 `docs/architecture.md` 规划，**实现**推迟至 Phase 5+；
* **未提供 CLI / 交互式界面**：所有功能需通过 `python -c "..."` 或测试代码调用。

---

## 十一、Phase 2 实施建议

1. **第一步：自实现最小堆**
   * 文件：`src/logiroute/algorithms/heap.py`
   * 接口：`push(item) / pop_min() / decrease_key(idx, new_key) / __len__ / heapify(items)`
   * 内部基于 `list[T]`，父子索引 `2i+1` / `2i+2`
   * 必须含上浮 / 下沉详细单元测试 + 复杂度证明
2. **第二步：自实现 Dijkstra**
   * 文件：`src/logiroute/algorithms/dijkstra.py`
   * 输入：`graph, source_id, target_id, metric="distance"`
   * 输出：`(total_cost: float, path: list[node_id])`
   * 禁止 `import heapq` / 禁止使用 `sortedcontainers`
3. **第三步：算法文档**
   * 新增 `docs/algorithms-dijkstra.md`：
     - 伪代码
     - 复杂度分析：`O((V + E) log V)`
     - 三种 metric 切换的语义说明
4. **第四步：测试**
   * `tests/test_dijkstra.py` 至少 30 用例
   * 验证三种 metric 在固定场景中产出**不同**的路径
5. **第五步：文档更新**
   * `README.md` 与 `docs/development-plan.md` 把 Phase 2 标记为 ✅

> **范围红线**：在收到「开始 Phase 2」的明确指令前，本项目将**保持 Phase 1 状态不变**，
> 不提前实施任何算法、调度或 Web 层。

---

## 附录 A —— 关键源码摘录

### A.1 LogisticsGraph 删除节点

```python
def remove_node(self, node_id: str) -> None:
    """Time: O(deg_in + deg_out)."""
    if node_id not in self._nodes:
        raise UnknownNodeError(node_id)
    for target_id, edge in list(self._out_edges.get(node_id, {}).items()):
        self._in_edges.get(target_id, {}).pop(node_id, None)
    self._out_edges.pop(node_id, None)
    for source_id in list(self._in_edges.get(node_id, {}).keys()):
        self._out_edges.get(source_id, {}).pop(node_id, None)
    self._in_edges.pop(node_id, None)
    self._nodes.pop(node_id, None)
```

### A.2 LogisticsGraph 邻接矩阵

```python
def get_adjacency_matrix(self, metric="distance", *, node_order=None):
    if metric not in self._SUPPORTED_METRICS:
        raise ValueError(...)
    if node_order is None:
        ordered_ids = list(self._nodes.keys())
    else:
        ordered_ids = list(node_order)
        unknown = [nid for nid in ordered_ids if nid not in self._nodes]
        if unknown:
            raise ValueError(f"unknown node ids: {unknown}")
    index = {nid: i for i, nid in enumerate(ordered_ids)}
    n = len(ordered_ids)
    matrix = [[float("inf")] * n for _ in range(n)]
    for source_id, out_map in self._out_edges.items():
        if source_id not in index: continue
        i = index[source_id]
        for target_id, edge in out_map.items():
            if target_id not in index: continue
            matrix[i][index[target_id]] = edge.weight(metric)
    return ordered_ids, matrix
```

### A.3 配置加载器连通性自检

```python
def _is_strongly_connected(graph, nodes) -> bool:
    """手写 Kosaraju 双 DFS。"""
    node_ids = [n.id for n in nodes]
    fwd = {n: [] for n in node_ids}
    rev = {n: [] for n in node_ids}
    for src in node_ids:
        for edge in graph.get_neighbors(src):
            fwd[src].append(edge.target_id)
            rev[edge.target_id].append(src)
    start = node_ids[0]
    if not _dfs(start, fwd, set(node_ids)): return False
    if not _dfs(start, rev, set(node_ids)): return False
    return True

def _dfs(start, adjacency, all_ids) -> bool:
    visited, stack = set(), [start]
    while stack:
        u = stack.pop()
        if u in visited: continue
        visited.add(u)
        for v in adjacency.get(u, []):
            if v not in visited: stack.append(v)
    return visited == all_ids
```

---

## 附录 B —— 测试结果详细输出

```
$ PYTHONPATH=src python -m unittest discover -s tests -t .
.........................................................................................................................
Ran 121 tests in 0.037s

OK
```

| 模块 | 通过 / 总数 |
| --- | --- |
| tests.test_nodes | 13 / 13 |
| tests.test_edges | 16 / 16 |
| tests.test_vehicles | 15 / 15 |
| tests.test_couriers | 9 / 9 |
| tests.test_orders | 10 / 10 |
| tests.test_graph | 35 / 35 |
| tests.test_config | 21 / 21 |
| **合计** | **121 / 121** |

---

## 附录 C —— Git 提交与远程同步

```bash
$ git log --oneline --decorate -10
2b05b43 (HEAD -> main, origin/main, origin/HEAD) docs: refresh Phase 1 docs around hand-rolled / config-driven rules
d251106 test!: migrate 121 tests from pytest to unittest stdlib
ee0fca9 feat(config): add strongly-validated scenario loader + fixed scene
06632fe refactor(modules): rename dispatch -> scheduling and add simulation
e93fa85 feat(graph): rename exports to get_* and document complexity
86a77e0 feat(core)!: align model fields with Phase 1 spec
40952ba docs: add project documentation for Phase 1
c16b52a test: add 115 unit tests covering Phase 1 data structures
5cb71a0 feat(graph): implement LogisticsGraph with adjacency-list storage
25a9ad2 feat(core): add Node / Edge / Vehicle / Courier / Order models

$ git ls-remote origin
2b05b43320a8451811cb6c8f12117d734e99dc7e	HEAD
2b05b43320a8451811cb6c8f12117d734e99dc7e	refs/heads/main
```

* **HEAD 哈希**：`2b05b43320a8451811cb6c8f12117d734e99dc7e`
* **远程仓库**：`https://github.com/earthgrass/Data-structure-project.git`
* **本地与远程一致 → 推送成功**

---

**报告完。**
**Phase 1 已完成，等待审查与下一阶段授权。**
