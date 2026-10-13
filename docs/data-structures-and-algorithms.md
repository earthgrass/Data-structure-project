# LogiRoute — 数据结构与算法专项设计文档

> 本文件是教师第一次课程检查的核心讲解材料：精确说明 LogiRoute Phase 1
> 已实现的每个模块**采用什么数据结构、什么算法、为什么这样选、复杂度是多少**，
> 并**严格区分**"已实现"与"规划中"两类内容。

---

## 一、核心选型总表

> 所有引用行号均来自实际源文件。标注的复杂度均**经本文档独立推导并与代码注释交叉核对**。

### 1.1 已实现模块

| 模块 | 抽象数据类型 | 实际存储结构 | 主要算法 | 自主实现 | 平均时间复杂度 | 空间复杂度 | 源码位置 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Node` | 不可变记录 | `dataclass(frozen=True)` | 字段校验、`distance_to`（欧氏距离公式） | ✅ 全部手写 | 构造 O(1) / `distance_to` O(1) | 单实例 O(1) | `src/logiroute/core/nodes.py:29-69` |
| `Edge` | 有向带权边 | 非冻结 `dataclass` | 字段校验、`weight(metric)` 调度 | ✅ 全部手写 | 构造 O(1) / `weight` O(1) | 单实例 O(1) | `src/logiroute/core/edges.py:33-89` |
| `Vehicle` | 容量受限资源 | 非冻结 `dataclass` | 状态机迁移 (`mark_*`)、`can_load` / `load` / `unload` | ✅ 全部手写 | 全部 O(1) | 单实例 O(1) | `src/logiroute/core/vehicles.py:30-133` |
| `Courier` | 人员 + 车辆引用 | 非冻结 `dataclass` | 状态机迁移 (`is_dispatchable` 分支判断) | ✅ 全部手写 | 全部 O(1) | 单实例 O(1) | `src/logiroute/core/couriers.py:21-69` |
| `Order` | 时限约束记录 | 非冻结 `dataclass` | 时间窗长度 / `is_within_window` 闭区间比较 | ✅ 全部手写 | 全部 O(1) | 单实例 O(1) | `src/logiroute/core/orders.py:29-97` |
| `LogisticsGraph` | 有向带权图容器 | 3 张 `dict`（哈希表） | 节点 / 边增删、邻接表导出、邻接矩阵按需导出、`validate` 一致性自检 | ✅ 全部手写 | 节点 / 边操作 O(1) avg；`edge_count` O(V)；`validate` O(V+E) | 主存 O(V + E) | `src/logiroute/graph/logistics_graph.py:83-442` |
| 邻接表（出边） | 哈希表版邻接表 | `dict[source_id, dict[target_id, Edge]]` | 邻居枚举 O(deg) | ✅ 容器与逻辑手写 | `has_edge` O(1) avg / `get_neighbors` O(deg) | O(V + E) | `logistics_graph.py:95-97`、使用见 `:253-271` |
| 反向邻接表（入边） | 哈希表版邻接表 | `dict[target_id, dict[source_id, Edge]]` | 反向邻居枚举 O(deg_in) | ✅ 容器与逻辑手写 | `get_in_edges` O(deg_in) | O(V + E) | `logistics_graph.py:97`、使用见 `:263-271` |
| 邻接矩阵（按需导出） | V×V 实数矩阵 | `list[list[float]]` + 哨兵 `inf` | 初始化 O(V²) + 邻接表填充 O(E) | ✅ 逻辑手写（`list` 是语言容器） | **O(V² + E)**（修正前期 docstring 的 O(V+E) 误写） | O(V²) | `logistics_graph.py:335-393` |
| `ArrayQueue`（FIFO 队列） | 队列抽象数据类型 | `list` + 递增 `head` 指针 | `enqueue` / `dequeue` / `front` / `compact` | ✅ 全部手写 | `enqueue` O(1) 摊销 / `dequeue` O(1) | O(n)，n 为当前元素数 | `src/logiroute/graph/queue.py:42-128` |
| 弱连通性 BFS | 图遍历 | `ArrayQueue` + `set` 访问标记 | 一次 BFS 覆盖所有节点 | ✅ 逻辑手写 | O(V + E) | O(V) | `src/logiroute/config/loader.py:475-505` |
| 强连通性判定（双向 DFS） | 图可达性 | 临时 `dict[id, list[id]]` + 显式栈 | 显式栈 DFS × 2（正图 + 反图） | ✅ 逻辑手写 | O(V + E) | O(V) | `src/logiroute/config/loader.py:508-560` |
| 配置加载 | JSON → 强类型对象 | `json`（标准库读取工具） | 顺序字段解析 + ID 引用校验 + 连通性自检 | ✅ 全部手写 | O(V + E)（连通性自检主导） | O(V + E) | `src/logiroute/config/loader.py:114-340` |

> **术语说明**："自主实现"≠"不依赖任何标准库"。本项目**拒绝**的是第三方
> 算法包（NetworkX、NumPy、SciPy、OR-Tools、heapq-as-algorithm 等）；
> Python 语言基础容器（`list` / `dict` / `set` / `tuple` / `str`）与
> 工程基础设施（`json` / `pathlib` / `dataclasses` / `enum` /
> `unittest`）属于课程明确允许的 A/B 类别。

### 1.2 规划中 / 未实现模块（**不计入已实现**）

| 规划模块 | 计划数据结构 | 计划算法 | 计划所在 Phase |
| --- | --- | --- | --- |
| 最小堆（Phase 2） | 数组版 + 显式下沉 / 上浮 | `push` / `pop_min` / `decrease_key` / `heapify` | 2 |
| Dijkstra 单源最短路（Phase 2） | `dist[]` + `prev[]` + 自实现堆 | 标准 Dijkstra | 2 |
| 多目标综合优化（Phase 3） | min-max 归一化 + 加权 | 多次 Dijkstra 复用 | 3 |
| TSP / VRP（Phase 4） | 列表 + 时刻表 dataclass | 最近邻 + 2-opt（手写） | 4 |
| 时间窗硬约束（Phase 4） | `Order.is_within_window` 闭区间检查 | 累计到达时刻推演 | 4 |
| 随机场景生成器（Phase 5） | `random.Random`（标准库种子源） | 节点布局 + 强连通骨干（手写 Prim / Kruskal 草案） | 5 |
| 动态事件队列（Phase 5） | 自实现事件堆 | 周期性事件调度 | 5 |
| FastAPI 后端（Phase 6） | 框架（**首次允许**三方包） | RESTful 路由 | 6 |
| React + TS 前端（Phase 7） | 前端框架 | 独立工程目录 | 7 |

> 上述模块**当前不在 `src/logiroute/` 任何文件中**；`algorithms/` /
> `scheduling/` / `simulation/` / `api/` / `web/` 均为占位空包。

---

## 二、图结构专题

### 2.1 数学定义

配送路网是**有向带权图** $G = (V, E, w)$：

* 顶点集 $V$ = 35 个节点（2 仓库 + 29 客户 + 4 中转站）；
* 边集 $E$ = 192 条有向边；
* 权重函数 $w : E \to \mathbb{R}_{\ge 0}^3$ —— 每条边同时具有
  `(distance, travel_time, cost)` 三种非负标量。

**为什么需要三种权重**：它们互不相关——
* `distance`（公里）描述物理长度；
* `travel_time`（分钟）描述道路通行时间，受限速 / 红绿灯 / 拥堵影响；
* `cost`（元）描述运输经济成本，受油价 / 路桥费 / 人工影响。

不同业务场景下需要不同度量下的最优路径（最近 / 最快 / 最省），因此
**多度量**是路径规划必须支持的特性。

**为什么必须是有向边**：实际道路常为单行道、转弯限制、潮汐车道；无向
图会丢失方向信息，使"最短路径"无解或误导。

### 2.2 邻接表实现（主存）

代码（`logistics_graph.py:95-97`）：

```python
self._nodes: dict[str, Node] = {}
self._out_edges: dict[str, dict[str, Edge]] = {}
self._in_edges: dict[str, dict[str, Edge]] = {}
```

| 字段 | 角色 | 数据结构 | 平均时间 | 空间 |
| --- | --- | --- | --- | --- |
| `_nodes` | 节点索引 | 哈希表 `dict[id, Node]` | O(1) avg | O(V) |
| `_out_edges` | 出边邻接表 | **外层哈希表** `dict[src, dict[tgt, Edge]]` | `has_edge` O(1) avg / `get_neighbors` O(deg) | O(V + E) |
| `_in_edges` | 入边邻接表 | **外层哈希表** `dict[tgt, dict[src, Edge]]` | `get_in_edges` O(deg_in) | O(V + E) |

**邻接表与"链表式邻接表"的区别**：

| 维度 | 链表式邻接表 | 哈希式邻接表（**本项目**） |
| --- | --- | --- |
| 邻居存储 | `list[NodeRef]` | `dict[NodeId, Edge]` |
| `has_edge(u, v)` | O(deg(u)) 线性扫描 | **O(1) avg** |
| 加边 | O(1) push | O(1) avg |
| 删边 | O(deg(u)) 找到再删 | **O(1) avg** |
| 遍历邻居 | O(deg) | O(deg) |
| 空间常数 | 小（每个节点一条指针） | 较大（哈希条目） |

> **结论**：本项目使用哈希式邻接表是**邻接表的一种实现方式**，不是邻接
> 矩阵；课程标准不要求"邻接表必须用链表实现"。

### 2.3 反向邻接表（`_in_edges`）的必要性

Phase 1 中已经用到的反向邻接表能力：

* `get_in_edges(node_id)` O(deg_in) 取入边（第 263-271 行）—— 是
  `validate()` 入边一致性检查的基础。

后续阶段（已规划，未实现）的关键用途：

* **Phase 3 反向松弛**：当多目标加权时，需要"所有能到达某点的边"做反
  向 Dijkstra 优化。
* **Phase 4 路径回溯**：构造 `prev[]` 之后，有时需要反查"哪些边最终汇
  入终点"以生成路径动画。
* **Phase 5 增量重规划**：当某条边失效时，需要"所有受其影响的节点"快
  速定位。

**没有反向邻接表时**，以上操作每次都要 O(E) 扫全图；**维护成本仅是
O(1) 写入**，换来大量频繁查询的常数倍提速。

### 2.4 邻接矩阵（按需导出视图）

代码（`logistics_graph.py:335-393`）：

```python
index = {nid: i for i, nid in enumerate(ordered_ids)}
n = len(ordered_ids)
matrix = [[_INF] * n for _ in range(n)]  # V×V 初始化
for source_id, out_map in self._out_edges.items():
    if source_id not in index: continue
    i = index[source_id]
    for target_id, edge in out_map.items():
        if target_id not in index: continue
        j = index[target_id]
        matrix[i][j] = edge.weight(metric)
return ordered_ids, matrix
```

| 维度 | 数值 / 行为 |
| --- | --- |
| 行 / 列数 | V = 35 |
| 元素总数 | V² = 1225 |
| 无自环时最大可能边数 | V·(V-1) = 1190 |
| 当前场景实际边数 | 192 |
| 直接邻接单元利用率 | 192 / 1225 ≈ **15.7%** |
| 不含自环的理论最大利用率 | 192 / 1190 ≈ **16.1%** |
| 主对角线（i==j）值 | 全部 `inf`（无自环） |
| 无直接边的位置 | 全部 `inf`（哨兵值） |
| 时间复杂度（修正） | **O(V² + E)**——V² 来自矩阵初始化，E 来自邻接表填充 |
| 空间复杂度 | O(V²) 新建矩阵；不持久化 |
| `__slots__` 是否含矩阵 | ❌ 不含，矩阵只是按需视图 |

**为什么"邻接表是主存 + 邻接矩阵按需导出"**：
* 主存是邻接表：稀疏图（边数 ≪ V²）下节省空间、迭代邻居 O(deg) 高效；
* 矩阵按需导出：满足课程演示、Floyd-Warshall 类全对最短路（Phase 3+）
  的需求，但不持久化避免双份数据不一致。

### 2.5 增删过程中的不变量

> `LogisticsGraph` 通过 `validate()` 在每次破坏性操作后可自检（O(V+E)）。

**核心不变量**：

1. `_nodes` / `_out_edges` / `_in_edges` 三个键集合**完全相等**；
2. 每条出边的 `key` 字段 `(_out_edges[src].source_id, _out_edges[src].target_id)`
   与外层哈希键 `(src, tgt)` 一致；
3. **双向索引指向同对象**：`_out_edges[src][tgt] is _in_edges[tgt][src]`；
4. 删除节点后，所有指向 / 来自该节点的边**全部**被清理，无悬挂边。

| 操作 | 不变量维护策略 | 证据行号 |
| --- | --- | --- |
| `add_node` | 写 `_nodes` + 双表 `setdefault` 空字典 | `:113-115` |
| `add_edge` | 先校验端点 / 查重，再**双写** `_out_edges` 与 `_in_edges` | `:206-213` |
| `remove_edge` | 双删：先 `_out_edges[src].pop`，再 `_in_edges[tgt].pop` | `:228-229` |
| `remove_node` | 1) 清 `_out_edges[node]` 并对每个目标点从 `_in_edges` 删；2) 清 `_in_edges[node]` 并对每个源点从 `_out_edges` 删；3) 删 `_nodes` | `:126-134` |

---

## 三、邻接表与邻接矩阵的全面对比

| 维度 | 邻接表（哈希版） | 邻接矩阵 |
| --- | --- | --- |
| 空间复杂度 | **O(V + E)** | O(V²) |
| `has_edge(u, v)` | O(1) avg | O(1) |
| 遍历 `u` 的所有邻居 | **O(deg(u))** | O(V) |
| 加边 | O(1) avg | O(1) |
| 删边 | O(1) avg | O(1) |
| 删点 | O(deg_in + deg_out) | O(V²) |
| 适合图类型 | **稀疏图** | 稠密图 |
| Floyd-Warshall 友好 | 不友好 | **友好** |
| 适合的算法 | BFS / DFS / Dijkstra / 拓扑序 | Floyd / 传递闭包 |
| 课程项目主流选型 | ✅ | （视场景） |

**本项目选邻接表作为主存的理由**：

1. 配送路网是**稀疏图**（35 节点 192 边，边数与 V 同阶，矩阵浪费 ~84% 空间）；
2. 已规划的所有算法（BFS / DFS / Dijkstra / 反向松弛）都以"取一个点的
   所有邻居"为主导操作，邻接表 O(deg) 天然友好；
3. 邻接矩阵按需导出，不持久化，避免双份数据不一致。

---

## 四、BFS 与 DFS 详解

### 4.1 弱连通性 BFS（`_is_weakly_connected`）

```python
def _is_weakly_connected(graph, nodes):
    """在无向化项目图上做 BFS。"""
    adjacency = {n.id: [] for n in nodes}
    for src_id in graph.node_ids:
        for edge in graph.get_neighbors(src_id):
            adjacency[src_id].append(edge.target_id)   # 正向
            adjacency[edge.target_id].append(src_id)   # 反向（无向化）
    visited = {start}
    queue: ArrayQueue[str] = ArrayQueue()              # ← 自实现 FIFO 队列
    queue.enqueue(start)
    while not queue.is_empty():
        u = queue.dequeue()
        for v in adjacency[u]:
            if v not in visited:
                visited.add(v)
                queue.enqueue(v)
    return visited == {n.id for n in nodes}
```

| 维度 | 内容 |
| --- | --- |
| 数据结构 | 自实现 `ArrayQueue`（递增 head 指针）；`set` 访问标记 |
| 空间 | O(V) |
| 时间 | O(V + E) |
| 自主实现 | 队列抽象数据类型（`ArrayQueue`） + BFS 控制循环均手写 |

### 4.2 强连通性双向 DFS 判定（`_is_strongly_connected`）

```python
def _is_strongly_connected(graph, nodes):
    """基于正反图的双向 DFS 强连通性判定。

    注意：这不是完整 Kosaraju 强连通分量分解算法。完整 Kosaraju 需要
    Pass 1 记录 DFS 完成时间序、Pass 2 按倒序在反图 DFS 求 SCC 划分。
    本函数仅做"是否整体强连通"的判定，等价于：
    "任取起点 s，在正图上从 s 能到达所有节点 且 在反图上从 s 也能到达
    所有节点"——这是 Kosaraju 定理的判定情形，仍保持 O(V + E) 复杂度
    与强连通性判定的完备正确性。
    """
    node_ids = [n.id for n in nodes]
    all_ids = set(node_ids)
    adjacency_fwd = {nid: [] for nid in node_ids}
    adjacency_rev = {nid: [] for nid in node_ids}
    for src_id in node_ids:
        for edge in graph.get_neighbors(src_id):
            adjacency_fwd[src_id].append(edge.target_id)
            adjacency_rev[edge.target_id].append(src_id)
    start = node_ids[0]
    if not _dfs_reaches_all(start, adjacency_fwd, all_ids): return False
    if not _dfs_reaches_all(start, adjacency_rev, all_ids): return False
    return True

def _dfs_reaches_all(start, adjacency, all_ids):
    """手写 DFS（**显式栈迭代**，非递归）；不使用任何第三方库。"""
    visited = set()
    stack = [start]
    while stack:
        u = stack.pop()
        if u in visited: continue
        visited.add(u)
        for v in adjacency.get(u, []):
            if v not in visited:
                stack.append(v)
    return visited == all_ids
```

| 维度 | 内容 |
| --- | --- |
| 数据结构 | 临时 `dict[id, list[id]]`（正/反向各一份）；`set` 访问标记；`list` 显式栈 |
| 空间 | O(V) |
| 时间 | O(V + E) |
| 自主实现 | DFS 控制循环 + 显式栈均手写 |
| 与 Kosaraju 的关系 | **判定情形的等价简化**（功能仅判定，不输出 SCC 划分） |

### 4.3 BFS / DFS / 显式栈迭代 vs 递归的对比

| 维度 | BFS | DFS（显式栈） | DFS（递归） |
| --- | --- | --- | --- |
| 数据结构 | FIFO 队列 | 显式栈（`list`） | Python 调用栈 |
| 入栈 / 入队 | 队尾 | 栈顶 | 函数调用 |
| 空间 | O(W)，W 为最大层宽 | O(h)，h 为树高 | O(h)，由 Python 解释器管理 |
| 栈溢出风险 | 无 | 无 | **有**（深度 > 1000 时） |
| 可调试性 | 一般 | **好**（栈是显式数据结构） | 一般 |
| 本项目采用 | ✅ | ✅ | ❌（避免栈溢出且更易演示） |

---

## 五、操作复杂度完整分析

> "平均"指哈希表摊销 O(1)；"最坏"指哈希冲突极端情形（实际中极少）。

### 5.1 图容器操作

| 操作 | 平均时间 | 最坏时间 | 辅助空间 | 输出空间 | 总存储 |
| --- | --- | --- | --- | --- | --- |
| `add_node` | O(1) | O(V) | O(1) | — | +O(1) |
| `add_edge` | O(1) | O(deg) | O(1) | — | +O(1) |
| `remove_node` | O(deg_in + deg_out) | O(V) | O(1) | — | -O(deg) |
| `remove_edge` | O(1) | O(1) | O(1) | — | -O(1) |
| `get_node` | O(1) | O(V) | O(1) | — | — |
| `has_node` | O(1) | O(V) | O(1) | — | — |
| `try_get_node` | O(1) | O(V) | O(1) | — | — |
| `get_neighbors` | O(deg) | O(V) | O(1) | O(deg) | — |
| `get_in_edges` | O(deg_in) | O(V) | O(1) | O(deg_in) | — |
| `get_all_nodes` | O(V) | O(V) | O(1) | O(V) | — |
| `get_all_edges` | O(E) | O(E) | O(1) | O(E) | — |
| `get_adjacency_list` | O(V + E + Σdeg·log·deg) | 同上 | O(V+E) | O(V+E) | — |
| `get_adjacency_matrix` | **O(V² + E)** | 同上 | O(V²) | O(V²) | — |
| `edge_count` | O(V) | O(V) | O(1) | O(1) | — |
| `node_count` | O(1) | O(1) | O(1) | O(1) | — |
| `validate` | O(V + E) | O(V + E) | O(V) | — | — |
| `clear` | O(1) | O(1) | O(1) | — | 清空 |

### 5.2 数据模型操作

| 操作 | 时间 | 空间 |
| --- | --- | --- |
| `Node.__post_init__` | O(1) | O(1) |
| `Node.distance_to` | O(1) | O(1) |
| `Edge.__post_init__` | O(1) | O(1) |
| `Edge.weight(metric)` | O(1) | O(1) |
| `Vehicle.can_load / load / unload` | O(1) | O(1) |
| `Vehicle.mark_*` | O(1) | O(1) |
| `Courier.mark_* / assign_vehicle` | O(1) | O(1) |
| `Order.is_within_window` | O(1) | O(1) |

### 5.3 连通性 / 遍历

| 操作 | 时间 | 空间 |
| --- | --- | --- |
| `_is_weakly_connected`（BFS） | O(V + E) | O(V) |
| `_is_strongly_connected`（双向 DFS） | O(V + E) | O(V) |
| `_dfs_reaches_all` | O(V + E) | O(V) |

### 5.4 自实现队列（`ArrayQueue`）

| 操作 | 时间 | 空间 |
| --- | --- | --- |
| `enqueue` | O(1) 摊销 | O(1) |
| `dequeue` | O(1) | O(1) |
| `front` | O(1) | O(1) |
| `is_empty` | O(1) | O(1) |
| `__len__` | O(1) | O(1) |
| `clear` | O(1)（仅重置指针） | O(1) |
| `compact` | O(n) | — |

---

## 六、自实现与现成调用审计

### 6.1 已自主实现的课程核心操作

| 操作 | 位置 | 自主实现程度 |
| --- | --- | --- |
| 欧氏距离 | `core/nodes.py:62-69` | ✅ 公式 + `**0.5` |
| 边权分发（按 metric） | `core/edges.py:76-88` | ✅ 字符串分发 |
| 状态机迁移 | `core/vehicles.py:125-133`、`core/couriers.py:61-69` | ✅ 显式 if 守卫 |
| 时间窗判定 | `core/orders.py:95-97` | ✅ 闭区间比较 |
| 字段级校验 | `core/*` 的 `__post_init__` | ✅ |
| BFS（弱连通） | `config/loader.py:475-505` | ✅ 显式 while 循环 + 自实现 `ArrayQueue` |
| 双向 DFS（强连通） | `config/loader.py:508-560` | ✅ 显式栈迭代 |
| FIFO 队列 | `graph/queue.py:42-128` | ✅ `list` + 递增 `head` |
| 哈希表版邻接表 | `graph/logistics_graph.py:95-97` | ✅ 容器（`dict`）+ 逻辑手写 |
| 邻接矩阵按需生成 | `graph/logistics_graph.py:335-393` | ✅ 矩阵初始化 + 邻接表填充 |

### 6.2 Python 基础容器的依赖边界

| 类别 | 允许使用 | 说明 |
| --- | --- | --- |
| A. 基础语言机制 | `list`、`dict`、`set`、`tuple`、`str`、`int`、`float`、`bool`、循环 / 分支 / 类 / 算术 | 默认允许 |
| B. 工程基础设施 | `json`、`pathlib`、`dataclasses`、`enum`、`unittest`、`math`（标量函数） | 默认允许 |
| C. 现成数据结构 | `collections.deque` 在 Phase 1 已被 `ArrayQueue` 替代；`collections.Counter` 在配置加载器内做类型计数 | **受限**：Dijkstra / 优先队列 / 队列等课程核心操作需自实现 |
| D. 现成算法 | `sorted()` 在 `get_adjacency_list` 导出时用 1 次（仅用于序列化顺序，**不参与任何路径算法**） | **禁止**用于算法核心 |

### 6.3 第三方依赖审计

```bash
$ cat pyproject.toml
dependencies = []      # Phase 1 阶段**完全无运行期依赖**
```

* NetworkX：未引入；
* NumPy / SciPy：未引入；
* OR-Tools / PuLP：未引入；
* `heapq`：未引入（Phase 2 优先队列自实现）；
* matplotlib / plotly / dash：未引入（Phase 7+ 之前不引入）；
* fastapi / flask：未引入（Phase 6+ 之前不引入）；
* pytest：未引入（**统一使用 unittest**）。

---

## 七、示例图：手算对照

以一个 4 节点示例图为例：

```
        1
   A ──────→ B
   │         │
2  │         │ 3
   ↓         ↓
   C ──────→ D
        4
```

### 7.1 数学表示

* $V = \{A, B, C, D\}$
* $E = \{(A,B), (A,C), (B,D), (C,D)\}$
* $w(A,B) = (1, 2, 0.5)$，`$w(A,C) = (2, 3, 1.0)$`，`$w(B,D) = (3, 4, 1.5)$`，`$w(C,D) = (4, 5, 2.0)$`

### 7.2 邻接表（按 target 升序）

```python
{
  "A": [Edge(A,B), Edge(A,C)],
  "B": [Edge(B,D)],
  "C": [Edge(C,D)],
  "D": [],
}
```

### 7.3 邻接矩阵（distance 度量）

```
       A    B    C    D
   A [ ∞    1    2    ∞ ]
   B [ ∞    ∞    ∞    3 ]
   C [ ∞    ∞    ∞    4 ]
   D [ ∞    ∞    ∞    ∞ ]
```

### 7.4 反向邻接表

```python
{
  "A": [],
  "B": [Edge(A,B)],
  "C": [Edge(A,C)],
  "D": [Edge(B,D), Edge(C,D)],
}
```

> 对照 `LogisticsGraph.get_in_edges(...)`：返回的就是上表对应数组。

---

## 八、Phase 1 课程检查自检清单

- [x] 每个核心模块标注了**具体存储结构**（非"高效结构"等模糊词）；
- [x] 每个核心模块标注了**具体算法**（非"采用优化算法"等模糊词）；
- [x] 每个核心模块标注了**自主实现 vs 标准库**依赖边界；
- [x] 每个核心模块标注了**精确的 Time / Space 复杂度**（含哈希表摊销、矩阵 V² 主导等细节）；
- [x] 邻接表 / 邻接矩阵 / 反向邻接表三种结构的**职责与权衡**已讲清；
- [x] 显式 BFS / 显式 DFS 控制循环均手写；
- [x] `ArrayQueue` 自主实现并解释空间回收策略；
- [x] 显式说明 `_is_strongly_connected` 是 Kosaraju 的**判定情形**而非完整 SCC 分解；
- [x] 修复了 `get_adjacency_matrix` 复杂度 docstring 的 O(V+E) → O(V² + E) 误写；
- [x] 修复了 BFS 队列由 `collections.deque` 改为自实现 `ArrayQueue`；
- [x] 修复了 `get_adjacency_list` 中 `sorted()` 的复杂度被遗漏问题（明确给出排序代价）。
