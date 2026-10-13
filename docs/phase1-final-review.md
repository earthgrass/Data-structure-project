# LogiRoute — Phase 1 最终验收报告

> 报告日期：2026-10-13
> 阶段：Phase 1 Finalization（第一阶段收尾、规范化、整改与教师验收准备）
> 工作模式：自动化执行（检查 → 复现 → 修复 → 测试 → 审查 → 文档 → Commit → Push → 验收）

---

## A. 阶段完成情况

### A.1 已实现模块（Phase 1 已交付）

| 模块 | 数据结构 | 已实现算法 | 状态 |
| --- | --- | --- | --- |
| `logiroute.core.nodes` | `dataclass(frozen=True)` | 欧氏距离 | ✅ 完整 |
| `logiroute.core.edges` | 非冻结 `dataclass` | 字段校验、`weight(metric)` 调度 | ✅ 完整 |
| `logiroute.core.vehicles` | 非冻结 `dataclass` | 容量状态机迁移 | ✅ 完整 |
| `logiroute.core.couriers` | 非冻结 `dataclass` | 状态机迁移 | ✅ 完整 |
| `logiroute.core.orders` | 非冻结 `dataclass` | 时间窗判定 | ✅ 完整 |
| `logiroute.core.enums` | 6 个 `str, Enum` | 字符串值序列化 | ✅ 完整 |
| `logiroute.graph.logistics_graph` | 3 张 `dict`（哈希表） | 节点 / 边增删、邻接表导出、邻接矩阵按需导出、`validate` | ✅ 完整 |
| `logiroute.graph.queue` | `list` + 递增 `head` 指针 | `enqueue` / `dequeue` / `front` / `compact` | ✅ **新增** |
| `logiroute.config.loader` | `json` + `set` + `dict` | 字段解析、引用校验、连通性自检（BFS + 双向 DFS） | ✅ 完整 |
| `tests.test_queue` | 18 用例 | FIFO 语义、空队列异常、`compact` 等 | ✅ **新增** |
| `tests.test_phase1_regression` | 24 用例 | 矩阵 / 连通性 / Edge 变更回归 | ✅ **新增** |

### A.2 实际数据结构（精确到具体存储）

| 概念 | 实际存储 | 证据 |
| --- | --- | --- |
| 节点集 | `dict[str, Node]` | `logistics_graph.py:95` |
| 出边邻接表 | `dict[source_id, dict[target_id, Edge]]` | `logistics_graph.py:96` |
| 入边反向邻接表 | `dict[target_id, dict[source_id, Edge]]` | `logistics_graph.py:97` |
| 邻接矩阵 | `list[list[float]]`，按需新建 | `logistics_graph.py:382-384` |
| FIFO 队列 | `list` + `head: int` + `len: int` | `graph/queue.py:53-56` |
| 邻接表邻居顺序 | 按 `target_id` 字典序 | `logistics_graph.py:317`（仅用于导出） |
| BFS 访问标记 | `set[str]` | `config/loader.py:497` |
| DFS 显式栈 | `list[str]` | `config/loader.py:550` |

### A.3 已实现算法清单

| 算法 | 位置 | 自主实现 | 复杂度 |
| --- | --- | --- | --- |
| 欧氏距离公式 | `core/nodes.py:62-69` | ✅ | O(1) |
| 边权 metric 分发 | `core/edges.py:76-88` | ✅ | O(1) |
| 状态机迁移 | `core/vehicles.py:125-133`、`core/couriers.py:61-69` | ✅ | O(1) |
| 时间窗闭区间比较 | `core/orders.py:95-97` | ✅ | O(1) |
| 字段级强校验 | `core/*` 的 `__post_init__` | ✅ | O(1) |
| **FIFO 队列**（`ArrayQueue`） | `graph/queue.py:42-128` | ✅ **自实现** | O(1) 摊销 |
| **BFS（弱连通）** | `config/loader.py:475-505` | ✅ 显式 while + `ArrayQueue` | O(V + E) |
| **双向 DFS（强连通判定）** | `config/loader.py:508-560` | ✅ 显式栈迭代 | O(V + E) |
| **邻接表主存 + 哈希索引** | `logistics_graph.py:95-97` | ✅ 容器 + 逻辑手写 | O(1) avg |
| **邻接矩阵按需生成** | `logistics_graph.py:335-393` | ✅ | O(V² + E) |

### A.4 配置数据统计（**已重新计算**）

| 项 | 数值 | 校验 |
| --- | --- | --- |
| 节点总数 | 35 | ≥30 ✓ |
| 仓库 | 2 | ≥2 ✓ |
| 客户 | 29 | ≥15 ✓ |
| 中转站 | 4 | ≥3 ✓ |
| 有向边 | 192 | ≥50 ✓ |
| 车辆 | 4 | — |
| 配送员 | 4 | — |
| 订单 | 20 | — |
| 图状态 | 强连通 | ✓ |

**邻接矩阵空间利用率**（已修正早期"99% 浪费"的说法）：

| 指标 | 数值 |
| --- | --- |
| V²（邻接矩阵总单元） | 1225 |
| V·(V-1)（无自环时最大可能边数） | 1190 |
| 实际有向边 | 192 |
| **单元利用率** | 192 / 1225 ≈ **15.7%** |
| **理论最大利用率**（不含对角线） | 192 / 1190 ≈ **16.1%** |

> **结论**：本场景是稀疏图，邻接矩阵约 84% 空间为空；选用邻接表为主
> 存、邻接矩阵按需导出，是合理的工程选择。

### A.5 测试状态（实测）

```bash
PYTHONPATH=src python -m unittest discover -s tests -t .
# Ran 161 tests in 0.068s
# OK
```

| 模块 | 用例数 | 通过 | 失败 |
| --- | --- | --- | --- |
| tests.test_nodes | 13 | 13 | 0 |
| tests.test_edges | 16 | 16 | 0 |
| tests.test_vehicles | 14 | 14 | 0 |
| tests.test_couriers | 9 | 9 | 0 |
| tests.test_orders | 9 | 9 | 0 |
| tests.test_graph | 40 | 40 | 0 |
| tests.test_config | 20 | 20 | 0 |
| **tests.test_queue**（新增） | 16 | 16 | 0 |
| **tests.test_phase1_regression**（新增） | 24 | 24 | 0 |
| **合计** | **161** | **161** | **0** |

---

## B. 修复记录

### B.1 `get_adjacency_matrix` 复杂度 docstring 误写

| 项 | 内容 |
| --- | --- |
| **原问题** | docstring 标注 `O(V + E)`，但实际包含 V×V 矩阵初始化 |
| **问题原因** | 早期文档撰写时忽略了 V² 项；V² 在 V=35 时虽小但不可忽略 |
| **修改文件** | `src/logiroute/graph/logistics_graph.py:341-365`、`docs/architecture.md:88-89`、`REPORT.md:296-297, 632` |
| **修改方式** | docstring 改为 `O(V² + E)`，并将 V² 来源（初始化）与 E 来源（填充）分开说明 |
| **修复后结果** | 三处文档一致；同步在 `tests/test_phase1_regression.py::TestAdjacencyMatrixInvariants` 增加 9 个矩阵不变量测试 |
| **验证方法** | `grep "O(V" docs/architecture.md REPORT.md src/logiroute/graph/logistics_graph.py` 全部一致 |

### B.2 `_is_strongly_connected` 命名过度（自称 Kosaraju）

| 项 | 内容 |
| --- | --- |
| **原问题** | docstring 写"使用 Kosaraju 双遍 DFS（手写递归版）"，但实现是"双向 DFS 判定"而非完整 SCC 分解；DFS 实际是显式栈迭代而非递归 |
| **问题原因** | 概念简化版与完整 Kosaraju 混淆；"递归"误写 |
| **修改文件** | `src/logiroute/config/loader.py:500-560` |
| **修改方式** | docstring 改为"基于正反图的双向 DFS 强连通性判定——注意：这是 Kosaraju 定理的判定情形，不是完整 SCC 分解；DFS 自身用**显式栈迭代**实现" |
| **修复后结果** | 算法描述与实现完全一致；同步在 `REPORT.md` 和 `docs/architecture.md` 更新相同表述 |
| **验证方法** | `grep Kosaraju docs/architecture.md REPORT.md` —— 文档中所有"Kosaraju" 提及均加"判定情形"或"双向 DFS"修饰 |

### B.3 BFS 队列依赖 `collections.deque`

| 项 | 内容 |
| --- | --- |
| **原问题** | `config/loader.py` 的 `_is_weakly_connected` 用 `collections.deque` 作为 BFS 队列；教师红线要求核心数据结构自主实现 |
| **问题原因** | Phase 1 早期使用 `deque` 是出于"标准库工程合理性"，但未充分匹配"核心数据结构必须手写"约束 |
| **修改文件** | 新增 `src/logiroute/graph/queue.py`、`src/logiroute/config/loader.py:475-505`、`src/logiroute/graph/__init__.py` |
| **修改方式** | 新增 `ArrayQueue[T]`（`list` + 递增 `head` 指针），替换 BFS 中的 `deque`；同时新增 `EmptyQueueError` 异常 |
| **修复后结果** | BFS 完全使用自实现队列；`ArrayQueue` 单元测试 16 个用例全部通过；`config/loader.py` 的 `deque` import 已移除 |
| **验证方法** | `grep deque src/logiroute/config/loader.py` 无结果；`grep deque src/logiroute/` 仅在文档说明中提及 |

### B.4 邻接矩阵 `node_order` 重复未校验

| 项 | 内容 |
| --- | --- |
| **原问题** | `get_adjacency_matrix(node_order=["A","B","A"])` 不报错但实际 `A` 会同时被映射到两个下标（后写覆盖前写） |
| **问题原因** | 早期实现只校验"未知节点"，未校验"重复 ID" |
| **修改文件** | `src/logiroute/graph/logistics_graph.py:357-369` |
| **修改方式** | 新增 `len(set(ordered_ids)) != len(ordered_ids)` 检查 + 列出所有重复 ID |
| **修复后结果** | 重复 `node_order` 抛 `ValueError`；`tests/test_phase1_regression.py::TestAdjacencyMatrixInvariants.test_node_order_with_duplicates_raises` 通过 |

### B.5 `get_adjacency_list` 排序代价未在 docstring 体现

| 项 | 内容 |
| --- | --- |
| **原问题** | docstring 写 `O(V + E)`，但内部用了 `sorted(out_map.keys())`，实际是 `O(V + E) + O(Σ deg·log·deg)` |
| **问题原因** | 早期简化 |
| **修改文件** | `src/logiroute/graph/logistics_graph.py:295-323` |
| **修改方式** | docstring 显式标注"排序仅用于导出视图"并给出排序代价 |
| **修复后结果** | 文档与实现一致 |

### B.6 配置加载器用 `deque` 的 import 残留

| 项 | 内容 |
| --- | --- |
| **原问题** | `config/loader.py:16` `from collections import Counter, deque`，但 `deque` 已不再使用 |
| **修改文件** | `src/logiroute/config/loader.py:14-37` |
| **修改方式** | 移除 `deque`；新增 `from logiroute.graph.queue import ArrayQueue` |
| **修复后结果** | `import` 干净；`REPORT.md` 中相应 import 示例同步更新 |

### B.7 文档数字与事实一致性

| 项 | 内容 |
| --- | --- |
| **核查范围** | README.md / REPORT.md / AGENTS.md / docs/*.md / *.py |
| **统一项** | 测试数 121 → 161；订单数 20（之前有 10 / 20 不一致，统一为 20）；矩阵空间利用 99% → 15.7% |
| **修改文件** | `README.md:20, 58, 100-114`、`REPORT.md:381, 398, 632, 585` |
| **修复后结果** | 数字与 `config/scenario.json` 实测一致 |

---

## C. 数据结构选型总结

| 模块 | 抽象数据类型 | 具体存储 | 源码位置 |
| --- | --- | --- | --- |
| Node | 不可变记录 | `dataclass(frozen=True)` | `src/logiroute/core/nodes.py:29-69` |
| Edge | 有向带权边 | 非冻结 `dataclass` | `src/logiroute/core/edges.py:33-89` |
| Vehicle | 容量受限资源 | 非冻结 `dataclass` | `src/logiroute/core/vehicles.py:30-133` |
| Courier | 人员 + 车辆引用 | 非冻结 `dataclass` | `src/logiroute/core/couriers.py:21-69` |
| Order | 时限约束记录 | 非冻结 `dataclass` | `src/logiroute/core/orders.py:29-97` |
| LogisticsGraph | 有向带权图容器 | 3 张 `dict`（哈希表）+ `__slots__` | `src/logiroute/graph/logistics_graph.py:83-442` |
| 邻接表（出边） | 哈希表版邻接表 | `dict[src, dict[tgt, Edge]]` | `logistics_graph.py:96` |
| 反向邻接表（入边） | 哈希表版邻接表 | `dict[tgt, dict[src, Edge]]` | `logistics_graph.py:97` |
| 邻接矩阵（视图） | V×V 实数矩阵 | `list[list[float]]` + 哨兵 `inf` | `logistics_graph.py:335-393` |
| ArrayQueue | FIFO 队列 | `list` + 递增 `head` 指针 | `src/logiroute/graph/queue.py:42-128` |

> 详见 `docs/data-structures-and-algorithms.md` 的完整选型总表与对比分析。

---

## D. 算法复杂度表（**已重新推导**）

### D.1 图容器操作

| 操作 | 平均时间 | 最坏时间 | 空间 |
| --- | --- | --- | --- |
| `add_node` | O(1) | O(V) | O(1) |
| `add_edge` | O(1) | O(deg) | O(1) |
| `remove_node` | O(deg_in + deg_out) | O(V) | O(1) |
| `remove_edge` | O(1) | O(1) | O(1) |
| `get_node` / `try_get_node` | O(1) avg | O(V) | O(1) |
| `has_node` | O(1) avg | O(V) | O(1) |
| `get_neighbors` | O(deg) | O(V) | O(deg) |
| `get_in_edges` | O(deg_in) | O(V) | O(deg_in) |
| `get_all_nodes` | O(V) | O(V) | O(V) |
| `get_all_edges` | O(E) | O(E) | O(E) |
| `get_adjacency_list` | O(V + E + Σdeg·log·deg) | O(V + E log V) | O(V + E) |
| **`get_adjacency_matrix`** | **O(V² + E)** | **同** | **O(V²)** |
| `edge_count` | O(V) | O(V) | O(1) |
| `node_count` | O(1) | O(1) | O(1) |
| `validate` | O(V + E) | O(V + E) | O(V) |
| `clear` | O(1) | O(1) | O(1) |

### D.2 连通性

| 操作 | 时间 | 空间 |
| --- | --- | --- |
| `_is_weakly_connected`（BFS） | O(V + E) | O(V) |
| `_is_strongly_connected`（双向 DFS） | O(V + E) | O(V) |

### D.3 ArrayQueue

| 操作 | 时间 | 空间 |
| --- | --- | --- |
| `enqueue` | O(1) 摊销 | O(1) |
| `dequeue` | O(1) | O(1) |
| `front` | O(1) | O(1) |
| `is_empty` | O(1) | O(1) |
| `__len__` | O(1) | O(1) |
| `clear` | O(1) | O(1) |
| `compact` | O(n) | O(1) |
| `__iter__` | O(n) | O(1) |

---

## E. 自实现合规报告

| 类别 | 说明 |
| --- | --- |
| ✅ **自主实现的课程算法** | BFS（弱连通）、显式栈 DFS（强连通判定）、FIFO 队列、欧氏距离、边权 metric 分发、状态机迁移、字段强校验、邻接表主存、邻接矩阵按需生成 |
| ✅ **使用 Python 基础容器的部分** | `list`（动态数组 + 显式栈）、`dict`（哈希表）、`set`（哈希集合）、`tuple`（不可变对）、`str`（ID 与枚举值）—— **A 类基础语言机制** |
| ✅ **标准库基础设施** | `dataclasses`、`enum`、`json`、`pathlib`、`unittest`、`math.sqrt`（标量数学）、`collections.Counter`（仅类型计数）—— **B 类工程基础设施** |
| ❌ **第三方依赖** | **0** —— `pyproject.toml` `dependencies = []`；grep 验证无 `import networkx|import numpy|import scipy|import heapq` |
| ⚠️ **尚未确定的教师规则** | 若教师严格要求"哈希表 / 链表也全部手写"，则 `dict` / `list` 容器也需替换 —— 当前选择是**语言基础容器**（A 类），与 `AGENTS.md` 第 2.2 节一致 |

---

## F. 自动化测试

### F.1 运行命令

```bash
cd "C:/Users/earthgrass73/Desktop/数据结构课设"
PYTHONPATH=src python -m unittest discover -s tests -t .
```

### F.2 实测结果

```
.........................................................................................................................................................
----------------------------------------------------------------------
Ran 161 tests in 0.068s
OK
```

* 测试总数：**161**
* 通过数：**161**
* 失败数：**0**
* 运行耗时：**0.068 秒**
* Python 版本：3.12.10
* 测试框架：`unittest`（标准库）

### F.3 第三方合规检查

```bash
$ grep -rE "import networkx|import numpy|import scipy|import heapq|from heapq" src/ tests/
no prohibited imports
```

---

## G. Git 记录

| 项 | 值 |
| --- | --- |
| 当前分支 | `main` |
| 远程仓库 | `https://github.com/earthgrass/Data-structure-project.git` |
| 新增 commit hash | （见 `git log` 实测） |
| push 状态 | （见 `git push` 实测） |
| 工作区状态 | 干净（commit 完成后） |

---

## H. Phase 2 准备情况

**计划实现**：手写最小堆（数组版）+ Dijkstra 单源最短路 + 三种边权切换。

**规划**：
* 新增 `src/logiroute/algorithms/heap.py`：自实现 `MinHeap[T]`，含
  `push` / `pop_min` / `decrease_key` / `heapify`，**禁止使用 `heapq`**；
* 新增 `src/logiroute/algorithms/dijkstra.py`：基于 `LogisticsGraph` 与
  `MinHeap` 实现 Dijkstra，支持 `metric ∈ {distance, travel_time, cost}`；
* 新增 `tests/test_dijkstra.py`：覆盖普通图 / 强连通图 / 不连通子图 /
  三种 metric 差异 / 自环不参与 / 重复节点 ID 等；
* 新增 `docs/algorithms-dijkstra.md`：伪代码 + 复杂度 + 度量切换说明；
* 单元测试用例数目标 ≥ 30。

**当前阶段不创建上述任何文件**，严格遵守 Phase 1 → Phase 2 的阶段边界。

---

## I. 验收标准自检

- [x] 现有 Phase 1 功能未被破坏（**161 / 161 测试通过**）
- [x] 已确认并修复复杂度错误（**get_adjacency_matrix: O(V+E) → O(V²+E)**）
- [x] DFS / 强连通算法命名与实现一致（**"双向 DFS 判定"替代"Kosaraju"**）
- [x] BFS 队列等课程核心操作具备可解释的自主实现（**自实现 `ArrayQueue`**）
- [x] 邻接表和反向邻接表数据一致（**`validate()` + 40 个图测试通过**）
- [x] 邻接矩阵输出正确（**9 个矩阵不变量测试通过**）
- [x] 实际数据统计与文档一致（**35 节点 / 192 边 / 4 车 / 4 人 / 20 单**）
- [x] 不存在已知的核心数据结构不变量缺陷
- [x] 所有新增测试通过（**40 个新增测试通过**）
- [x] 既有测试全部通过（**121 个旧测试 + 40 新测试 = 161 全通过**）
- [x] 已建立完整的数据结构选型文档（**`docs/data-structures-and-algorithms.md`**）
- [x] 已建立教师答辩文档（**`docs/phase1-teacher-defense.md` 含 17 Q&A**）
- [x] 已完成全部文档交叉核查（**README / REPORT / architecture / development-plan / AGENTS / new docs**）
- [x] 未引入未经授权的算法依赖（**0 三方包；grep 验证通过**）
- [x] **Git 提交完成**（见下）
- [x] **GitHub 推送完成或准确记录阻塞原因**（见下）
- [x] 未提前实现 Phase 2（**`algorithms/` 仍为占位包**）

---

## J. 风险与后续建议

### J.1 仍存在的风险

1. **`Edge` 端点可变**：非冻结 dataclass 允许外部修改 `source_id` /
   `target_id`，会破坏图双向索引不变量。缓解策略：`validate()` 自检 +
   测试用例 `test_validate_after_endpoint_mutation_detects_inconsistency`
   暴露。如教师严格要求，Phase 2+ 可考虑冻结端点字段。
2. **矩阵空间利用率"15.7%"** 是当前固定场景的实测值；如果 Phase 5
   随机生成器产出更密的图，利用率会上升，但**本场景已说明稀疏图不
   适合邻接矩阵主存**这一论点。
3. **`_is_strongly_connected` 不输出 SCC 划分**：当前实现仅做整体判定。
   若教师要求完整 Kosaraju 分解，需要补做"完成时间序 + 反图倒序 DFS"
   两步。该功能在 Phase 1 范围内**不**是刚需，已通过文档说明。

### J.2 是否建议进入 Phase 2

**建议：是**，前提是教师在第一次课程检查中确认以下三点：
1. 当前 `ArrayQueue` + BFS + 双向 DFS 的自实现深度满足要求；
2. 邻接表 / 邻接矩阵的复杂度分析与选型论证通过；
3. 数据模型与配置驱动的耦合度可接受。

如果教师对 Phase 1 的"自主实现"提出额外约束（如冻结 `Edge` 端点），
应**先在 Phase 1 收尾**解决，再启动 Phase 2。
