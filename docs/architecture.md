# LogiRoute 系统架构

> 本文档描述 LogiRoute 在 Phase 1 已落地的分层结构、模块责任边界与对象关系。
> Phase 2 起新增的路径规划、调度、Web 框架将由后续文档补充并保持正文与代码一致。

## 一、总体分层

```
+-----------------------------------------------------------+
|  Web Frontend (Phase 7)                                   |
+-----------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------+
|  FastAPI Service (Phase 6)                                |
+-----------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------+
|  Domain Layer                                             |
|   - logiroute.dispatch  (Phase 3+, 当前占位)               |
|   - logiroute.algorithms (Phase 2+, 当前占位)              |
|   - logiroute.config    (Phase 2+, 当前占位)               |
+-----------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------+
|  Core Data Structures                                     |
|   - logiroute.graph   LogisticsGraph (邻接表 + 邻接矩阵)     |
|   - logiroute.core    Node / Edge / Vehicle / Courier /    |
|                       Order / Enums                        |
+-----------------------------------------------------------+
                          |
                          v
+-----------------------------------------------------------+
|  Persistence / External (Phase 6+：JSON, SQLite, ...)      |
+-----------------------------------------------------------+
```

依赖箭头指向下方；上层禁止反向依赖下层。`core` 与 `graph` 不引用任何 Web/算法/调度包。

## 二、模块责任

### `logiroute.core` — 业务数据模型
不依赖任何外部业务库，只依赖 Python 标准库。  
职责：定义配送网络中各实体的字段、字段级校验、不变量与少量便利方法。

| 类 / 枚举  | 角色 | 说明 |
| ----------- | ---- | ---- |
| `Node`      | 数据 | 不可变 dataclass；`id`、`name`、`node_type`、`x`、`y`、`metadata`；含 ``distance_to``。 |
| `Edge`      | 数据 | 可变 dataclass；`source_id`、`target_id`、`distance`、`travel_time`、`cost`、`traffic_status`、`metadata`；提供 ``weight(metric)``、``key``。 |
| `Vehicle`   | 行为 | 含 ``load / unload / can_load / remaining_capacity``，防止超载。 |
| `Courier`   | 行为 | 与 Vehicle 独立建模；``assign_vehicle``、状态机切换。 |
| `Order`     | 行为 | 时间窗口判定 ``is_within_window``；状态机。 |
| `NodeType` / `TrafficStatus` / `CourierStatus` / `OrderPriority` / `OrderStatus` | 枚举 | 字符串值可 JSON 序列化。 |

所有字段均经过校验，违反约束立即抛 ``ValueError``，避免错误数据进入图。

### `logiroute.graph` — 有向带权图容器
唯一职责：以邻接表为核心存储 ``LogisticsGraph``，提供节点 / 边的增删查与
邻接表 / 邻接矩阵导出。**不实现任何路径算法**。

数据结构：

```
_nodes        : Dict[node_id, Node]
_out_edges    : Dict[source_id, Dict[target_id, Edge]]    # 邻接表
_in_edges     : Dict[target_id, Dict[source_id, Edge]]    # 反向邻接表
```

* 邻接表是唯一可变状态；邻接矩阵按需从邻接表导出，不重复维护。
* ``remove_node`` 同时清理入边和出边的双向索引；``validate()`` 用于自检。
* 异常类型：`GraphError` / `DuplicateNodeError` / `DuplicateEdgeError` /
  `UnknownNodeError`，便于上层精确捕获。

### `logiroute.algorithms` — 路径规划（Phase 2+ 占位）
当前不允许实现任何算法；目录仅保留作为模块边界。

### `logiroute.dispatch` — 配送调度（Phase 3+ 占位）
订单-车辆-人员匹配、路径合并与时间窗口评估的占位包。

### `logiroute.config` — 配置管理（Phase 2+ 占位）
JSON / YAML / 环境变量加载的统一入口占位。

### `logiroute.api` 与 `logiroute.web` — 后端与前端占位
仅保留模块路径；后续阶段才会引入 FastAPI 与前端工程。

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
|  id, name         |                                  |  id, max_capacity |
|  vehicle_id ------+--> (id)                          |  current_load     |
|  status           |                                  |  current_node_id  |
+-------------------+                                  +-------------------+

+-------------------+
| Order             |
|  id               |
|  destination_node_id -----> 指向 Node.id
|  demand           |
|  time_window_*    |
|  priority, status |
+-------------------+
```

* **图 ↔ Node / Edge**：仅以节点 ``id`` 与边 ``(source_id, target_id)`` 标识关系。
* **Vehicle ↔ Node**：``current_node_id`` 是字符串引用，避免互相组合造成的循环依赖。
* **Courier ↔ Vehicle**：`Courier.vehicle_id` 字符串引用，便于后续重新分配。
* **Order ↔ Node**：`destination_node_id` 字符串引用。

## 四、数据流

Phase 1 中数据流方向有限：

```
配置 JSON (Phase 2+) -> logiroute.config -> Graph / Model
                                        ↓
                                   LogisticsGraph
                                        ↓
                       邻接表 / 邻接矩阵导出 -> 路径算法 (Phase 2+)
                                        ↓
                                    调度 (Phase 3+)
                                        ↓
                                    FastAPI (Phase 6)
                                        ↓
                                React Dashboard (Phase 7)
```

Phase 1 仅闭环于「数据模型 + 图结构 + 单元测试」。

## 五、测试架构

* 测试与主代码解耦：`tests/` 通过 ``pythonpath = ["src"]``（`pyproject.toml`）发现包。
* 全部为单元测试，不依赖前端 / 数据库 / 网络。
* 使用 ``pytest.mark.phase1`` 显式标记阶段，便于长期维护时筛选。
* 测试假数据使用 ``conftest.py`` 的 fixture 工厂，避免重复样板。
* ``LogisticsGraph.validate()`` 用于在测试后主动验证内部一致性。

## 六、扩展边界（Phase 2+ 应遵循）

* ``algorithms`` 模块应仅依赖 ``core`` 与 ``graph``，**严禁**依赖 ``api`` / ``web``。
* ``dispatch`` 模块允许引用 ``core`` / ``graph`` / ``algorithms``。
* 后端 API 转换数据模型为 JSON 时应使用 ``dataclasses.asdict`` 或自定义序列化器，
  以保持模型层纯净。
* 前端应通过 FastAPI 提供的接口与后端通信；**不**直接与 Python 模型耦合。
