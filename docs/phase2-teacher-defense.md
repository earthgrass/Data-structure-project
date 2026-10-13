# LogiRoute — 第二次课程检查教师答辩材料（Phase 2）

> 本文件包含：5 分钟演示稿、24+ 教师提问与标准答案。
> Phase 1 答辩材料仍位于 `docs/phase1-teacher-defense.md`，**不要覆盖**。

---

## 一、五分钟课堂演示

### 第一分钟 —— 有向带权图与邻接表

> 老师好，Phase 2 我做了 Dijkstra 单源最短路。
>
> 起点是 Phase 1 完成的 `LogisticsGraph` —— 三张哈希表
> `_nodes` / `_out_edges` / `_in_edges`。
>
> Dijkstra 只**消费** `get_neighbors(u)` 拿到 u 的出边，**不**修改图，
> 也不**触碰** `_in_edges`（那是 Phase 4 反向松弛用的）。
>
> 给定源点 s，Dijkstra 要找 s 到所有其它节点的最短距离。

### 第二分钟 —— 最小堆的结构与上浮、下沉

> 我没有用 `heapq`，而是自己实现了一个**索引式二叉最小堆**
> `MinHeap`（`src/logiroute/algorithms/heap.py`）。
>
> 数组版完全二叉树：父节点 ``(i-1)//2``，左孩子 ``2i+1``，右孩子 ``2i+2``。
>
> **三个关键操作**：
>
> 1. `push`：插末尾后**上浮**——O(log V)；
> 2. `pop_min`：移末尾到顶后**下沉**——O(log V)；
> 3. `decrease_key`：靠 `_pos: dict[node_id, int]` 辅助映射 O(1) 定位后**上浮**——O(log V)。
>
> 我特别维护了**位置映射**，让 decrease_key 不需要线性扫描。这是
> Dijkstra 性能的**关键**—— 否则每次 decrease_key 都是 O(V)。

### 第三分钟 —— Dijkstra 初始化与松弛操作

> 算法状态（`dijkstra.py`）：
>
> * `dist: dict[node_id, float]` —— 当前已知最短距离
> * `prev: dict[node_id, node_id | None]` —— 路径前驱
> * `settled: set[node_id]` —— 已确定最短距离的节点
> * `MinHeap` —— 待处理候选集合
>
> 初始化：`dist[source] = 0`、其他 `= inf`，全 `prev = None`。
>
> **核心循环**（伪代码）：
>
> ```
> while heap 非空:
>     u, du = pop_min()
>     if u in settled: continue      # 懒删除
>     settled.add(u)
>     for edge in get_neighbors(u):
>         v = edge.target_id
>         if v in settled: continue
>         new = du + edge.weight(metric)
>         if new < dist[v]:
>             dist[v] = new
>             prev[v] = u
>             heap.decrease_key(v, new)
> ```
>
> **贪心正确性**：当 `u` 第一次弹出时，`dist[u]` 是最终最短距离——证明见
> 课程文档 §6.1。

### 第四分钟 —— 三种权重对比和实际输出

> 同一对 `(A, D)`（4 节点 toy graph）跑三种 metric：
>
> * **distance**: 路径 `A→B→C→D`，总 4.0
> * **travel_time**: 路径 `A→C→D`，总 2.0
> * **cost**: 路径 `A→C→D`，总 11.0
>
> 三种 metric 给出**不同路径**，因为 `B→D` 距离短但时间长；
> `A→C` 距离长但时间和成本最优。
>
> 在固定场景（35 节点 / 192 边）上对 `(W1, C1)`：
>
> * distance 路径 `W1→T1→C1`，总 9.55
> * travel_time 路径 `W1→T1→C1`，总 23.84
> * cost 路径 `W1→T1→C5→C1`，总 11.36
>
> 我可以现场跑 `python scripts/demo_dijkstra.py` 演示。

### 第五分钟 —— 复杂度分析、测试结果、未来扩展

> **复杂度**：O((V + E) log V) 时间，O(V) 辅助空间（不含 trace 输出）。
>
> **测试**：32 个堆 + 31 个 Dijkstra = 63 个新测试，加上 Phase 1 的
> 161 个，**总 224 个用例，全部通过**（实测 0.3 秒）。
>
> 三种 metric **共用同一 Dijkstra 实现**，通过 `edge.weight(metric)` 切换，
> 没有 `dijkstra_distance` / `dijkstra_time` / `dijkstra_cost` 三份代码。
>
> **未来扩展**（**未实现**）：
>
> * Phase 3：多目标线性加权（min-max 归一化 + 加权）；
> * Phase 4：TSP / VRP、最近邻 + 2-opt、时间窗硬约束；
> * Phase 5：随机场景生成 + 动态事件 + 增量重规划。
>
> 演示结束，欢迎老师提问。

---

## 二、教师可能提问（24 题）

> 每题：**简明回答** → **详细原理** → **源码位置** → **演示入口**。

---

### Q1：为什么使用 Dijkstra？

**简明**：在非负权有向图上求最短路的多项式算法。

**详细原理**：
* BFS 仅适用边权 = 1 的无权图；
* Bellman-Ford 支持负权但 O(VE)，过慢；
* Dijkstra 在非负权假设下，用贪心 + 优先队列达到 O((V+E) log V)；
* 本场景（配送路网）所有边权均非负（`Edge.__post_init__` 强制拒绝负权 / NaN / inf），
  满足前提。

**源码位置**：`src/logiroute/algorithms/dijkstra.py`、`docs/algorithms-dijkstra.md` §1。

**演示**：
```python
from logiroute.algorithms.dijkstra import shortest_path
r = shortest_path(graph, "W1", "C1", metric="distance")
print(r.path, r.total_weight)
```

---

### Q2：为什么不用 BFS？

**简明**：BFS 解决"最少边数"问题；Dijkstra 解决"最小权重"问题。本场景边权有差异，必须用 Dijkstra。

**详细原理**：
* BFS 按"层序"扩展，每步代价 = 1；
* Dijkstra 按"暂定距离"扩展，每步代价 = 边权；
* 当所有边权都 = 1 时，Dijkstra **退化**为 BFS；
* 反之 BFS 给出错误结果。

**源码位置**：`dijkstra.py:dijkstra_single_source` 整体循环。

**演示**：toy graph 中 `A→B` 权 10、`A→C` 权 1、`C→B` 权 1，
BFS 会先 A→B（边数 1），但 Dijkstra 给出 A→C→B（权重 2）。

---

### Q3：Dijkstra 和 BFS 的本质区别是什么？

**简明**：BFS 用 FIFO 队列保证"按层"扩展；Dijkstra 用优先队列保证"按距离"扩展。

**详细原理**：
* **数据结构**：BFS = `deque`/FIFO；Dijkstra = `MinHeap`/优先队列；
* **节点处理顺序**：BFS 按入队先后；Dijkstra 按 `dist[u]` 升序；
* **正确性前提**：BFS 仅限无权图；Dijkstra 仅限非负权图；
* **通用化**：Dijkstra ⊃ BFS（BFS = 边权 1 的 Dijkstra）。

**源码位置**：`dijkstra.py` + `core/queue.py`（自实现 BFS 队列）。

---

### Q4：为什么用邻接表而不是邻接矩阵？

**简明**：本场景是稀疏图（35 节点 / 192 边 ≈ 5.5V），邻接表 O(V+E) 远优于矩阵 O(V²)。

**详细原理**：
* 邻接表 `get_neighbors(u)` O(deg(u))，单次遍历只访问相关边；
* 邻接矩阵单次遍历 O(V)，大部分是浪费；
* Dijkstra 主循环每节点调用一次 `get_neighbors` → 邻接表共 O(E)，矩阵共 O(V²)；
* 矩阵按需导出（Phase 1）已存在，本阶段不重复维护。

**源码位置**：`logistics_graph.py:96-97`（邻接表）、`dijkstra.py:_weight_of`。

**演示**：
```python
g = load_scenario("config/scenario.json").graph
print(f"V={g.node_count}, E={g.edge_count}, density={g.edge_count/(g.node_count**2):.1%}")
```

---

### Q5：Dijkstra 为什么要求非负边权？

**简明**：贪心不变量（首次弹出即最终距离）依赖"经过未确定节点的路径不可能更短"——这需要边权非负。

**详细原理**：
* 若有负权边 `(x, y)` 权 -10：
  * 假设 `x` 先弹出，`dist[x] = 5`（确定）；
  * `dist[y]` 当前 = 7（通过另一条路径）；
  * 但 `x → y` 边权 -10 使真实 `source → y` 最短 = -5；
  * `y` 的 `dist` 永远不会被更新（y 可能比 x 先弹出，弹出后 dist 不再改）；
* 正确处理负权需 Bellman-Ford O(VE)。

**源码位置**：`core/edges.py:21-25, 60-62`（拒绝负权 / NaN / inf）。

**演示**：
```python
try:
    Edge("A","B", distance=-1, travel_time=1, cost=1)
except ValueError as e:
    print("rejected:", e)
```

---

### Q6：最小堆是什么？

**简明**：一种支持"插入元素 + 始终能 O(1) 取最小 + O(log n) 删除最小"的数据结构。

**详细原理**：
* 实现方式：二叉堆（最常见）/ 斐波那契堆（左式堆等）；
* 本项目用**二叉堆**（数组版完全二叉树）；
* 关键不变量：父节点 ≤ 子节点（最小堆）。

**源码位置**：`src/logiroute/algorithms/heap.py:MinHeap` 类。

**演示**：
```python
from logiroute.algorithms.heap import MinHeap
h = MinHeap()
for k, v in [("a",3),("b",1),("c",2)]: h.push(k, v)
print(h.pop_min())  # ('b', 1)
```

---

### Q7：二叉堆为什么能用数组实现？

**简明**：完全二叉树层序遍历与数组下标一一对应，父子下标公式简单。

**详细原理**：
* 0-based 数组：父 ``(i-1)//2``、左 ``2i+1``、右 ``2i+2``；
* 完全二叉树 = 满树或最后一层不满的树，节点连续，无空缺；
* 无需指针 / `None` 标记，缓存友好。

**源码位置**：`heap.py:_sift_up` / `_sift_down`（使用上述公式）。

**演示**：
```python
h = MinHeap()
for k, v in [("a",3),("b",1),("c",2)]: h.push(k, v)
print(h._heap)  # 内部数组：[(b,1), (a,3), (c,2)]
```

---

### Q8：上浮和下沉分别什么时候执行？

**简明**：上浮——push 与 decrease_key；下沉——pop_min。

**详细原理**：
* **上浮**（sift_up）：插入末尾 / 优先级下降，新元素可能比父节点小，要上浮到正确位置；
* **下沉**（sift_down）：删除堆顶后把末尾元素放到堆顶，新堆顶可能比孩子大，要下沉；
* 两者都是 O(log V)。

**源码位置**：`heap.py:_sift_up` / `_sift_down`。

**演示**：见 `tests/test_heap.py:TestPushPop.test_push_preserves_min`。

---

### Q9：为什么需要 decrease_key？

**简明**：Dijkstra 中某节点的暂定距离可能多次下降，必须能高效更新它在堆中的优先级。

**详细原理**：
* 朴素法：删除 + 重新插入 → 产生重复条目，且要做两次 O(log V)；
* 索引式：O(1) 定位 + O(log V) 上浮 → 仍 O(log V)，但避免重复条目；
* 拒绝"增大"：Dijkstra 中距离不应增大；强行增大破坏不变量。

**源码位置**：`heap.py:decrease_key`。

**演示**：
```python
h.push("a", 5); h.push("b", 3)
h.decrease_key("a", 1)  # a 上浮到顶
print(h.peek_min())  # ('a', 1)
```

---

### Q10：为什么使用位置映射？

**简明**：让 decrease_key 在 O(1) 摊销时间找到节点位置。

**详细原理**：
* 不用 `_pos`：必须 O(V) 扫描 `_heap` 找节点；
* 用 `_pos`：`dict[node_id, int]` 哈希表定位，O(1) avg；
* 维护成本：每次 push / pop_min / sift 操作同步更新 `_pos`，O(1)；
* 净收益：Dijkstra 整个循环 E 次 decrease_key，每次省 O(V) → 总省 O(VE)。

**源码位置**：`heap.py:__init__` / `_sift_up` / `_sift_down` / `pop_min`。

**演示**：见 `tests/test_heap.py:TestDecreaseKey`。

---

### Q11：dist 与 prev 分别有什么作用？

**简明**：dist 记最短距离；prev 记最短路径前驱，用于回溯。

**详细原理**：
* `dist[v]`：`source → v` 当前已知最短距离；弹入 settled 后成为最终值；
* `prev[v]`：在 `source → v` 的最短路径上，`v` 的前驱节点；
* 回溯：`target → prev[target] → ... → source` → reverse → 正向路径；
* `dist[source] = 0`、`prev[source] = None`。

**源码位置**：`dijkstra.py:dijkstra_single_source`（初始化与更新）。

**演示**：
```python
ss = dijkstra_single_source(g, "A", metric="distance")
print(ss["dist"]["D"], ss["prev"]["D"])  # 4.0, 'C'
```

---

### Q12：settled 代表什么？

**简明**：已最终确定最短距离的节点集合。

**详细原理**：
* 加入条件：节点 `u` 从堆中**首次**弹出时；
* 含义：`dist[u]` 即 `source → u` 的最终最短距离；
* 不在 settled 的节点：`dist` 仅为"已知候选"，可能再被 decrease_key。

**源码位置**：`dijkstra.py:settled` 变量与 `settled.add(u)` 行。

**演示**：
```python
ss = dijkstra_single_source(g, "A", metric="distance")
print(ss["settled"])  # ('A', 'B', 'C', 'D') —— 按确定顺序
```

---

### Q13：松弛操作是什么？

**简明**：检查通过 `u` 到 `v` 是否比当前已知 `dist[v]` 更短，若是则更新。

**详细原理**：
* 公式：`dist[v] = min(dist[v], dist[u] + w(u,v))`；
* 含义：每条候选路径都要被考虑一次；
* 实现：在 Dijkstra 主循环中 `if new_dist < dist[v]: dist[v] = new_dist`；
* 时间：每次 O(1)，每条边最多做 O(1) 次成功松弛。

**源码位置**：`dijkstra.py:130-138`（核心松弛代码）。

**演示**：
```python
# toy_graph 中：A→B 权 1，A→C 权 4
ss = dijkstra_single_source(toy_graph(), "A", "distance")
# 弹出 A 后：
#   松弛 A→B：dist[B] = min(inf, 0+1) = 1
#   松弛 A→C：dist[C] = min(inf, 0+4) = 4
print(ss["dist"])
```

---

### Q14：Dijkstra 的贪心选择为什么正确？

**简明**：非负权下，从堆中弹出的最小 dist 节点不可能再被任何其他路径超越。

**详细原理**：
* 假设 `u` 是当前堆中最小 dist = `du`；
* 任何 `source → u` 的路径 `P` 必经过若干 settled 节点 → 第一个非 settled 节点 `x`；
* 由堆序：`du ≤ dist[x]`，`P` 长度 ≥ `dist[x]` ≥ `du`；
* 故 `du` 是 `source → u` 的最短距离；
* 详细证明见 `docs/algorithms-dijkstra.md` §6.1。

**源码位置**：`dijkstra.py` 主循环 + `docs/algorithms-dijkstra.md` §6。

---

### Q15：为什么三种目标可以共享一套算法？

**简明**：三种 metric 都是非负实数边权；算法不关心物理含义，只做"求和最小"。

**详细原理**：
* Dijkstra 内部**只**调用 `edge.weight(metric)`；
* `Edge` 已实现 `weight(metric)`（`core/edges.py:76-88`）支持三种 metric；
* 算法核心无任何 `if metric == "distance"` 之类分支；
* **禁止**为三种 metric 写三份独立代码（教师红线）。

**源码位置**：`dijkstra.py:_weight_of`（统一读取）+ 整个循环无 metric 分支。

**演示**：
```python
for m in ("distance", "travel_time", "cost"):
    r = shortest_path(g, "A", "D", metric=m)
    print(m, r.path, r.total_weight)
```

---

### Q16：最短距离和最短时间为什么可能不同？

**简明**：物理上两者独立（道路长度 vs 通行时间）；一条路可能"短但慢"或"长但快"。

**详细原理**：
* 例：高速路距离 100 km / 60 min vs 市区路 80 km / 90 min；
* 最短距离选市区路（80 km），最短时间选高速路（60 min）；
* 不同的"成本函数"对应不同的最优路径。

**源码位置**：`scripts/demo_dijkstra.py:toy_graph`（精心构造的三 metric 差异示例）。

**演示**：见 `tests/test_dijkstra.py:TestThreeMetrics` 与 demo 脚本。

---

### Q17：源节点无法到达终点怎么办？

**简明**：返回 `reachable=False`，`path=()`，`total_weight=+inf`。

**详细原理**：
* 终点不会被从堆中弹出（因为没有任何路径能使其暂定距离 < +inf）；
* `dist[target]` 保持 +inf；
* 接口返回 `PathResult(reachable=False, path=(), total_weight=inf, cross_metrics={})`；
* 早期停止版：当 target 不可达时，循环直到堆空才结束。

**源码位置**：`dijkstra.py:shortest_path` 中 `if not found or dist[target] == inf` 分支。

**演示**：
```python
g = LogisticsGraph()
for n in ("A","B"): g.add_node(_node(n))
# 无边：A→B 不可达
r = shortest_path(g, "A", "B", "distance")
print(r.reachable, r.path, r.total_weight)
```

---

### Q18：如何处理相同权重的路径？

**简明**：tie-break 按 `node_id` 字典序，保证确定性。

**详细原理**：
* 堆内比较键 = `(priority, node_id)`；
* 相同 priority 时 node_id 字典序更小者排前；
* 多次运行同输入得到稳定输出；
* 距离相同时选择不同路径不影响正确性（都是最短路）。

**源码位置**：`heap.py:_less_or_equal`。

**演示**：
```python
h = MinHeap()
for nid in ("b","c","a"): h.push(nid, 1.0)
print([h.pop_min()[0] for _ in range(3)])  # ['a', 'b', 'c']
```

---

### Q19：算法时间复杂度如何推导？

**简明**：初始化 O(V) + 堆操作 O((V+E) log V) + 边遍历 O(E) = O((V+E) log V)。

**详细原理**：
* `dist` / `prev` 初始化：O(V)；
* `push(source, 0)`：O(log V)；
* `pop_min` 至多 V 次：O(V log V)；
* `decrease_key` / `push`（松弛）至多 E 次：O(E log V)；
* `get_neighbors(u)` 总和 O(Σdeg) = O(E)；
* 边权读取 O(1)，比较 O(1)；
* 总计 **O((V + E) log V)**。

**源码位置**：`docs/algorithms-dijkstra.md` §5。

---

### Q20：堆版本为什么通常比线性查找版本更适合稀疏大图？

**简明**：稀疏图 E ≪ V²，堆的 O(log V) 远胜线性扫描 O(V)。

**详细原理**：
* 线性版：每次取最小 O(V)，V 次共 O(V²)；
* 堆版：每次取最小 O(log V)，V 次共 O(V log V)；
* E/V ≤ 10 时（配送路网 E/V ≈ 5.5），堆版总时间 O(V log V) ≪ O(V²)；
* 邻接矩阵扫描版：O(V²) 取最小，O(V²) 总时间。

**源码位置**：`docs/algorithms-dijkstra.md` §5.2（对比表）。

**演示**：
```python
# 35 节点 192 边的实测耗时
import time
t0 = time.perf_counter()
for s, t in itertools.combinations(g.node_ids, 2):
    shortest_path(g, s, t, "distance")
print(f"{time.perf_counter()-t0:.3f}s for 595 pairs")
```

---

### Q21：Dijkstra 能解决多客户配送顺序问题吗？

**简明**：**不能**。Dijkstra 是点对点最短路；多客户配送顺序是组合优化（VRP）。

**详细原理**：
* Dijkstra 输出"source → target"最短路，**不关心**经过哪些中间节点；
* 多客户 VRP：寻找"经过多个客户并返回起点"的回路，**NP-hard**；
* 课程计划（Phase 4）用最近邻 + 2-opt 启发式，每段用 Dijkstra 算最短距离。

**源码位置**：`docs/development-plan.md` Phase 4（规划中，未实现）。

---

### Q22：最小堆是否调用 Python 标准库？

**简明**：**没有**。完全自实现（`list` + 辅助 `dict`），**不**调用 `heapq`。

**详细原理**：
* 底层仅用 `list`（A 类基础容器）与 `dict`（A 类基础容器）；
* 不导入 `heapq` / `queue.PriorityQueue` / `sorted`；
* 全部上浮 / 下沉 / 位置映射逻辑手写。

**源码位置**：`heap.py` 全文（无外部数据结构 import）。

**演示**：
```bash
grep -E "import heapq|from heapq" src/logiroute/algorithms/heap.py
# 无输出
```

---

### Q23：如何验证你没有直接调用现成图算法？

**简明**：(1) `dependencies = []`；(2) grep 验证无 networkx / scipy；(3) 224 单测全过；(4) 算法代码可展示。

**详细原理**：
* `pyproject.toml` `dependencies = []` —— 零三方包；
* `grep -rE "import networkx|import numpy|import scipy|import heapq" src/` —— 无结果；
* 224 个 unittest 全部通过；
* 32 个堆 + 31 个 Dijkstra 测试覆盖了"由独立穷举得到正确性"的反向验证。

**源码位置**：`tests/test_dijkstra.py:TestExhaustiveConsistency`（穷举对照）。

**演示**：
```bash
PYTHONPATH=src python -m unittest discover -s tests -t .
# Ran 224 tests in 0.3s — OK
```

---

### Q24：道路拥堵后是否可以重新运行 Dijkstra？

**简明**：**可以**，但本项目尚未实现动态事件（Phase 5 规划）。

**详细原理**：
* Dijkstra 是**只读**算法：不修改图；
* 重新运行时用更新后的 `Edge.weight("travel_time")` 即可；
* 本场景的 `TrafficStatus` 已存在但尚未参与算法（`core/edges.py:TrafficStatus`）；
* Phase 5（未实现）将引入事件队列 + 增量重规划。

**源码位置**：`docs/development-plan.md` Phase 5。

**演示**：
```python
e = g.get_edge("A", "B")
e.travel_time = 999  # 拥堵
r = shortest_path(g, "A", "D", "travel_time")
print(r.path, r.total_weight)  # 反映拥堵后的最短时间
```

---

## 三、答辩规范

* **所有事实陈述都应有源码行号或测试用例为证据**；
* **不要把规划功能说成已实现**（Phase 3/4/5 都未做）；
* **回答时先复述问题**，再按"简明 / 详细 / 源码 / 演示"四步展开；
* **若被问及未实现功能**，如实说"Phase X 计划实现"。

---

## 四、答辩前 5 分钟自检

- [ ] 已 `git pull` 同步最新代码
- [ ] 已运行完整 224 个测试并确认通过
- [ ] 已准备好 `scripts/demo_dijkstra.py` 的输出
- [ ] 能口头说出"O((V+E) log V)" 的推导步骤
- [ ] 能口头说出"位置映射为什么必要"
- [ ] 能口头说出 Dijkstra 贪心不变量证明的关键三步
- [ ] 能口头说出 Phase 2 不实现的功能（VRP / 随机生成 / 动态）
