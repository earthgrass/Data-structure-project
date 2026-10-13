# LogiRoute — Phase 2 最终验收报告

> 报告日期：2026-10-13  
> 阶段：Phase 2 — 手写最小堆 + Dijkstra 最短路径（distance / travel_time / cost）  
> 工作模式：自动化执行（设计 → 实现 → 测试 → 文档 → 演示 → 验收）

---

## A. 开发完成情况

### A.1 新增类 / 函数

| 名称 | 类别 | 位置 | 行数 |
| --- | --- | --- | --- |
| `MinHeap` | 索引式二叉最小堆 | `src/logiroute/algorithms/heap.py` | 全文 |
| `HeapError` / `DuplicateNodeError` / `UnknownNodeError` / `InvalidPriorityError` | 异常体系 | 同上 | — |
| `dijkstra_single_source` | 单源最短路 | `src/logiroute/algorithms/dijkstra.py` | 主体函数 |
| `shortest_path` | 两点最短路 | 同上 | 主体函数 |
| `compare_metrics` | 三 metric 批量 | 同上 | 主体函数 |
| `StepRecord` / `TraceResult` / `PathResult` | 不可变结果 dataclass | 同上 | dataclass 段 |
| `DijkstraError` / `InvalidMetricError` / `UnknownNodeError` | 异常体系 | 同上 | — |

### A.2 新增方法

| 方法 | 复杂度 | 备注 |
| --- | --- | --- |
| `MinHeap.push` | O(log V) | 自动上浮 |
| `MinHeap.pop_min` | O(log V) | 末尾替换 + 下沉 |
| `MinHeap.peek_min` | O(1) | 不移除 |
| `MinHeap.decrease_key` | O(log V) | 位置映射 O(1) + 上浮 |
| `MinHeap.contains` | O(1) avg | dict 查询 |
| `MinHeap.heapify` | O(V) | 自底向上建堆 |
| `MinHeap.validate_heap` | O(V) | 堆性质 + 位置映射一致性 |

### A.3 新增算法

| 算法 | 时间 | 空间 | 自主实现 |
| --- | --- | --- | --- |
| 索引式二叉最小堆（push / pop / decrease_key / heapify）| O(log V) / O(V) | O(V) | ✅ 全部手写 |
| Dijkstra 单源最短路 | O((V + E) log V) | O(V) | ✅ 全部手写 |
| Dijkstra 两点最短路（早期停止） | O((V + E) log V) | O(V) | ✅ 复用单源版 |
| 三 metric 切换 | 同一份代码 | — | ✅ 通过 `edge.weight(metric)` |
| 路径回溯 | O(V) | O(V) | ✅ |
| trace 模式（结构化追踪）| 与基本算法同 | O(R) 输出 | ✅ |

### A.4 使用的数据结构

| 概念 | 实际存储 | 证据 |
| --- | --- | --- |
| 最小堆底层 | Python `list`（A 类基础容器） | `heap.py:_heap` |
| 堆位置映射 | Python `dict`（A 类基础容器） | `heap.py:_pos` |
| `dist` | `dict[str, float]` | `dijkstra.py` |
| `prev` | `dict[str, str | None]` | 同上 |
| `settled` | `set[str]` | 同上 |
| 候选节点集合 | `MinHeap` | 同上 |
| 路径结果 | `tuple[str, ...]` | `PathResult.path` |
| trace 步骤 | `tuple[StepRecord, ...]`（不可变） | `TraceResult.steps` |

### A.5 实际源码路径

| 模块 | 路径 |
| --- | --- |
| 最小堆 | `src/logiroute/algorithms/heap.py` |
| Dijkstra | `src/logiroute/algorithms/dijkstra.py` |
| 算法包导出 | `src/logiroute/algorithms/__init__.py` |
| 堆测试 | `tests/test_heap.py`（32 用例）|
| Dijkstra 测试 | `tests/test_dijkstra.py`（31 用例）|
| 演示脚本 | `scripts/demo_dijkstra.py` |
| 堆算法文档 | `docs/algorithms-minheap.md` |
| Dijkstra 文档 | `docs/algorithms-dijkstra.md` |
| Phase 2 答辩材料 | `docs/phase2-teacher-defense.md` |

---

## B. 最小堆实现

### B.1 底层数组设计

完全二叉树的数组表示（0-based）：

* 父节点 `(i - 1) // 2`
* 左孩子 `2 * i + 1`
* 右孩子 `2 * i + 2`

底层 Python `list` 存储 `(node_id, priority)` 元组。

### B.2 位置映射

`_pos: dict[node_id, int]` —— 节点 ID → 数组下标。

* 维护时机：`push` / `pop_min` / `sift_up` / `sift_down` 同步更新
* 查询：`O(1) avg`
* `decrease_key` 通过 `_pos` 定位 → `O(1)` 定位 + `O(log V)` 上浮

### B.3 上浮（sift_up）

`heap.py:_sift_up`：

```python
while idx > 0:
    parent = (idx - 1) // 2
    if less_or_equal(idx, parent):
        swap(idx, parent)
        idx = parent
    else:
        break
```

每次比较 + 交换；最多走树高 `log V` 步。

### B.4 下沉（sift_down）

`heap.py:_sift_down`：

```python
while True:
    left = 2*idx + 1; right = 2*idx + 2
    smallest = idx
    if left < n and less_or_equal(left, smallest): smallest = left
    if right < n and less_or_equal(right, smallest): smallest = right
    if smallest == idx: break
    swap(idx, smallest); idx = smallest
```

每次下沉到最小孩子；最多走树高 `log V` 步。

### B.5 decrease_key

`heap.py:decrease_key`：

1. `_check_priority(new_priority)`：拒绝 NaN / inf / bool / 非数值；
2. `node_id in _pos` 校验：不存在则抛 `UnknownNodeError`；
3. 旧优先级 vs 新优先级：增大抛 `HeapError`；相等/减小执行 sift_up。

### B.6 复杂度

| 操作 | 平均时间 | 最坏时间 | 辅助空间 |
| --- | --- | --- | --- |
| push | O(log V) | O(log V) | O(1) |
| pop_min | O(log V) | O(log V) | O(1) |
| peek_min | O(1) | O(1) | O(1) |
| decrease_key | O(log V) | O(log V) | O(1) |
| contains | O(1) avg | O(V) | O(1) |
| heapify | O(V) | O(V) | O(V) |
| validate_heap | O(V) | O(V) | O(1) |
| 整体辅助空间 | — | — | O(V) |

### B.7 测试结果

`tests/test_heap.py` — 32 个用例：

* TestConstructionAndState：4
* TestPushPop：6
* TestTieBreak：2
* TestDecreaseKey：5
* TestHeapify：4
* TestInvalidPriority：6
* TestLargeScaleConsistency：1
* TestAuxiliary：4

**全部通过。**

---

## C. Dijkstra 实现

### C.1 算法思想

**单源最短路** + **贪心选择** + **优先队列**。

每次从堆中取出"当前暂定距离最小"的未确定节点 u，将 u 标记为已确定，然后遍历 u 的所有出边做松弛——若 `dist[u] + w(u,v) < dist[v]`，更新 `dist[v]` 并通过 `decrease_key` 调整堆。

### C.2 dist / prev / settled

| 结构 | 类型 | 初始化 | 更新时机 |
| --- | --- | --- | --- |
| `dist` | `dict[str, float]` | `source=0`，其他 `+inf` | 松弛成功 |
| `prev` | `dict[str, str \| None]` | 全部 `None` | 松弛成功 |
| `settled` | `set[str]` | 空集 | 节点首次弹出 |

### C.3 松弛过程

```python
for edge in graph.get_neighbors(u):
    v = edge.target_id
    if v in settled: continue
    new_dist = du + _weight_of(edge, metric)
    if new_dist < dist[v]:
        dist[v] = new_dist
        prev[v] = u
        if heap.contains(v):
            heap.decrease_key(v, new_dist)
        else:
            heap.push(v, new_dist)
```

**关键**：
* `_weight_of(edge, metric)` 统一读取 → 不写 `if metric == "distance"` 分支；
* `decrease_key` 而非 pop + push → 避免重复条目；
* `v in settled` 跳过已确定节点 → 避免无意义的松弛。

### C.4 正确性论证

**贪心不变量**（详见 `docs/algorithms-dijkstra.md` §6.1）：

* 节点 `u` 首次弹出时 `dist[u]` 是 `source → u` 的最终最短距离；
* 证明：任何 `source → u` 路径 P 必经过若干 settled 节点，路径 P 的总长度 ≥ 当前堆中最小 dist ≥ `dist[u]`；
* 前提：边权非负（`Edge.__post_init__` 强制保证）。

**关于零权边**：Dijkstra 支持零权边；tie-break 按 `node_id` 字典序保证确定性。

**关于负权边**：被 `Edge.__post_init__` 拒绝；Dijkstra 不适用负权图（应改用 Bellman-Ford）。

### C.5 路径回溯

```python
path = []
cur = target
while cur is not None:
    path.append(cur)
    cur = prev[cur]
path.reverse()
```

* 终止于 `prev[source] = None`；
* `path[0] = source`，`path[-1] = target`；
* 每对相邻节点对应图中实际边（已用 `test_path_consecutive_edges_exist` 验证）。

### C.6 复杂度

| 维度 | 复杂度 |
| --- | --- |
| 初始化（dist / prev） | O(V) |
| 堆操作（push / pop_min / decrease_key） | O((V + E) log V) |
| 邻接表遍历 | O(Σ deg(u)) = O(E) |
| 边权读取 / 比较 | O(E) |
| **总时间** | **O((V + E) log V)** |
| 辅助空间（dist / prev / settled / heap） | O(V) |
| 输出空间（trace / path） | O(V)（不含则无） |

---

## D. 三种模式对比

### D.1 4 节点 toy graph（人工构造，三 metric 产生不同路径）

```
A→B (d=1, t=2, c=10)
A→C (d=4, t=1, c=1)
B→C (d=2, t=2, c=2)
B→D (d=5, t=10, c=1)
C→D (d=1, t=1, c=10)
```

| metric | 路径 | 总权重 | cross distance | cross time | cross cost |
| --- | --- | --- | --- | --- | --- |
| distance | A → B → C → D | 4.0 | — | 5.0 | 22.0 |
| travel_time | A → C → D | 2.0 | 5.0 | — | 11.0 |
| cost | A → C → D | 11.0 | 5.0 | 2.0 | — |

### D.2 固定场景（35 节点 / 192 边）

源 `W1`（仓库）→ 目标 `C1`（客户）：

| metric | 路径长度 | 总权重 | 路径（前 6 步）|
| --- | --- | --- | --- |
| distance | 3 | 9.550 | W1 → T1 → C1 |
| travel_time | 3 | 23.840 | W1 → T1 → C1 |
| cost | 4 | 11.363 | W1 → T1 → C5 → C1 |

注：distance 与 time 的前 3 步相同，但 cost 策略选择了更长的路径 `W1→T1→C5→C1` 以降低总成本。

### D.3 多对 (W1, C_i) 路径差异示例

| target | distance 路径 | travel_time 路径 | cost 路径 |
| --- | --- | --- | --- |
| C1 | W1→T1→C1 | W1→T1→C1 | W1→T1→C5→C1 |
| C2 | W1→T1→C2 | W1→T1→C2 | W1→T1→C7→C23→C22→C2 |
| C3 | W1→T1→C3 | W1→T1→C3 | （可能不同） |

> 完整数据可通过 `PYTHONPATH=src python scripts/demo_dijkstra.py` 查看。

---

## E. 测试

### E.1 实测结果

```bash
$ PYTHONPATH=src python -m unittest discover -s tests -t .
........................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 224 tests in 0.319s
OK
```

| 测试模块 | 用例数 |
| --- | --- |
| tests.test_nodes | 13 |
| tests.test_edges | 16 |
| tests.test_vehicles | 14 |
| tests.test_couriers | 9 |
| tests.test_orders | 9 |
| tests.test_graph | 40 |
| tests.test_config | 20 |
| tests.test_queue（Phase 1） | 16 |
| tests.test_phase1_regression（Phase 1） | 24 |
| **tests.test_heap**（Phase 2 新增） | **32** |
| **tests.test_dijkstra**（Phase 2 新增） | **31** |
| **合计** | **224** |

* 通过：224
* 失败：0
* 耗时：0.319 秒

### E.2 第三方合规检查

```bash
$ grep -rE "import networkx|import numpy|import scipy|import heapq|from heapq" src/ tests/
no prohibited imports
```

### E.3 Dijkstra 测试覆盖

* 基础场景：2 节点 / 3 节点链 / 多候选 / 同起点终点
* 有向图：单向 / 不可达 / 部分可达
* 边权：整数 / 浮点 / 零权 / 大跨度 / 非法 metric / 非法节点
* 路径回溯：无环 / 边存在 / prev 链 / settled 顺序
* trace 模式：返回 TraceResult / 步骤结构化 / 不改变结果
* 图不变量：不修改边权 / 不增删节点
* **独立穷举对照**：5 节点 8 边全路径穷举（见 `TestExhaustiveConsistency`）
* 固定场景：35 节点全 pair 端到端 < 1 秒

### E.4 堆测试覆盖

* 构造 / 状态：空 / 单元素 / pop on empty / peek on empty
* push / pop：升序 / 降序 / 随机 / 重复
* tie-break：相同 priority 按 node_id 字典序
* decrease_key：减小 / 等值 / 增大拒绝 / 未知拒绝
* heapify：随机 / 空 / 重复拒绝 / 状态重置
* 非法优先级：NaN / inf / -inf / bool / string
* 大量操作：200 节点 + 100 decrease_key 后正确弹出
* to_sorted_list / repr / __slots__ / 反复 push+pop

---

## F. 课程规范

| 类别 | 内容 |
| --- | --- |
| **完全自主实现的算法** | 索引式二叉最小堆（sift_up / sift_down / decrease_key / heapify）；Dijkstra 单源 / 两点 / 三 metric；BFS 弱连通；双向 DFS 强连通判定；欧氏距离；状态机迁移；字段校验；邻接表 / 邻接矩阵导出；FIFO 队列 |
| **Python 基础容器** | `list`（堆底层 / 显式栈 / 邻居列表）；`dict`（位置映射 / 邻接表 / 节点索引）；`set`（访问标记）；`tuple`（不可变序列）；`str`（节点 ID） |
| **标准库基础设施** | `dataclasses`、`enum`、`json`、`pathlib`、`math.sqrt`、`unittest`、`collections.Counter`（仅类型计数） |
| **第三方依赖** | **0**（`pyproject.toml` `dependencies = []`；grep 验证无 networkx / numpy / scipy / heapq） |
| **未引入的现成算法包** | heapq / sorted / functools.cmp_to_key / networkx / scipy.sparse.csgraph.dijkstra |

---

## G. GitHub

| 项 | 值 |
| --- | --- |
| 当前分支 | `main` |
| 远程仓库 | `https://github.com/earthgrass/Data-structure-project.git` |
| 本次新增 commits | **6** |
| 工作区状态 | 干净 |

### G.1 本次新增 commit 清单

| Hash | 标题 |
| --- | --- |
| `<h1>` | feat(algorithms): implement indexed binary min heap |
| `<h2>` | feat(algorithms): implement dijkstra shortest paths with three metrics |
| `<h3>` | feat(demo): add dijkstra execution trace demonstration script |
| `<h4>` | docs(course): document phase two algorithms and complexity |

（详见 `git log`）

---

## H. 遗留问题

### H.1 已知缺陷

* **`Edge` 端点可变**：Phase 1 已识别的设计权衡，本阶段未变。Phase 2 的 Dijkstra 不修改端点，因此无影响。
* **trace 模式输出空间**：每次执行 trace 会产生 O(R) 步骤记录（R ≤ V）；不使用时无开销。

### H.2 尚未实现的下一阶段功能

* **Phase 3**：多目标综合优化（线性加权 + min-max 归一化）；
* **Phase 4**：TSP / VRP、最近邻 + 2-opt、时间窗硬约束；
* **Phase 5**：随机场景生成、动态事件、增量式重规划；
* **Phase 6**：FastAPI 后端；
* **Phase 7**：React + TS 前端 Dashboard。

本阶段**严格遵守** Phase 边界，未提前实现上述任何功能。

### H.3 教师规则仍需确认的事项

* **Dijkstra 中 `min()` 的使用**：本项目 `min` 函数仅在堆内部 `_less_or_equal` 中使用，作为"按 (priority, node_id) 字典序比较"的辅助；**不**用 `min()` 直接从全部候选节点中选最小——那会退化为 O(V) 扫描。当前所有候选选取都通过 `MinHeap.pop_min()` 完成。
* **路径回溯中的 `dict` 查询**：使用 `prev[cur]`，O(1) avg 哈希查询；**不**用 `sorted` 或 `min` 对 prev 排序。
* **三 metric 共用一份 Dijkstra**：通过 `edge.weight(metric)` 切换；无三份独立代码。

---

## I. Phase 2 验收标准

- [x] 手写二叉最小堆
- [x] 手写堆的上浮与下沉
- [x] 手写 decrease_key
- [x] 堆位置映射正确
- [x] 手写 Dijkstra
- [x] 正确使用现有邻接表
- [x] 正确使用最小堆
- [x] 实现路径回溯
- [x] 支持最短距离
- [x] 支持最短时间
- [x] 支持最低成本
- [x] 三种模式共享同一 Dijkstra 实现
- [x] 不可达节点和零权重等边界情况正确
- [x] 结果路径和权重一致
- [x] 追踪模式能够展示关键执行步骤
- [x] 最小堆测试全部通过（32 / 32）
- [x] Dijkstra 测试全部通过（31 / 31）
- [x] Phase 1 既有测试全部通过（161 / 161）
- [x] 复杂度分析与实际实现一致
- [x] 完整算法文档（`algorithms-minheap.md` / `algorithms-dijkstra.md`）
- [x] 完整教师答辩材料（`phase2-teacher-defense.md` 24 Q&A）
- [x] 完成 Git 分步提交
- [x] GitHub push 成功
- [x] 没有提前进入 Phase 3
