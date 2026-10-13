# Dijkstra 单源最短路 —— Phase 2 算法文档

> 本文档是 `src/logiroute/algorithms/dijkstra.py` 的课程教学材料。
> 配套测试：`tests/test_dijkstra.py`（31 个用例）。

---

## 一、问题定义

给定有向带权图 $G = (V, E)$，边权 $w : E \to \mathbb{R}_{\ge 0}$，
源节点 $s \in V$，求 $s$ 到所有其它节点 $v \in V$ 的最短距离：

$$
d(s, v) = \min_{P: s \to v} \sum_{(u, w) \in P} w(u, w)
$$

**前提**：所有边权 **非负**（$\ge 0$）。

**三种 metric**：

| metric | 物理意义 | 单位 |
| --- | --- | --- |
| `distance` | 道路长度 | km |
| `travel_time` | 通行时间 | min |
| `cost` | 运输成本 | 元 |

三种 metric 共享同一 Dijkstra 实现，通过 `edge.weight(metric)` 切换。

---

## 二、为什么需要 Dijkstra？

朴素枚举所有路径是指数级。Dijkstra 用**贪心** + **优先队列**在多项式时间内求解。

Dijkstra 与 BFS 的关系：

| 维度 | BFS | Dijkstra |
| --- | --- | --- |
| 边权 | 全部 = 1（无权） | 非负实数 |
| 数据结构 | FIFO 队列 | **优先队列（最小堆）** |
| 取出节点的顺序 | 按入队先后 | 按暂定距离最小优先 |
| 时间复杂度 | O(V + E) | O((V + E) log V) |
| 适用范围 | 无权图最短路（最少边数）| 非负权图最短路（最小权重）|

**BFS 是 Dijkstra 在边权全 1 时的特例**。

---

## 三、核心数据结构

### 3.1 `dist: dict[node_id, float]`

| 项 | 内容 |
| --- | --- |
| 作用 | 记录从 `source` 到各节点的**当前已知**最短距离 |
| 初始化 | `dist[source] = 0`；其他 `= +inf` |
| 更新时机 | 每次松弛成功 |
| 何时最终 | 当节点被加入 `settled` 后 `dist[u]` = 最终最短距离 |

### 3.2 `prev: dict[node_id, node_id | None]`

| 项 | 内容 |
| --- | --- |
| 作用 | 最短路径树上每个节点的前驱节点 |
| 初始化 | 全部 `None` |
| 更新时机 | 每次松弛成功后 `prev[v] = u` |
| 用于 | 路径回溯 |

### 3.3 `settled: set[node_id]`

| 项 | 内容 |
| --- | --- |
| 作用 | 已**最终确定**最短距离的节点集合 |
| 加入时机 | 节点从堆中**首次**弹出 |
| 不变量 | 任意 `u ∈ settled`：`dist[u]` 是 `source → u` 的最终最短距离 |

### 3.4 `MinHeap`

| 项 | 内容 |
| --- | --- |
| 元素 | `(node_id, dist[node_id])` |
| 排序键 | (priority, node_id) —— priority 升序，相同时 node_id 字典序 |
| 作用 | 维护"待处理"候选节点集合 |

### 3.5 三表关系图

```
                source
                  ↓ dist[source] = 0
                ┌─────┐
                │  0  │ ← 推入 MinHeap
                └──┬──┘
                   ↓ pop_min → 首次弹出
                ┌─────┐
                │  u  │ → 标记 settled
                └──┬──┘
                   ↓ 遍历 get_neighbors(u)
       ┌───────────┼───────────┐
       ↓           ↓           ↓
   边 (u,v1)   边 (u,v2)   边 (u,v3)
       ↓           ↓           ↓
  松弛: dist[v_i] = min(旧, dist[u] + w)
       ↓           ↓           ↓
  decrease_key(v_i, new_dist) 或 push(v_i, new_dist)
```

---

## 四、算法骨架

```python
def dijkstra(graph, source, metric):
    dist[source] = 0
    其他 dist = +inf
    所有 prev = None
    settled = ∅
    heap.push(source, 0)

    while not heap.is_empty():
        u, du = heap.pop_min()
        if u in settled: continue     # 懒删除
        settled.add(u)

        for edge in graph.get_neighbors(u):
            v = edge.target_id
            if v in settled: continue
            new_dist = du + edge.weight(metric)
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                if heap.contains(v):
                    heap.decrease_key(v, new_dist)
                else:
                    heap.push(v, new_dist)
    return dist, prev, settled
```

**两点版**（`shortest_path`）在 `u == target` 时**提前停止**，节省计算。

---

## 五、复杂度分析

设 V = 节点数，E = 边数。

### 5.1 主操作计数

| 操作 | 每次 | 调用次数 | 累计 |
| --- | --- | --- | --- |
| `dist` / `prev` 初始化 | O(V) | 1 | O(V) |
| `heap.push(source, 0)` | O(log V) | 1 | O(log V) |
| `heap.pop_min` | O(log V) | 至多 V 次 | O(V log V) |
| `heap.push` / `decrease_key` | O(log V) | 至多 E 次 | O(E log V) |
| `graph.get_neighbors(u)` | O(deg(u)) | 每个 u 一次 | O(Σ deg(u)) = O(E) |
| 松弛 / 比较 | O(1) | 至多 E 次 | O(E) |

**总时间**：O((V + E) log V)

**辅助空间**：

* `dist` O(V)
* `prev` O(V)
* `settled` O(V)
* `heap` O(V)
* **合计 O(V)**（与图邻接表存储 O(V+E) 独立）

**输出空间**（不计在内）：

* `TraceResult.steps`：O(R)，R = round 数 ≤ V
* `PathResult.cross_metrics`：O(1) 三个数

### 5.2 与简单实现对比

| 候选集合 | 取最小 | 减少优先级 | 总时间 |
| --- | --- | --- | --- |
| 无序数组 | O(V) | O(1) | **O(V²)** |
| 邻接矩阵扫描 | O(V²) | O(1) | **O(V²)** |
| **二叉最小堆（本项目）** | O(log V) | O(log V) | **O((V + E) log V)** |
| Fibonacci 堆（理论） | O(log V) 摊销 | O(1) 摊销 | O(V log V + E) |

**稀疏图场景**（E ≈ V）：二叉堆版 ≈ O(V log V)，远优于 O(V²)。

**稠密图场景**（E ≈ V²）：二叉堆版 ≈ O(V² log V)，比 O(V²) 慢；但本项目配送路网是**稀疏图**（E/V ≈ 5.5），二叉堆版是正确选择。

> **注**：本项目未实现无序数组版 / 邻接矩阵版作为对照实验；以上为**理论分析**，
> 不构成实测性能数据。

---

## 六、正确性证明

### 6.1 Dijkstra 贪心不变量

**声明**：在所有边权非负的前提下，节点 `u` 从堆中**首次**弹出时，`dist[u]` 即 `source → u` 的**最终最短距离**。

**证明**（教科书标准论证）：

**基例**：初始时 `dist[source] = 0`，其他 `dist = +inf`。当 `source` 从堆中弹出，`dist[source] = 0` 是 `source → source` 的最短距离。✓

**归纳步骤**：假设在第 k 轮之前，所有已弹出节点的 `dist` 都是最终最短距离。
设第 k 轮从堆中弹出 `u`（`dist[u] = du` 最小）。

考虑任意 `source → u` 的路径 P（不一定最短）：

* P 一定经过若干个 `settled` 节点 → 第一个**不在** `settled` 中的节点设为 `x`；
* 由堆序：当前 `u` 是堆中最小（`du`），所以 `du ≤ dist[x]`；
* `dist[x]` 是 `source → x` 的某条路径长度；
* P 的 `u` 之后部分权重 ≥ 0（P 包含非负边权）；
* 因此 P 的总长度 ≥ `dist[x]` ≥ `du` = `dist[u]`。

故 `du` 是 `source → u` 的最短距离。✓

**结论**：贪心选择正确。

### 6.2 边权非负是必要条件

若存在负权边 `(x, y)`：

* `dist[x]` 已确定 = 5；
* `dist[y]` 当前 = 7（经过另一条路径）；
* 但 `x → y` 边权 = -10；
* 真实最短 `source → y` = 5 + (-10) = -5；
* 但 `y` 的 `dist` 永远不会被更新（因为 `y` 可能比 `x` 先弹出，弹出后 `dist` 不再变）。

→ **Dijkstra 在负权下可能错误**。本项目 `Edge.__post_init__` 强制拒绝负权、NaN、inf（`core/edges.py:21-25, 60-62`），保证前提始终成立。

### 6.3 零权边的处理

零权边对应"经过 v 的路径长度等于 `dist[u]`"。

例如 `A→B` 权 0：

* `dist[A] = 5`；
* 弹出 A 后松弛 B：`new_dist = 5 + 0 = 5`；
* `dist[B] = min(7, 5) = 5`；
* 下次堆中最小可能是 B（与 A 的其它邻居同距离）；
* tie-break 按 node_id 字典序。

**结论**：Dijkstra 支持零权边，结果正确；仅在 tie-break 时影响选取顺序。

### 6.4 松弛不遗漏更短路径

`dist[v] = min(dist[v], dist[u] + w(u,v))` 的语义是：

* `dist[v]` 始终是"目前已知从 source 到 v 的最短路径长度"；
* 每次从堆中弹出一个 `u` 时，`u` 的距离已确定；
* 遍历 `u` 的所有出边 `(u, v)`，更新 `dist[v]` 候选；
* 若新候选 < 旧候选，则 `dist[v]` 变优。

**关键**：Dijkstra 不会主动"跳过"任何候选路径——每个 `(u, v)` 边都参与至少一次松弛。

### 6.5 路径回溯正确性

`prev[v] = u` 表示"在 `source → v` 的最短路径上，`v` 的前驱是 `u`"。

回溯过程：

```
path = []
cur = target
while cur is not None:
    path.append(cur)
    cur = prev[cur]
path.reverse()
```

因为 `prev` 链一定从 `target` 沿"前驱关系"逆推到 `source`（`prev[source] = None`），所以：

* `path[0] = source`
* `path[-1] = target`
* 路径连续（每一对相邻节点 `path[i] → path[i+1]` 都是 `prev[path[i+1]] = path[i]`，对应一条实际存在的边）。

**正确性**已由 Dijkstra 不变量保证。

---

## 七、API 设计

### 7.1 `dijkstra_single_source(graph, source, metric, *, trace=False)`

返回 `source` 到**所有**节点的距离与前驱。

```python
{
    "dist": {"A": 0.0, "B": 1.0, ...},
    "prev": {"A": None, "B": "A", ...},
    "settled": ("A", "B", ...),  # 按被确定顺序
    "relaxed_edges": 5,
    "heap_pops": 4,
}
```

`trace=True` 时返回 `TraceResult`，包含每轮的 `StepRecord`。

### 7.2 `shortest_path(graph, source, target, metric) -> PathResult`

返回两点间最短路径。**早期停止**：当 `target` 弹出时终止。

```python
@dataclass(frozen=True)
class PathResult:
    source: str
    target: str
    metric: str
    path: tuple[str, ...]      # 正向；不可达时为空
    total_weight: float        # 不可达 = +inf
    reachable: bool
    cross_metrics: dict[str, float]  # 同路径在另外两种 metric 下的总权重
```

### 7.3 `compare_metrics(graph, source, target)`

对同一对 (source, target) 跑三种 metric，返回 `{metric: PathResult}`。

### 7.4 异常

| 异常 | 触发 |
| --- | --- |
| `InvalidMetricError` | metric ∉ {"distance", "travel_time", "cost"} |
| `UnknownNodeError` | source 或 target 不在图中 |

---

## 八、教学追踪模式（trace=True）

`StepRecord` 记录每轮关键事件：

```python
@dataclass(frozen=True)
class StepRecord:
    round: int                  # 轮次
    popped_node: str            # 本轮弹出节点
    popped_distance: float      # 弹出时该节点的暂定距离
    settled_snapshot: tuple    # 本轮结束后已确定集合
    relaxations: tuple          # 本轮所有成功松弛的边详情
```

**特点**：

* 默认不产生追踪数据（性能无损）；
* 追踪模式不改变算法计算结果（已被 `test_trace_does_not_change_results` 验证）；
* 追踪数据**结构化存储**，便于未来 Dashboard 动画；
* 不在算法核心循环中散落 print 语句（保持算法代码整洁）。

**演示**：

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 python scripts/demo_dijkstra.py
```

---

## 九、代码索引

| 概念 | 文件 | 行号 |
| --- | --- | --- |
| `dijkstra_single_source` | `src/logiroute/algorithms/dijkstra.py` | 全文主体函数 |
| `shortest_path` | 同上 | 主体函数 |
| `compare_metrics` | 同上 | 主体函数 |
| `StepRecord` / `TraceResult` / `PathResult` | 同上 | `dataclass` 定义 |
| 异常 | 同上 | `DijkstraError` / `InvalidMetricError` / `UnknownNodeError` |
| 单元测试 | `tests/test_dijkstra.py` | 31 用例 |
| 演示脚本 | `scripts/demo_dijkstra.py` | 4 个 demo 段 |
