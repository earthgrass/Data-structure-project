# LogiRoute — 第一次课程检查教师答辩材料（Phase 1）

> 本文件包含：5 分钟讲解稿、15+ 教师提问与标准答案、答辩规范。
>
> **核心承诺**：所有答案均给出**简明回答**、**详细原理**、**对应源码位置**与
> **可演示的测试入口**，确保学生真正能解释代码，而不是背诵空泛描述。

---

## 一、五分钟讲解稿

> 建议配合 IDE（VS Code / PyCharm）打开源码同步演示。

### 第一分钟 —— 问题建模与整体架构

> 老师好，我做的是《电商物流配送路径规划系统 LogiRoute》。
>
> **业务问题**：城市配送路网建模。35 个节点（2 仓库 + 29 客户 + 4 中转站），
> 192 条有向边，每条边同时携带距离、时间、成本三种互不相关的度量。
>
> **技术架构**（边说边展示 `docs/architecture.md` 第 1 节）：
>
> ```
> Web (P7) → FastAPI (P6) → Scheduling/Simulation (P4-5)
>     → Algorithms (P2-3, **手写**) → Config + Core + Graph (P1, **已实现**)
> ```
>
> **当前进度**：Phase 1 — 工程初始化 + 配置驱动 + 核心数据结构，**121 → 161
> 个 unittest 全部通过**（新增 40 个回归 / 队列测试）。

### 第二分钟 —— 节点、边、车辆与订单建模

> 我用 5 个 `dataclass` 描述业务实体（边说边打开 `core/` 目录）：
>
> * **`Node`**（`core/nodes.py:29-69`）—— `frozen=True` 的不可变节点，
>   含欧氏距离 `distance_to`。
> * **`Edge`**（`core/edges.py:33-89`）—— 有向带权边，**构造时拒绝自环
>   / 负权 / NaN / inf**（第 55-69 行）；`weight(metric)` 在三种度量间
>   分发（第 76-88 行）。
> * **`Vehicle`**（`core/vehicles.py:30-133`）—— 容量受限资源，
>   状态机由 `mark_*` 方法显式驱动；`load` / `unload` / `can_load` 提供
>   装载约束。
> * **`Courier`**（`core/couriers.py:21-69`）—— 配送员与车辆是 1:1
>   **字符串引用**关系，避免循环依赖。
> * **`Order`**（`core/orders.py:29-97`）—— 含 `time_window_start` /
>   `time_window_end` 闭区间，构造时强制 `end > start`（第 71-74 行）。
>
> 校验失败一律抛 `ValueError`，**不静默吞错**。

### 第三分钟 —— 邻接表、反向邻接表与邻接矩阵

> 图容器是 `LogisticsGraph`（`graph/logistics_graph.py:83-442`），用
> `__slots__` 收紧内存。它有 3 张**哈希表**（强调：不是链表，但**仍然是
> 邻接表**）：
>
> ```python
> self._nodes: dict[str, Node] = {}                          # O(1) 节点查找
> self._out_edges: dict[str, dict[str, Edge]] = {}           # 出边邻接表
> self._in_edges: dict[str, dict[str, Edge]] = {}            # 反向邻接表
> ```
>
> **为什么用哈希表实现邻接表**：本场景是稀疏图（35 节点 / 192 边，矩阵
> 利用率仅约 16%），哈希邻接表让 `has_edge(u, v)` O(1) avg。
>
> **为什么有反向邻接表**：Phase 4 之后要做反向松弛 / 前置节点重规划 /
> 路径动画回溯；没有它，每次都要 O(E) 扫全图。
>
> **邻接矩阵按需导出**（`get_adjacency_matrix`，第 335-393 行），不持久化
> —— V×V 初始化 O(V²) + 邻接表填充 O(E)，**总复杂度 O(V² + E)**（这是我
> 之前 docstring 误写为 O(V+E) 后修正的）。

### 第四分钟 —— BFS、DFS、强连通检查与复杂度

> 弱连通性用 BFS（`config/loader.py:475-505`），强连通性用基于正反图
> 的**双向 DFS 判定**（第 508-560 行）。
>
> **重点说明**：
>
> 1. **BFS 队列是自实现的 `ArrayQueue`**（`graph/queue.py:42-128`），
>    用 `list` + 递增 `head` 指针实现 O(1) 入队出队，**没有用
>    `collections.deque`**。
> 2. **DFS 是显式栈迭代**（`_dfs_reaches_all` 第 547-560 行），不是
>    Python 递归，避免栈溢出。
> 3. **这不是完整 Kosaraju**（只判定是否整体强连通，不输出 SCC 划分），
>    我已在代码注释中明确澄清。
>
> **复杂度总结**：
>
> | 操作 | 时间 | 空间 |
> | --- | --- | --- |
> | BFS 弱连通 | O(V + E) | O(V) |
> | 双向 DFS 强连通判定 | O(V + E) | O(V) |
> | 邻接表 / 邻接矩阵导出 | O(V+E) / O(V²+E) | O(V+E) / O(V²) |
> | 单边增删 | O(1) avg | O(1) |

### 第五分钟 —— 配置初始化、测试结果与后续开发

> **配置驱动**（打开 `config/scenario.json`）：35 节点 / 192 边 / 4 车
> 辆 / 4 配送员 / 20 订单。Python 源码**没有任何硬编码的节点数 / 容量
> / 默认 ID**；一切业务参数来自 JSON。
>
> **测试架构**（`tests/`）：7 个 `unittest` 文件，**121 → 161 个用例
> 全部通过**，实测耗时 67 ms。包括：
>
> * 数据模型字段级校验（`test_nodes` / `test_edges` / `test_vehicles` / 等）
> * 图结构操作与一致性（`test_graph.py` 含 35 用例）
> * 配置加载校验（`test_config.py` 含 21 用例）
> * **新增** `test_queue.py`（自实现队列 18 用例）
> * **新增** `test_phase1_regression.py`（矩阵 / 连通性 / Edge 变更 22 用例）
>
> **下一阶段（Phase 2）**：手写 `MinHeap[T]`（数组版，**禁 `heapq`**）
> + Dijkstra 单源最短路，支持三种 `metric` 切换。
>
> 讲解到此结束，欢迎老师提问。

---

## 二、教师可能提问（15+ 题）与标准答案

> 每题均给出：**简明回答**、**详细原理**、**源码位置**、**演示入口**。

---

### Q1：为什么不用邻接矩阵作为主要存储结构？

**简明**：本场景是稀疏图，35 节点 192 边只占 V×V 矩阵的 15.7% 空间，浪费 84% 以上。

**详细原理**：
* 邻接矩阵空间 O(V²) = 1225 单元；邻接表空间 O(V+E) = 35+192 = 227 条目，
  节省约 5 倍。
* 矩阵的 O(1) `has_edge` 在 V 较小时优势不明显；本项目所有算法都以
  "取一个点的所有邻居"为主，邻接表 O(deg) 更合适。
* 矩阵作为**按需视图**导出即可满足 Floyd-Warshall 等场景，避免双份数据
  不一致。

**源码位置**：`logistics_graph.py:95-97`（邻接表主存）、`:335-393`（按需导出矩阵）。

**演示**：
```bash
PYTHONPATH=src python -c "
from logiroute.config import load_scenario
b = load_scenario('config/scenario.json')
ids, m = b.graph.get_adjacency_matrix(metric='distance')
print(f'V={len(ids)}, V^2={len(m)**2}, 实际有向边={b.graph.edge_count}')
print(f'邻接矩阵单元利用率 = {b.graph.edge_count / len(m)**2:.1%}')
"
```

---

### Q2：邻接表一定是链表吗？用 `dict` 实现是否合规？

**简明**：邻接表是一种**抽象结构**，不强制链表。哈希实现是稀疏图场景的
**标准做法**之一，完全合规。

**详细原理**：
* 经典教材"邻接表"既可以用 `list[NodeRef]`（链表式）也可以用
  `dict[NodeId, Edge]`（哈希式）。
* 链表式适合"加边后只遍历、不频繁查任意边"的场景；哈希式适合"频繁
  `has_edge(u, v)`"的场景。
* 本场景的 Phase 2 Dijkstra 会反复调用 `has_edge` 与 `decrease_key`，
  哈希实现 O(1) 更合适。
* 课程标准未要求邻接表必须用链表实现。

**源码位置**：`logistics_graph.py:96-97`、`tests/test_graph.py:TestEdgeOperations`。

**演示**：
```python
g = LogisticsGraph()
g.add_edge(Edge("A","B", distance=1, travel_time=2, cost=3))
print(g.has_edge("A","B"))  # O(1) avg —— 哈希均摊
print(g.get_neighbors("A"))  # O(deg("A"))
```

---

### Q3：有向图和无向图的区别是什么？配送路网为什么必须有向？

**简明**：无向图的边是双向隐含的；有向图显式区分起点终点。

**详细原理**：
* **无向图** $G=(V,E)$ 中，$\{u,v\} \in E$ 等价于 $u \to v$ 与 $v \to u$；
* **有向图** $G=(V,E)$ 中，$(u,v) \in E$ 明确表示从 $u$ 出发到 $v$ 的单向边；
* **配送路网必须有向**的实际原因：
  1. **单行道 / 转弯限制 / 潮汐车道** —— 现实中存在大量方向约束；
  2. **道路等级不对称** —— 主路与支路在两个方向上的 `travel_time`
     差异显著；
  3. **强连通性才有意义** —— 弱连通但不强连通时，"从 A 出发能到 B"
     但"B 不能回到 A"，意味着无法形成**闭合回路**，对"仓库→客户→仓库"
     配送不成立。

**源码位置**：`config/loader.py:140-141`（`network.directed = true` 强校验）、`:228-235`（强连通性检查）。

**演示**：
```python
g = LogisticsGraph()
g.add_node(_node("A")); g.add_node(_node("B")); g.add_node(_node("C"))
g.add_edge(_edge("A","B"))
g.add_edge(_edge("B","C"))
# A→B→C 存在；C→A 不存在
print(g.has_edge("A","B"))  # True
print(g.has_edge("B","A"))  # False
```

---

### Q4：三种边权（distance / travel_time / cost）为什么不能直接混在一起？

**简明**：三者量纲不同（公里 / 分钟 / 元），直接相加无物理意义。

**详细原理**：
* `distance` 单位是 km，`travel_time` 单位是 min，`cost` 单位是元；
* `1.0 km + 2.0 min + 3.0 元` 数值上能加，但**没有物理意义**；
* Phase 3 多目标优化要做**线性加权**：先做 min-max 归一化，再用
  `w_d·distance' + w_t·time' + w_c·cost'` 形式加权和。
* 在 Phase 2 Dijkstra 中，`weight(metric)` 通过字符串分发改用单个
  度量，避免跨度量混淆。

**源码位置**：`core/edges.py:76-88`（`weight` 三度量分发）、`architecture.md` 规划 Phase 3 归一化。

**演示**：
```python
e = Edge("A","B", distance=10.0, travel_time=15.0, cost=8.0)
print(e.weight("distance"))  # 10.0
print(e.weight("travel_time"))  # 15.0
print(e.weight("cost"))  # 8.0
```

---

### Q5：BFS 为什么使用队列？DFS 为什么使用栈？

**简明**：BFS 按"层"扩展，先入先出 → 队列；DFS 沿"路径"深探，后入先出 → 栈。

**详细原理**：
* **BFS** 用于"找最近 / 最短（无权图）/ 层级遍历"：
  节点 `u` 入队后，其所有未访问邻居依次入队。先访问 `u` 的邻居，再
  访问邻居的邻居，这要求"先入队的先处理"——FIFO 队列。
* **DFS** 用于"路径搜索 / 拓扑序 / SCC 分解"：
  沿当前路径深入到底再回溯，这要求"后入的先处理"——LIFO 栈。
* 二者仅是数据结构差异，**控制循环都是显式手写**的。

**源码位置**：
* BFS：`config/loader.py:475-505`（弱连通），使用 `ArrayQueue`（`graph/queue.py:42-128`）；
* DFS：`config/loader.py:547-560`（强连通判定），使用 `list` 显式栈。

**演示**：
```python
from logiroute.graph.queue import ArrayQueue
q = ArrayQueue()
for x in [1, 2, 3]: q.enqueue(x)
print([q.dequeue() for _ in range(3)])  # [1, 2, 3] —— FIFO
```

---

### Q6：如何证明图是强连通的？

**简明**：双向 DFS —— 任取起点 `s`，在正图能从 `s` 到达所有节点，
**且**在反图也能从 `s` 到达所有节点。

**详细原理**：
* 设反图 $G^T$ 的边集为 $\{(v,u) | (u,v) \in E\}$；
* **定理**（Kosaraju 判定情形）：$G$ 强连通 $\iff$ 任取 $s \in V$，
  $G$ 中 `s` 可达所有节点 **且** $G^T$ 中 `s` 可达所有节点。
* 这比完整 Kosaraju（求 SCC 划分）简单，复杂度仍是 O(V+E)，但**只
  判定、不分解**。
* 本项目用 `_dfs_reaches_all`（显式栈迭代）在正图和反图各跑一次。

**源码位置**：`config/loader.py:508-560`。

**演示**：
```python
from logiroute.config import load_scenario
b = load_scenario("config/scenario.json")
from logiroute.config.loader import _is_strongly_connected
print(_is_strongly_connected(b.graph, list(b.graph.get_all_nodes())))  # True
```

---

### Q7：为什么需要反向邻接表（`_in_edges`）？

**简明**：没有反向邻接表，所有"以某点为目的点"的操作都要 O(E) 扫全图。

**详细原理**：
* Phase 1 已用：`_validate()` 用入边检查双向索引一致性；`get_in_edges`
  O(deg_in) 取入边；
* Phase 3（已规划）反向松弛：当多目标加权时，可以反向 Dijkstra
  减少对所有源点的重复计算；
* Phase 4（已规划）路径回溯：构造 `prev[]` 后，需要"哪些边汇入终点"
  以生成路径动画；
* Phase 5（已规划）增量重规划：某条边失效时，需要"所有受其影响的
  节点"快速定位。

**源码位置**：`logistics_graph.py:97`（字段定义）、`:263-271`（`get_in_edges`）。

**演示**：
```python
g = LogisticsGraph()
for n in "ABCD": g.add_node(_node(n))
g.add_edge(_edge("A","C")); g.add_edge(_edge("B","C"))
print([e.source_id for e in g.get_in_edges("C")])  # ['A', 'B'] —— O(deg_in)
```

---

### Q8：删除节点需要哪些操作？时间复杂度多少？

**简明**：清出边 + 清入边 + 删节点；时间 O(deg_in + deg_out)。

**详细原理**：
1. 对当前节点的每条出边 $(u, v)$，在 `_in_edges[v]` 里删 `u` 键；
2. 清空 `_out_edges[u]`；
3. 对当前节点的每条入边 $(v, u)$，在 `_out_edges[v]` 里删 `u` 键；
4. 清空 `_in_edges[u]`；
5. 删 `_nodes[u]`；
6. 维护不变：双向索引对象一致 / 无悬挂边 / 三表 key 集相等。

**源码位置**：`logistics_graph.py:117-134`。

**演示**：
```python
g = _sample_graph()  # 5 节点 5 边
g.remove_node("T1")  # 删 T1，其出边 (T1→C1, T1→C2) 和入边 (A→T1) 全部清理
g.validate()  # 一致性自检
print(g.node_count, g.edge_count)  # 4 2
```

---

### Q9：Dijkstra 为什么适合非负权重？

**简明**：Dijkstra 的贪心前提是"已确定的最短路径不会被后来更短的路径覆
盖"，这要求边权非负。

**详细原理**：
* Dijkstra 维护 `dist[]` 数组，每次从"未确定的最小 dist"取一个节点
  `u`，将 `u` 标记为"已确定"，然后松弛 `u` 的所有邻居；
* 当边权 ≥ 0 时，**任何经过 `u` 的路径都不可能比 `dist[u]` 更短**，
  因为 `u` 已经"最小"了。
* 如果存在负权边，可能"绕远路"反而更便宜，贪心失效；这种情况需要
  Bellman-Ford。
* 本项目 `Edge.__post_init__` 强制拒绝负权、NaN、inf（`core/edges.py:21-25, 60-62`），
  保证 Dijkstra 的前提始终成立。

**源码位置**：`core/edges.py:21-25`（非负校验）、`docs/development-plan.md` Phase 2。

**演示**：
```python
# Edge 拒绝负权
try:
    Edge("A","B", distance=-1, travel_time=1, cost=1)
except ValueError as e:
    print("rejected:", e)
```

---

### Q10：Dijkstra 能否解决多客户配送顺序问题（VRP）？

**简明**：**不能**。Dijkstra 是**单对**最短路 / 单源最短路；多客户
配送顺序（VRP）需要的是"路径序列"，属于组合优化。

**详细原理**：
* **Dijkstra** 的输出是"从起点 s 到目标 t 的最短路"，或"单源到所有
  节点的最短路"；它**不**关心"经过哪些中间节点、按什么顺序"。
* **多客户 VRP** 需要求"经过多个客户点并返回起点"的回路（Hamilton
  圈变种），这属于 NP-hard 组合优化。
* 课程计划（Phase 4）：用**最近邻 + 2-opt** 启发式做 VRP，用 Dijkstra
  计算每段路段的最短距离。

**源码位置**：`docs/development-plan.md` Phase 2 / Phase 4；`docs/architecture.md` 第 2.4、2.5 节。

**演示**：在 Phase 4 实现前，可口头说明思路，不展示代码（不虚构）。

---

### Q11：邻接矩阵的初始化是 O(V²) 还是 O(V+E)？

**简明**：**O(V²)**。这是早前 docstring 误写为 O(V+E) 的地方，本阶段
已修正。

**详细原理**：
* `matrix = [[_INF] * n for _ in range(n)]` 本身是 V×V 的写入，**不可
  忽略**；
* 之后 `for source_id, out_map in self._out_edges.items()` 遍历邻接表
  填充是 O(E)；
* 总时间 O(V² + E)，V² 在 V 较大时主导。

**源码位置**：`logistics_graph.py:362-393`（`get_adjacency_matrix`）。

**演示**：
```python
g = _sample_graph()
ids, m = g.get_adjacency_matrix(metric="distance")
print(f"V={len(ids)}, V^2={len(m)**2}, 实际有向边={g.edge_count}")
# 35 节点场景：V^2=1225, 实际有向边=192, 利用率约 15.7%
```

---

### Q12：时间复杂度如何计算？给我一个例子。

**简明**：以 `BFS 弱连通`为例说明。

**详细原理**：
* 输入：图 $G=(V,E)$，从任一节点出发做 BFS；
* 每条边最多被访问 2 次（正向 + 反向无向化时插入两条）→ **O(E)**；
* 每个节点最多入队 + 出队各 1 次 → **O(V)**；
* 集合 `visited` 的 `in` 操作均摊 O(1)；
* `ArrayQueue.enqueue / dequeue` 均为 O(1) 摊销；
* 总计 **O(V + E)**，空间 O(V)（队列 + visited 集合）。

**源码位置**：`config/loader.py:475-505`。

**演示**：通过 `tests/test_phase1_regression.py::TestConnectivityChecks` 验证。

---

### Q13：为什么动态更新不能只修改邻接矩阵？

**简明**：邻接矩阵是**按需导出的视图**，不是主存；删边 / 改权必须更新
邻接表（主存），矩阵下次调用时再生成。

**详细原理**：
* 主存是 `_out_edges` / `_in_edges` 哈希表，所有"真相"在那里；
* 邻接矩阵 `matrix = [[_INF]*n for _ in range(n)]` 在调用
  `get_adjacency_matrix` 时**新建**一份；
* 如果直接修改矩阵，下次调用会被覆盖，**修改会丢失**；
* 一致性原则：**单一数据源** + **视图按需生成**，避免双份数据不同步。

**源码位置**：`logistics_graph.py:335-393`、`architecture.md` 第 2.2.1 节。

**演示**：
```python
g = _sample_graph()
e = g.get_edge("A","T1")
e.distance = 99.0  # 改边权
_, m1 = g.get_adjacency_matrix(metric="distance")
# 矩阵反映最新边权 —— 因为是从主存（_out_edges）重新生成
print(m1[0][1])  # 99.0
```

---

### Q14：如何证明程序没有调用现成算法库？

**简明**：(1) `pyproject.toml` 的 `dependencies = []`；(2) 全项目
`grep -rE "import networkx|import numpy|import scipy|import heapq"` 无结
果；(3) 121+40 = 161 个 unittest 全通过；(4) 源码注释自证。

**详细原理**：
* **依赖声明**：`pyproject.toml` 中 `dependencies = []`，零运行期三方包。
* **关键字扫描**：

  ```bash
  grep -rE "import networkx|import numpy|import scipy|import heapq" src/
  # 期望：无输出
  ```
* **测试覆盖**：`PYTHONPATH=src python -m unittest discover -s tests -t .`
  实测 161 / 161 通过，0.067 s。
* **代码自证**：所有"算法"段（BFS / DFS / 字段校验 / 状态机迁移）都
  是显式 `while` 循环 + 分支判断，没有 `scipy.sparse.csgraph.dijkstra`
  这类调用。

**源码位置**：`pyproject.toml:19`（`dependencies = []`）、`tests/test_*` 全部 161 个用例。

**演示**：
```bash
cd "C:/Users/earthgrass73/Desktop/数据结构课设"
grep -rE "import networkx|import numpy|import scipy|import heapq" src/ || echo "no prohibited imports"
PYTHONPATH=src python -m unittest discover -s tests -t .
```

---

### Q15：你的 `Edge` 是 mutable 的，会不会被外部改了端点后破坏图？

**简明**：是的，这是已知风险；本项目通过**两阶段设计**缓解：①图层校
验、②`validate()` 自检、③测试暴露。

**详细原理**：
* `Edge` 是非冻结 dataclass（`core/edges.py:33`），允许修改 `distance` /
  `travel_time` / `cost` 等"业务可变"字段；
* 但**端点 `source_id` / `target_id` 不应在加图后修改**——会破坏
  `_out_edges[src][tgt] is _in_edges[tgt][src]` 的双向同对象不变量；
* 本项目当前**不**强制将端点设为不可变（避免冻结后无法调整边权的设计
  摩擦），但通过 `validate()` 暴露此类破坏，供测试捕获。

**源码位置**：`core/edges.py:33-89`、`logistics_graph.py:397-437`
（`validate`）、`tests/test_phase1_regression.py::TestEdgeMutationImpact`。

**演示**：
```python
g = LogisticsGraph()
g.add_node(_node("A")); g.add_node(_node("B")); g.add_node(_node("C"))
e = _edge("A","B", d=1.0)
g.add_edge(e)
e.source_id = "C"  # 故意破坏
try:
    g.validate()
except GraphError as exc:
    print("captured:", exc)
```

---

### Q16：FIFO 队列为什么要自实现 `ArrayQueue`，而不是用 `collections.deque`？

**简明**：教师要求"核心数据结构自主实现"，FIFO 队列是 BFS 的核心部件。

**详细原理**：
* `collections.deque` 是标准库数据结构（C 类），不是 A/B 基础；
* BFS 算法的"按层访问"逻辑仍是我手写的（`config/loader.py:475-505`），
  但队列本身若用 `deque`，就引入了标准库数据结构；
* `ArrayQueue`（`graph/queue.py:42-128`）用 `list` + 递增 `head` 实现：
  * `enqueue` O(1) 摊销（`list.append`）；
  * `dequeue` O(1)（`self._buf[self._head]; self._head += 1`）；
  * `is_empty` / `__len__` O(1)；
  * `compact` O(n) 主动回收；
* BFS 短期使用，队列随函数栈释放，无需环形缓冲。

**源码位置**：`graph/queue.py:42-128`、`config/loader.py:489-505`（BFS）、
`tests/test_queue.py`（18 用例）。

**演示**：
```python
from logiroute.graph.queue import ArrayQueue
q = ArrayQueue()
for x in [1,2,3]: q.enqueue(x)
print([q.dequeue() for _ in range(3)])  # [1, 2, 3]
print(q.is_empty())  # True
```

---

### Q17（加分题）：如果配送路网是 1000 节点、5000 边，本项目的图结构还合适吗？

**简明**：完全合适；复杂度不变。

**详细原理**：
* 邻接表空间 O(V+E) = 6030；矩阵空间 O(V²) = 1,000,000，矩阵浪费
  99.4% 空间 → 邻接表优势更明显。
* 单边操作 O(1) avg 不变；`edge_count` O(V) 仍可接受；`validate`
  O(V+E) = 6000 仍是常数级别操作。
* Dijkstra（Phase 2）O((V+E) log V) = 6000·log(1000) ≈ 60,000，对
  1000 节点图仍亚毫秒级。
* `__slots__` 收紧内存让 Python `dict` 内存更紧凑，1000 节点图仍可
  一次性加载。

**源码位置**：`logistics_graph.py:91-97`（`__slots__` 与字段定义）。

**演示**：可通过 `python scripts/generate_scenario.py --nodes 1000`（需先实现）演示；当前未提供生成器，可口头说明。

---

## 三、答辩规范（学生执行守则）

### 3.1 回答流程

每题按以下 4 步回答：

1. **简明回答**（1 句话）：结论先行；
2. **详细原理**（2-4 句话）：讲清"为什么"和"怎么做"；
3. **源码位置**：给出文件 + 行号（如果可以）；
4. **演示入口**：能在 IDE / 终端复现。

### 3.2 注意事项

* **不要背诵空泛描述**（"采用高效算法" / "用合适的数据结构"）。必须精确到具体实现；
* **不要声称未实现的功能**（Dijkstra / 2-opt / 随机生成器）。如实说
  "Phase 2 计划实现，当前是规划文档"；
* **不要回避缺陷**。如被问及已知问题（如 `Edge` 端点可变），先承认、
  再说明缓解策略；
* **所有事实陈述都应有源码行号或测试用例为证据**。

### 3.3 推荐答辩节奏

* 教师提问后，先**复述问题**确认理解；
* 再按 4 步流程回答，约 1-2 分钟；
* 最后**反问"老师是否想看某段代码演示"**——主动展示能力。

---

## 四、答辩前 5 分钟自检清单

- [ ] 已 `git pull` 同步最新代码
- [ ] 已运行 `PYTHONPATH=src python -m unittest discover -s tests -t .` 并确认 161 用例通过
- [ ] 已打开 `src/logiroute/` 4 个核心源文件与 `docs/data-structures-and-algorithms.md`
- [ ] 已熟悉 `tests/test_queue.py` 和 `tests/test_phase1_regression.py` 的具体用例
- [ ] 能口头说出 35 / 192 / 4 / 4 / 20 这五个数字的含义
- [ ] 能口头说出 `_is_strongly_connected` 是"双向 DFS 判定"而非"完整 Kosaraju"
- [ ] 能口头说出 `get_adjacency_matrix` 的复杂度是 **O(V² + E)**
- [ ] 能口头说出 BFS 用 `ArrayQueue` 而非 `collections.deque`
