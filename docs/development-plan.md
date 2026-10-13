# LogiRoute 后续开发阶段规划

> 本文件描述从 Phase 2 起的功能路线。每阶段边界清晰、可单独交付。
> 严禁在收到明确阶段切换指令前提前实施。

## 状态总览

| Phase | 名称                                          | 状态       |
| ----- | --------------------------------------------- | ---------- |
| 1     | 工程初始化、配置驱动与核心数据结构             | ✅ 已完成  |
| 2     | 最短距离路径规划（手写 Dijkstra + 手写堆）      | ✅ 已完成  |
| 3     | 多目标综合优化与最低成本路径                    | ⏳ 待启动  |
| 4     | 配送顺序规划、时间窗口硬约束                    | ⏳ 待启动  |
| 5     | 随机场景生成与动态调度                          | ⏳ 待启动  |
| 6     | FastAPI 后端 API                                | ⏳ 待启动  |
| 7     | React + TypeScript 前端 Dashboard             | ⏳ 待启动  |

---

## Phase 2 — 手写 Dijkstra 与自实现堆

**目标**：基于 `LogisticsGraph` 实现单源最短路径算法。**关键：堆必须手写，
不得使用 `heapq`；排序需要时也使用手写排序实现。**

**状态：✅ 已完成（2026-10-13）**

### 主要工作项

1. 自实现最小堆（`MinHeap[T]`）：支持 `push / pop_min / decrease_key / heapify`。
2. 自实现 Dijkstra：
   * 输入：`graph, source_id, target_id, metric='distance'`
   * 输出：`(total_cost, path: list[node_id])`
3. 单源版：`single_source_shortest_paths(...)` 返回 `{target_id -> (cost, path)}`。
4. 测试覆盖：
   * 普通图 / 强连通图 / 不连通子图 / 反向边；
   * 三种 `metric`（distance / travel_time / cost）的差异性；
   * 自环不参与（边构造已拒绝）；
   * 重复节点 ID（模型已拒绝）。

### 交付物

* `src/logiroute/algorithms/heap.py`（手写堆）—— **✅ 已交付**
* `src/logiroute/algorithms/dijkstra.py` —— **✅ 已交付**
* `tests/test_heap.py`（32 用例）—— **✅ 已交付**
* `tests/test_dijkstra.py`（31 用例）—— **✅ 已交付**
* `docs/algorithms-minheap.md` —— **✅ 已交付**
* `docs/algorithms-dijkstra.md` —— **✅ 已交付**
* `docs/phase2-teacher-defense.md` —— **✅ 已交付**
* `scripts/demo_dijkstra.py` —— **✅ 已交付**

## Phase 3 — 多目标综合优化

* 线性加权：`(w_d, w_t, w_c)` 组合距离、时间、成本；
* 极端配置：仅距离 / 仅成本 / 仅时间三种特殊情形；
* 度量不可比时（量纲差异）的归一化策略；
* 多策略路径对比表输出。

## Phase 4 — 配送顺序规划与时间窗口硬约束

* 在 `scheduling/` 下构建简单 TSP / VRP（最近邻 + 2-opt）；
* 时间窗口硬约束：超出 `time_window_end` 视为 `EXPIRED`，并写入 `Order.status`；
* 容量约束：违反车辆容量的解直接拒绝；
* 输出「配送路径 × 时刻表」。

## Phase 5 — 随机场景生成与动态调度

* 按 `docs/architecture.md` 第 2.6 节设计实现随机生成器；
* 周期性路况事件（拥堵 / 阻断 / 修复）；
* 增量式事件回调接口，便于 Dijkstra 重规划订阅；
* 多 seed 对比实验脚本。

## Phase 6 — FastAPI 后端

* 在 `logiroute.api` 下搭建 FastAPI 应用；
* 路由：`/graphs`, `/nodes`, `/edges`, `/orders`, `/vehicles`, `/paths`；
* Pydantic 与 `core` 模型解耦：通过 `serializers` 模块转换；
* 暴露 `app: ASGIApp`。

## Phase 7 — React + TypeScript 前端 Dashboard

* 独立前端工程目录（例 `frontend/`）；
* 选型：React 18 + TypeScript + Vite；可视化库如 vis-network 或 deck.gl；
* 与 FastAPI 服务对接；提供：上传网络 JSON、运行规划、查看路径动画。

---

## 通用执行规范（持续适用）

* 任何 Phase 启动前确认上阶段全部测试通过；
* 严格使用 Conventional Commits；
* 提交前必须先跑 `python -m unittest discover`；任何失败禁止 push；
* 任何超出本阶段范围的功能请求，先与用户对齐再实施；
* 当前阶段结束后立即停止，等待用户审查。
