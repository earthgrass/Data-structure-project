# 索引式二叉最小堆（Indexed Binary Min Heap）—— Phase 2 算法文档

> 本文档是 `src/logiroute/algorithms/heap.py` 的课程教学材料。
> 配套测试：`tests/test_heap.py`（32 个用例）。

---

## 一、为什么 Dijkstra 需要优先队列？

Dijkstra 的核心循环是反复选择"当前暂定距离最小"的未确定节点。
若每次线性扫描所有候选节点（O(V)），则总时间 = O(V² + E)。
**改用优先队列后**，每次取最小只需 O(log V)，总时间 = O((V + E) log V)。

在 V 较大时，二叉堆版 Dijkstra 比无序数组版快一个量级。

| 候选集合实现 | 每次取最小 | 总时间 |
| --- | --- | --- |
| 无序数组（线性扫描） | O(V) | O(V²) |
| **二叉最小堆**（**本项目**） | O(log V) | **O((V + E) log V)** |
| Fibonacci 堆（理论） | O(log V) 摊销 / decrease_key O(1) 摊销 | O(V log V + E) |

本科课程标准实现选择二叉堆——足够展示优先队列的核心思想。

---

## 二、为什么选择二叉最小堆？

* **完全二叉树结构紧凑**，可用数组存储（无需指针）；
* 父子下标公式简单：``parent(i) = (i - 1) // 2``；``left(i) = 2i + 1``；``right(i) = 2i + 2``；
* 数组版缓存友好（连续内存），实际常数小；
* 课程标准实现之一，与教材章节对应；
* 与"排序""完全二叉树""上浮 / 下沉"等概念同章节，可一举多得。

不选 Fibonacci 堆的原因：实现复杂，课程不要求。

---

## 三、完全二叉树为什么能用数组表示？

**定理**：高度为 h 的完全二叉树恰有 2^h - 1 个节点（满树），或介于
2^(h-1) 与 2^h - 1 之间。

**数组表示法的本质**：将树节点按"层序遍历"顺序写入数组：

```
        1
       / \
      2   3
     /\   /\
    4 5  6 7

索引：[1, 2, 3, 4, 5, 6, 7]  (1-based)
```

转为 0-based 后：

```
索引：[0, 1, 2, 3, 4, 5, 6]  (0-based)
```

**父子关系**（0-based）：
* 父节点 ``i``：``(i - 1) // 2``（特例 ``i = 0`` 为根）
* 左孩子 ``2i + 1``
* 右孩子 ``2i + 2``

**为什么用 0-based**：Python `list` 默认 0-based；公式更直接。

---

## 四、上浮（sift_up）

**触发时机**：

* `push(node_id, priority)`：插入末尾后，调用 `sift_up`。
* `decrease_key(node_id, new_priority)`：优先级下降后调用 `sift_up`。

**步骤**：

1. 当前元素在 ``idx``，父节点在 ``(idx - 1) // 2``；
2. 若当前元素优先级更小（或同优先级 node_id 字典序更小），则与父节点交换；
3. 重复直到根节点或满足堆性质。

**复杂度**：O(log V)，最多走树高 h = ⌊log V⌋ 步。

**代码位置**：`src/logiroute/algorithms/heap.py:_sift_up`。

---

## 五、下沉（sift_down）

**触发时机**：`pop_min()`：将末尾元素移到堆顶后调用 `sift_down`。

**步骤**：

1. 当前元素在 ``idx``，左孩子 ``2i + 1``，右孩子 ``2i + 2``；
2. 在 ``idx`` / 左 / 右 三者中找优先级最小者（同时考虑 node_id 字典序）；
3. 若最小者不是 ``idx``，则与最小者交换；
4. 重复直到叶子或满足堆性质。

**复杂度**：O(log V)。

**代码位置**：`src/logiroute/algorithms/heap.py:_sift_down`。

---

## 六、decrease_key 如何实现

**问题**：Dijkstra 过程中可能多次发现某节点 v 的更短路径。需要将 v 在堆中的优先级从旧值更新为更小的新值。

**朴素做法**：删除 v 再插入新条目 → O(log V) + O(log V) = 2O(log V)，**但**会产生重复条目（同一节点在堆中出现多次）。

**索引式堆的做法**：维护 ``_pos: dict[node_id, int]`` 辅助映射，在 O(1) 摊销时间定位到 v 的下标，再做 O(log V) 上浮。

**为何要拒绝"增大"优先级**：Dijkstra 中 `decrease_key` 增大意味着"距离反而变长"——这破坏"Dijkstra 一旦确定不再改变"的不变量。本实现直接抛 `HeapError`，强迫调用方明确处理。

**代码位置**：`src/logiroute/algorithms/heap.py:decrease_key`。

---

## 七、为什么需要位置映射（索引式堆）

无索引堆的 `decrease_key`：

```
不知道 v 在数组中哪个位置 → 必须 O(V) 线性扫描查找 → 然后 O(log V) 上浮
```

索引式堆：

```
_pos[v] -> idx         O(1) avg 找到位置
sift_up(idx)           O(log V) 上浮
```

**总复杂度**：O(log V)（位置查找 O(1) + 上浮 O(log V)）。

**代价**：插入 / 删除时需维护 ``_pos``（O(1) 摊销额外更新），但带来的查询提速远大于维护成本。

---

## 八、每个操作的复杂度

| 操作 | 平均时间 | 最坏时间 | 辅助空间 |
| --- | --- | --- | --- |
| `push(node, prio)` | O(log V) 摊销 | O(log V) | O(1) |
| `pop_min()` | O(log V) | O(log V) | O(1) |
| `peek_min()` | O(1) | O(1) | O(1) |
| `decrease_key(node, prio)` | O(log V) | O(log V) | O(1) |
| `contains(node)` | O(1) avg | O(V) | O(1) |
| `is_empty()` / `size()` | O(1) | O(1) | O(1) |
| `heapify(items)` | O(V) | O(V) | O(V) |
| `validate_heap()` | O(V) | O(V) | O(1) |
| `to_sorted_list()` | O(V log V) | O(V log V) | O(V) |

**辅助总空间**：O(V)（底层 list + _pos 映射）。

---

## 九、与无序数组线性找最小值的对比

| 维度 | 无序数组 | 二叉最小堆 |
| --- | --- | --- |
| 插入 | O(1) | O(log V) |
| 取最小 | **O(V)** 线性扫描 | **O(log V)** |
| 减少优先级 | O(1)（找到再改）| O(log V) |
| 删除最小 | O(V)（移动元素）| O(log V) |
| 总时间（Dijkstra） | O(V²) | **O((V+E) log V)** |

**结论**：V 较大时，堆版快得多；V 较小时常数差异不明显，但堆版的"减少优先级"语义直接对应 Dijkstra 松弛操作，代码更清晰。

---

## 十、小堆实例：每轮数组变化

设输入 `[(A,3), (B,1), (C,4), (D,2), (E,5)]`，依次 push 后每一步的数组状态：

### 步骤 1：push (A, 3)
数组：[(A,3)]
堆（0-based）：
```
A:3
```

### 步骤 2：push (B, 1)
插入末尾：(B,1) 父节点 (A,3) 更大 → 交换
数组：[(B,1), (A,3)]
堆：
```
    B:1
   /
  A:3
```

### 步骤 3：push (C, 4)
插入末尾：(C,4) 父节点 (B,1) 更小 → 不动
数组：[(B,1), (A,3), (C,4)]
堆：
```
    B:1
   / \
 A:3  C:4
```

### 步骤 4：push (D, 2)
插入末尾：(D,2) 父节点 (A,3) 更大 → 交换
数组：[(B,1), (D,2), (C,4), (A,3)]
堆：
```
    B:1
   / \
 D:2  C:4
 /
A:3
```

### 步骤 5：push (E, 5)
插入末尾：(E,5) 父节点 (C,4) 更小 → 不动
数组：[(B,1), (D,2), (C,4), (A,3), (E,5)]
堆：
```
       B:1
      / \
    D:2  C:4
   / \
 A:3  E:5
```

### pop_min → B:1
末尾 E 移到顶：[(E,5), (D,2), (C,4), (A,3)]；sift_down：E 与 D 交换 → [(D,2), (E,5), (C,4), (A,3)]
```
       D:2
      / \
    E:5  C:4
   /
 A:3
```

---

## 十一、代码索引

| 概念 | 文件 | 行号 |
| --- | --- | --- |
| `MinHeap` 类 | `src/logiroute/algorithms/heap.py` | 全文 |
| `push` | 同上 | `def push` 段 |
| `pop_min` | 同上 | `def pop_min` 段 |
| `peek_min` | 同上 | `def peek_min` 段 |
| `decrease_key` | 同上 | `def decrease_key` 段 |
| `heapify` | 同上 | `def heapify` 段 |
| `_sift_up` | 同上 | `def _sift_up` 段 |
| `_sift_down` | 同上 | `def _sift_down` 段 |
| `_less_or_equal`（tie-break） | 同上 | `def _less_or_equal` 段 |
| `__slots__` 内存收紧 | 同上 | `__slots__` 行 |
| 异常体系 | 同上 | `HeapError` / `DuplicateNodeError` / `UnknownNodeError` / `InvalidPriorityError` |
| 单元测试 | `tests/test_heap.py` | 32 用例 |
