# AGENTS.md — 协作约束（强约束）

> 本文件为 Claude Code / Codex / Cursor 等 AI 编程助手提供**强协作约束**。
> 所有贡献者（人 / AI）在本项目下工作时，均须遵守以下规则。

## 1. 项目基线

* **课程**：数据结构课程设计 —— 《电商物流配送路径规划系统》
* **仓库名**：Data-structure-project（中文工作目录：`数据结构课设`）
* **Python 版本**：≥ 3.11
* **测试框架**：`unittest`（标准库，**禁止**改回 pytest）
* **包管理**：`src/` 布局，配置走 `pyproject.toml`
* **当前阶段**：Phase 1 ✅ **已完成**

## 2. 强约束 —— 教师要求

> **「所有核心数据结构与算法必须自主实现，不允许调用现成的算法包。」**

### 2.1 严禁引入的库

| 类别 | 严禁 |
| --- | --- |
| 图算法 | NetworkX、graph-tool、python-igraph、NetworKit、OR-Tools |
| 数值 / 矩阵 | NumPy、SciPy、pandas、Cython |
| 路径 / 规划 | OR-Tools、PuLP、Gurobi / CPLEX 接口 |
| 优化求解 | scipy.optimize、cvxpy、pulp |
| 排序 / 堆（算法核心） | `heapq`、`sorted()`、`functools.cmp_to_key` 等用现成排序代替课程要求排序实现的情形 |
| 测试框架 | pytest、nose2 等第三方框架（统一用 `unittest`） |
| 数据可视化 / Web | matplotlib、plotly、dash、fastapi、flask、uvicorn（**直到** 对应阶段授权） |

### 2.2 完全允许的库（仅作为非算法核心工具）

| 库 / 模块 | 用途 |
| --- | --- |
| `dataclasses`、`enum`、`typing` | 数据模型 |
| `json`、`pathlib` | 配置文件解析（**不**属于算法核心） |
| `math`（标量函数）、`collections.deque` | 通用工具；不得用作算法替代实现 |
| `unittest` | 测试运行 |

> 当不确定是否算「算法核心」时，按「更严的标准」对待：能不复用就不复用。

## 3. 模块边界

### 3.1 Phase 1 阶段严禁

* **不**实现 Dijkstra / A* / BFS / DFS / Floyd / Bellman-Ford 等任何路径算法；
* **不**实现 TSP / VRP / 2-opt / 综合目标求解器；
* **不**实现随机路网生成器（设计已在 docs，**实现**推迟到 Phase 5+）；
* **不**引入 FastAPI / Web 框架 / 数据库；
* **不**为「未来扩展」而引入复杂的抽象模式。

### 3.2 数据模型层（`logiroute.core`）

* **不**依赖任何 Web / 业务 / 算法库；
* **不**与图算法或调度模块形成反向依赖；
* 数据校验失败一律抛 ``ValueError``，不静默吞错；
* ``Node`` 必须保持 frozen dataclass 不变性。

### 3.3 图结构层（`logiroute.graph`）

* 邻接表是**唯一**可变状态；邻接矩阵为按需导出视图，不重复维护；
* ``add_edge`` 拒绝重复边（无多边支持），重复抛 ``DuplicateEdgeError``；
* ``remove_node`` 原子化清理双向邻接索引；``validate()`` 用于自检；
* ``Edge`` 自环必须在构造时被拒绝。

### 3.4 配置层（`logiroute.config`）

* 所有场景参数（网络 / 车辆 / 配送员 / 订单 / 仿真 / 优化权重）**必须在** JSON 中配置；
* Python 源码**不**应出现硬编码「节点数 / 边数 / 默认 ID / 默认容量」等值；
* 加载器必须做完整的引用 + 数值 + 连通性校验；
* Phase 1 仅支持 ``mode="fixed"``；随机生成推迟到 Phase 5+。

### 3.5 后续阶段前置约束

* 任何路径 / 优化算法的实现都必须以**手写堆 / 手写排序 / 手写 BFS/DFS** 为基础；
* 算法模块应提供：伪代码 + 复杂度分析 + 单元测试；
* 算法实现不得放在 `graph` 模块内；只能放在 `algorithms/` 子包。

### 3.6 课程原始约束 —— 单车辆配送（覆盖性条款）

> 教师原始题目要求：**实现单车辆基础路径规划 —— 从仓库出发，遍历所有待配送点后返回仓库。**
>
> 历史多车辆调度方案作废；本条款覆盖任何后续 Phase（含配送调度、随机场景、Dashboard、动态重规划）。

* 调度器**只允许**调度**一辆车**参与实际配送；配置中其余车辆仅作为模型保留，不参与规划。
* 配送车辆必须从选定的出发仓库出发，按调度算法访问**所有**待配送订单目的地，最终返回该出发仓库 —— **必须形成闭合回路**。
* **不**实现多车辆订单分配 / 车队优化 / 多车 VRP / 跨车交换；不允许"为了提升指标"而拆单或加车。
* 配送点之间的实际道路路径**必须**复用 Phase 2 的 Dijkstra；**不**得重写第二套最短路径算法。
* 主要优化目标：**最短距离** 与 **最低运输成本**；**最短时间** 仅作为附加对比策略。
* 业务硬约束：车辆容量、订单时间窗口（含 `service_time`）、超时记录与不可行原因明确化。
* 若在单次装货或时间约束下确实无法服务全部订单，调度器必须**如实报告未服务订单及原因**，**不**得伪造 100% 完成率。
* 固定场景最低规模基线：≥ 2 仓库、≥ 15 配送点、≥ 3 中转站、≥ 30 节点、≥ 50 有向边；少于该基线的场景配置加载器必须拒绝。
* 后续随机场景生成器、Dashboard 与动态重规划模块同样必须遵守单车辆约束；"随机生成 ≠ 随机增加车辆"。
* 任何违反上述条款的方案（含历史多车辆草案）**一律作废**。

### 3.7 Phase 3 算法策略（当前授权范围内）

* **自主实现**：
  * 最近邻（Nearest-Neighbor）基线构造；
  * 可行插入（Cheapest Feasible Insertion）调度；
  * 受约束 2-opt 局部搜索（仅在已有可行路线上做单车内配送顺序改进）。
* **策略开关**：每个调度实例仅指定一个主目标（`distance` / `cost`），`travel_time` 仅作为对比列。
* **路径来源**：所有相邻配送站点之间的有向最短路径必须调用 Phase 2 的 `dijkstra.shortest_path` / `single_source`；调度器持有**单次调度作用域内的路径缓存**（键：`(graph_version, source, target, metric)`），调度结束自动丢弃，避免跨场景串味。
* **同一份 Dijkstra**：禁止为调度再写一套最短路径子例程。

## 4. 编码风格

* 全部公开接口（类、方法、属性）必须带类型注解；
* 使用 `from __future__ import annotations` 保持前向引用整洁；
* 异常命名 ``XxxError``，继承自业务基类（图层）或直接 ``ValueError``（数据层）；
* 关键方法必须给出 **Time / Space 复杂度注解**（docstring 形式）；
* 不要发明无意义的设计模式 / 抽象；优先实现清晰、可读的最小方案；
* 私有字段统一加下划线前缀，并通过 ``__slots__`` 收紧图结构内存。

## 5. 测试约定

* **必须**使用 `unittest`，测试文件命名 `tests/test_<module>.py`；
* 不引入第三方测试框架；
* 复杂 fixture 用 `setUp` / `tearDown` 或工厂函数手动管理；
* 测试失败时禁止 push；先修复再考虑提交；
* 关键场景测试（连通性、最小节点 / 边数）放在专门的形状测试文件下。

## 6. Git 协作规则

1. 修改前先 `git status` 与确认分支。
2. 一个逻辑改动 = 一次提交，使用 Conventional Commits，例如：
   * `feat(config): add strongly-connected connectivity check`
   * `fix(graph): remove node clears in/out edges atomically`
   * `docs: refresh hand-rolled algorithm constraints in AGENTS.md`
3. **未授权禁止**：`force push`、`reset --hard`、删除他人分支、覆盖其他提交。
4. 远程仓库：`https://github.com/earthgrass/Data-structure-project.git`，认证信息已在本地配置。
5. 不要在仓库中保存密钥、token、个人隐私数据。

## 7. 文档约定

* 项目入口：`README.md`
* 架构文档：`docs/architecture.md`
* 阶段规划：`docs/development-plan.md`
* 协作约束：`AGENTS.md`（本文）
* 新增主题放入 `docs/` 子目录并保留 README 导航。

## 8. 与用户的协作预期

* 完成每一阶段后立即停止，等待审查；
* 最终交付：目录树、对象职责、数据结构设计理由、测试结果、commit hash；
* 不承诺尚未完成的工作；
* 任何超出当前阶段的功能请求，先与用户确认再实施。

## 9. AGENTS 行为准则

* 始终在已授权的 Phase 范围内活动；
* 修改现有文件前**先 Read** 再 Edit / Write；
* 重大重构前先与用户对齐方案；
* 拒绝编造 GitHub 地址、commit 历史或 push 状态；
* **拒绝**为节省工作量而偷偷引入 `heapq` / `sorted` / `numpy` 等已禁用的工具。
