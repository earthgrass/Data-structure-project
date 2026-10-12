# LogiRoute 后续开发阶段规划

> 本文件描述从 Phase 2 起将逐步引入的功能。每阶段的边界清晰、可单独交付，
> 与 Phase 1（已交付，✅）和当前阶段状态共同记录在档。

## 状态总览

| Phase | 名称                                          | 状态                |
| ----- | --------------------------------------------- | ------------------- |
| 1     | 工程初始化与核心数据结构                       | ✅ 已完成（当前快照） |
| 2     | 最短距离路径规划（Dijkstra 等）                | ⏳ 待启动            |
| 3     | 多目标综合优化与最低成本路径                    | ⏳ 待启动            |
| 4     | 配送顺序优化与时间窗口约束                      | ⏳ 待启动            |
| 5     | 动态订单插入、交通拥堵与重规划                  | ⏳ 待启动            |
| 6     | FastAPI 后端 API                                | ⏳ 待启动            |
| 7     | React + TypeScript 前端 Dashboard             | ⏳ 待启动            |

> **范围限制**：在收到对应 Phase 的明确指令前，**不得提前实现**任何阶段。
> 每次只针对当前开启的 Phase 进行开发、测试与提交。

---

## Phase 2 — 最短距离路径规划（Dijkstra）

**目标**：基于 ``LogisticsGraph`` 实现 Dijkstra 单源最短路径，并暴露按距离、时间、
成本三种度量的查询接口。

**主要工作项**

1. 在 ``logiroute.algorithms`` 下新增：
   * ``shortest_path(graph, source, target, metric)``
   * ``single_source_shortest_paths(graph, source, metric)``
   * 内部使用最小堆（``heapq``）保证 O((V+E) log V) 复杂度。
2. 在测试中补充正向图、反向图、不连通子图、自环拒绝等用例。
3. 在 ``docs/`` 增加 ``algorithms-dijkstra.md`` 算法说明。

**交付物**

* 新算法模块 + 单元测试覆盖
* 现有数据模型与图结构保持向后兼容
* README 状态表更新至 Phase 2 ✅

## Phase 3 — 多目标综合优化与最低成本路径

**目标**：在 Phase 2 之上加入 cost 度量，支持线性加权综合目标（α·距离+β·时间+γ·成本），
并允许调用方动态指定权重。

**主要工作项**

1. ``algorithms`` 增加 ``weighted_multi_objective_path``，参数 ``weights: dict[metric, float]``。
2. 对边界情况：负权边（不允许）、度量不可比、权重为 0 的情形做单元测试。
3. 提供一个简单的 Demo 输入（JSON）展示三种策略下的路径差异。

## Phase 4 — 配送顺序优化与时间窗口约束

**目标**：实现多客户点路径拼接（TSP / VRP），结合 ``Order.time_window`` 做软硬约束评估。

**主要工作项**

1. ``dispatch`` 模块新增 ``TourPlanner``，基于最近邻 / 2-opt 构造基础解。
2. 时间窗口约束：超出 ``time_window_end`` 视为 ``EXPIRED``，写回 ``Order.status``。
3. 性能目标：30 节点 / 50 边内可在 1 秒内出解。

## Phase 5 — 动态订单插入与重规划

**目标**：模拟实时订单插入、节点 / 边删除与交通拥堵对路径的影响。

**主要工作项**

1. 新增 ``GraphEvent`` 总线：``node_added`` / ``edge_removed`` / ``traffic_changed``。
2. 增量式 Dijkstra / 局部重规划，仅重算受影响子图。
3. 单元测试覆盖事件分发、订阅者注销、批量事件去重。

## Phase 6 — FastAPI 后端

**目标**：将核心模型与算法暴露为 RESTful API。

**主要工作项**

1. 在 ``logiroute.api`` 下搭建 FastAPI 应用，注册路由：
   * ``POST /graphs/nodes`` / ``DELETE /graphs/nodes/{id}``
   * ``POST /graphs/edges``
   * ``GET /graphs/{graph_id}/path?source=&target=&metric=``
2. Pydantic 与 ``core`` 模型解耦：通过 ``serializers`` 模块转换。
3. 容器化友好：暴露 ``logiroute.api.app:app`` 作为 ASGI 入口。

## Phase 7 — React + TypeScript 前端 Dashboard

**目标**：可视化配送网络、订单状态、路径与动态变化。

**主要工作项**

1. 独立前端工程目录（例如 ``frontend/``），与 Python 项目分离；
2. 选型 React 18 + TypeScript + Vite；可视化库如 vis-network 或 deck.gl；
3. 与 FastAPI 服务对接，提供上传网络 JSON、运行规划、查看路径动画等能力。

---

## 通用执行规范（持续适用）

* 任何 Phase 启动前，确认上一阶段全部测试通过；
* 严格使用 Conventional Commits 风格，例如：
  * `feat(algorithms): add dijkstra single-source shortest path`
  * `fix(graph): properly clear reverse edges on node removal`
* 提交前必须先跑 `pytest`；任何 red test 禁止 push；
* 与 GitHub 远程仓库的所有 push 操作必须基于当前授权范围；
* 若需要 force push / `reset --hard` / 删除远端分支，必须先取得用户授权。
