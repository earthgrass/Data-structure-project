# LogiRoute 系统架构

> 本文档描述 LogiRoute 已落地的分层结构、模块责任边界、对象关系、图实现原理、
> 以及**随机场景生成器的设计方案**。代码层细节请配合源码阅读。

## 一、总体分层

```
+-----------------------------------------------------------------+
|  Web Frontend  (Phase 7，独立工程，目前不创建)                     |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  FastAPI Service  (Phase 6，目前包占位)                          |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Scheduling / Simulation  (Phase 4-5，目前包占位)                 |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Algorithms  (Phase 2+，**手工实现** Dijkstra 等)                |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Config Loader —— JSON -> ScenarioBundle -> LogisticsGraph       |
+-----------------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------------+
|  Core + Graph (zero third-party, stdlib only)                    |
+-----------------------------------------------------------------+
```

依赖箭头指向下方；上层禁止反向依赖下层。

## 二、模块责任

### 2.1 `logiroute.core` — 业务数据模型

不依赖任何外部业务库，只使用 Python 标准库（`dataclasses`、`enum`、`math`）。
负责定义字段、字段级校验、不变量与少量便利方法。

| 类 / 枚举 | 角色 | 关键字段 / 行为 |
| --- | --- | --- |
| `Node` (frozen) | 数据 | `id`, `name`, `node_type`, `x`, `y`, `metadata`；``distance_to`` 欧氏距离 |
| `Edge` | 数据 | `source_id`, `target_id`, `distance`, `travel_time`, `cost`, `traffic_status`, `metadata`；``weight(metric)``, `key`；自环 / 负权 / NaN / inf 一律拒绝 |
| `Vehicle` | 行为 | `id`, `capacity`, `current_load`, `current_node_id`, `status`, `metadata`；``load``, ``unload``, ``can_load``, ``remaining_capacity``，状态机 |
| `Courier` | 行为 | `id`, `name`, `vehicle_id` (字符串引用), `status`, `metadata`；``assign_vehicle``, ``mark_delivering``, ``mark_idle``, ``is_dispatchable`` |
| `Order` | 行为 | `id`, `destination_id`, `demand`, `time_window_start/end`, `priority`, `status`, `metadata`；``time_window_length``, ``is_within_window`` |
| `NodeType` / `TrafficStatus` / `VehicleStatus` / `CourierStatus` / `OrderPriority` / `OrderStatus` | 枚举 | 字符串值，便于 JSON 序列化 |

### 2.2 `logiroute.graph` — 有向带权图容器

唯一职责：以邻接表为核心存储，提供节点 / 边的增删查与邻接表 / 邻接矩阵导出，
**不**实现任何路径算法。

#### 2.2.1 数据结构

```
_nodes        : Dict[node_id, Node]
_out_edges    : Dict[source_id, Dict[target_id, Edge]]     -- 邻接表（出边）
_in_edges     : Dict[target_id, Dict[source_id, Edge]]     -- 反向邻接表（入边）
```

* 邻接表是**唯一**可变状态；邻接矩阵按需从邻接表导出，不重复维护；
* ``remove_node`` 同步清理双向邻接索引；``validate()`` 用于自检；
* ``Edge`` 自环在构造时被拒绝；图层亦校验重复与未知端点；
* 异常类型：`GraphError`、`DuplicateNodeError`、`DuplicateEdgeError`、`UnknownNodeError`；
* 关键方法全部带 Time / Space 复杂度注解。

#### 2.2.2 操作接口

| 方法 | Time | Space | 行为 |
| --- | --- | --- | --- |
| `add_node(node)` | O(1) avg | O(1) | 加入新节点，ID 重复抛 `DuplicateNodeError` |
| `remove_node(id)` | O(deg_in + deg_out) | O(1) | 原子化清理双向邻接后删除节点 |
| `add_edge(edge)` | O(1) avg | O(1) | 新增有向边；端点必须存在；同对重复抛 `DuplicateEdgeError` |
| `remove_edge(s,t)` | O(1) avg | O(1) | 删除一条有向边 |
| `get_node(id)` / `try_get_node` | O(1) avg | O(1) | 节点查询 |
| `get_neighbors(id)` | O(deg_out) | O(deg_out) | 出边列表 |
| `get_in_edges(id)` | O(deg_in) | O(deg_in) | 入边列表 |
| `get_all_nodes()` / `get_all_edges()` | O(V) / O(E) | O(V) / O(E) | 全量快照 |
| `get_adjacency_list()` | O(V + E) 主干 + O(Σdeg·log·deg) 排序 | O(V + E) | 序列化字典，按 target_id 升序（**仅**为确定性导出） |
| `get_adjacency_matrix(metric)` | **O(V² + E)** | O(V²) | 按需构造矩阵；V² 来自初始化，E 来自邻接表填充；无直接边 = `inf` |
| `validate()` | O(V + E) | O(V) | 内部一致性自检 |

### 2.3 `logiroute.config` — 配置加载

**单一职责**：将 `config/scenario.json` 解析为强类型的 `ScenarioBundle`。

* 仅使用 Python 标准库 `json` / `pathlib`；**BFS 队列采用自实现的 `ArrayQueue`**（`graph/queue.py`），不依赖 `collections.deque`；
* 校验项：
  - 节点 / 边下界（≥30 / ≥2 仓库 / ≥15 客户 / ≥3 中转 / ≥50 边）；
  - ID 唯一性；
  - 边权合法性（非负、有限、有限范围已知）；
  - 边端点引用所有引用的节点 ID 都存在；
  - 边不自环（与 `Edge` 模型双重保险）；
  - `Vehicles.current_node_id`、`Courier.vehicle_id`、`Order.destination_id` 引用的存在性；
  - 时间窗口合法性（`start < end`、有限）；
  - **连通性自检**：弱连通（BFS）+ 强连通（**基于正反图的双向 DFS 强连通性判定**——注意：这是 Kosaraju 定理的判定情形，不是完整 SCC 分解；DFS 自身用**显式栈迭代**实现，**不**依赖任何算法库）；
  - 优化目标取值集合（仅允许 `distance / travel_time / cost`）。
* 失败时抛 `ConfigError`，附带字段路径（如 `network.edges[3].distance`），便于定位；
* 不修改 `LogisticsGraph` 类 —— 配置加载是「消费者」而不是「注入器」。

#### 2.3.1 ScenarioBundle

```python
@dataclass
class ScenarioBundle:
    name: str
    mode: str                      # 当前只支持 "fixed"
    random_seed: int
    graph: LogisticsGraph
    vehicles: list[Vehicle]
    couriers: list[Courier]
    orders: list[Order]
    simulation: dict[str, Any]
    optimization: dict[str, Any]
    metadata: dict[str, Any]
```

### 2.4 `logiroute.algorithms` — 路径规划（Phase 2+）

占位包；本阶段**严禁**实现任何算法。后续 Phase 将：

* **Phase 2**：手写最小堆（**禁止**使用 `heapq`） + 单源最短路（Dijkstra），支持 `distance / travel_time / cost` 三种度量切换；
* **Phase 3**：综合目标加权（线性组合多度量）；多策略路径对比；
* **Phase 4**：路径回溯 + 节点序列构造。

### 2.5 `logiroute.scheduling` — 配送调度（Phase 4+）

预留包；将承担车辆 / 人员分配、TSP / VRP、时间窗口硬约束评估。

### 2.6 `logiroute.simulation` — 仿真与随机场景（Phase 5+）

预留包。当前不含任何实现，仅在本节（见下）记录**随机场景生成器的设计方案**。

#### 2.6.1 随机场景生成器设计

> 强约束：**Phase 1 不实现**，仅规划。

**目标**：在后续阶段提供一个**可复现**、**可控制规模**、**满足强连通** 的随机场景生成器，
与固定场景产生**完全等价的 `LogisticsGraph`** 对象，从而让上层算法层**不感知**数据来源。

**输入参数（接口设计）**

```python
@dataclass
class RandomScenarioSpec:
    seed: int
    node_count: int                       # ≥30
    warehouse_count: int                  # ≥2
    transfer_count: int                   # ≥3
    customer_count: int                   # = node_count - warehouse - transfer
    edge_density: float                   # 边的概率 / 平均出度，0 < d < 1
    distance_range: tuple[float, float]
    time_range: tuple[float, float]
    cost_range: tuple[float, float]
    coverage: float = 0.95                # 强连通保证：至少要保证一个强连通骨干
```

**生成流程（草案）**

1. **节点布局**：在二维矩形上以 `seed` 为种子的随机 RNG 撒点，确保多数节点彼此可达。
2. **节点类型分配**：先固定 warehouse / transfer 数量，剩余随机均匀分配为 customer。
3. **强连通骨干生成**：以「最近邻 + K 边补全」构造「Hamiltonian-like 环」，
   每个节点至少 1 入 1 出。Phase 1 已通过"基于正反图的双向 DFS 强连通性判定"验证该思路可行。
4. **稀疏 / 稠密补全**：在骨干图上按 `edge_density` 随机连接，得到目标边数。
5. **权重解耦**：对每条边 `e = (u,v)`，按三种度量范围分别独立采样。
6. **类型分配**：生成 `vehicles`、`couriers`、`orders`（订单按客户子集派生）。
7. **返回 `ScenarioBundle`**，与固定场景形态完全一致。

**关键不变量**

* 不引用任何第三方库（不调用 `numpy.random`，统一用 `random.Random(seed)`）；
* 使用 `seed`，调用 N 次结果恒定；
* 最终图必须强连通（与现有 `loader.py` 配合校验）。

### 2.7 `logiroute.api` 与 `logiroute.web`

* `api`：FastAPI 后端占位（Phase 6+）；
* `web`：前端 Dashboard 占位（独立 React / TS 工程放在另一目录）。

## 三、对象关系

```
+-------------------+        出/入边                  +-------------------+
| LogisticsGraph    | <---------------------------->  | Edge              |
|                   |                                  |  source_id        |
|   _nodes          |                                  |  target_id        |
|   _out_edges      |                                  |  distance, time,  |
|   _in_edges       |                                  |  cost, traffic    |
+--------+----------+                                  +-------------------+
         |
         | 关联 (id)
         v
+-------------------+
| Node              |
|  id, name, type   |
|  x, y, metadata   |
+-------------------+

+-------------------+        1:1 引用                  +-------------------+
| Courier           | <------------------------------> | Vehicle           |
|  id, name         |                                  |  id, capacity     |
|  vehicle_id ------+--> (id)                          |  current_load     |
|  status           |                                  |  current_node_id  |
+-------------------+                                  |  status           |
                                                       +-------------------+

+-------------------+
| Order             |
|  id               |
|  destination_id -----> 指向 Node.id
|  demand           |
|  time_window_*    |
|  priority, status |
+-------------------+
```

* **图 ↔ Node / Edge**：仅以节点 ``id`` 与边 ``(source_id, target_id)`` 标识；
* **Vehicle ↔ Node**：`current_node_id` 是字符串引用，避免互相组合造成循环依赖；
* **Courier ↔ Vehicle**：`Courier.vehicle_id` 字符串引用，便于重新分配；
* **Order ↔ Node**：`Order.destination_id` 字符串引用。

## 四、数据流

```
config/scenario.json
        │
        ▼ (json.load)
logiroute.config.loader
   ├── 字段解析 -> Node / Edge / Vehicle / Courier / Order
   ├── 引用完整性校验（基于 dict 与 set）
   ├── 手写双向 DFS 强连通性判定（Kosaraju 判定情形）
   ▼
ScenarioBundle { graph, vehicles, couriers, orders, ... }
        │
        ▼
   LogisticsGraph
   ─────────────────────────
        │
        ▼ (Phase 2+)
   手写 Dijkstra / 综合目标 / 调度 / 仿真
        │
        ▼ (Phase 6)
   FastAPI 后端
        │
        ▼ (Phase 7)
   React + TypeScript 前端 Dashboard
```

## 五、测试架构

* 测试与主代码解耦：`tests/` 用 `unittest` 标准库；
* 测试目录布局：`tests/test_<module>.py`；
* 使用 `setUp` / 工厂函数管理 fixture；
* 测试既覆盖单组件行为，又包含「端到端」形状测试（连通性 / 最小节点 / 类型下界）；
* `LogisticsGraph.validate()` 作为多组测试的收尾断言；
* `loader` 的连通性自检确保固定场景强连通。

## 六、扩展边界（Phase 2+ 守则）

* `algorithms` 模块允许依赖 `core` 与 `graph`，**严禁**依赖 `api`/`web`/`scheduling`/`simulation`；
* `scheduling` 模块允许引用 `core` / `graph` / `algorithms`；
* 后端 API 转换数据模型为 JSON 时使用 `dataclasses.asdict`，保持数据模型纯净；
* 任何算法提供：伪代码 + 复杂度 + 单元测试 + 大型 fixture 行为对比。

## 七、配置驱动 vs 硬编码 —— 思维定式

| 项 | 配置 | 代码 |
| --- | --- | --- |
| 节点 / 边 ID | ✅ | ❌ |
| 边权（距离 / 时间 / 成本） | ✅ | ❌ |
| 节点坐标 | ✅ | ❌ |
| 车辆容量 | ✅ | ❌ |
| 订单时间窗口 | ✅ | ❌ |
| 配送员状态机 | 部分（仅起始状态） | ✅（迁移规则） |
| 默认优化权重 | ✅ | ❌ |
| 基础校验规则 | ❌ | ✅（与模型共存） |
