# AGENTS.md — 协作约束

> 本文件为 Claude Code、Codex、Cursor 等 AI 编程助手提供统一协作约束。
> 所有人在本项目下工作时，均须遵守以下规则；新增规则请加入本文件并提交。

## 1. 项目基线

* **仓库名**：`LogiRoute`（中文环境仓库名为「数据结构课设」目录）
* **Python 版本**：≥ 3.11
* **测试框架**：pytest ≥ 8
* **包管理**：`src/` 布局，安装 / 运行测试走 `pyproject.toml`
* **当前阶段**：Phase 1 ✅（**已完成**），未经授权请勿推进后续 Phase

## 2. 范围与边界

### 2.1 Phase 1 严禁的内容

* **不**实现 Dijkstra、A*、TSP、VRP 等任何路径算法
* **不**引入综合优化 / 多目标评估
* **不**引入时间窗口评估 / 动态调度
* **不**实现 FastAPI 路由、HTTP 接口
* **不**实现前端 Dashboard、React、TypeScript
* **不**引入数据库、外部图算法库（如 NetworkX 替换自有图结构）

### 2.2 数据模型层（`logiroute.core`）的硬约束

* **不**依赖任何 Web 框架（FastAPI、Flask）或外部业务库
* **不**与图算法或调度模块形成反向依赖
* 数据校验失败一律抛 ``ValueError``，不要静默吞错
* ``Node`` 是 frozen dataclass，不可变性是文档级约束

### 2.3 图结构层（`logiroute.graph`）的硬约束

* 邻接表是唯一可变状态；邻接矩阵为导出视图，不与邻接表重复维护
* ``add_edge`` 拒绝重复边（无多边支持），直到 Phase 5 引入正式说明
* ``remove_node`` 必须同时清理双向邻接索引；``validate()`` 用于自检
* ``Edge`` 自环在构造时被拒绝；图中不应出现自环

## 3. 编码风格

* 全部公开接口（类、方法、属性）必须带类型注解
* 使用 `from __future__ import annotations` 保持前向引用整洁
* 异常命名 ``XxxError``，继承自 ``GraphError``（图层）或直接 ``ValueError``（数据层）
* 不要发明无意义的设计模式与抽象；优先实现清晰、可读的最小方案
* 私有字段统一加下划线前缀，并通过 ``__slots__`` 收紧图结构内存

## 4. 测试约定

* 所有新增行为都必须有对应单元测试覆盖
* 测试文件命名 ``tests/test_<module>.py``
* 复杂 fixture 集中在 ``tests/conftest.py``
* 阶段标签：``@pytest.mark.phase1`` / ``phase2`` ... 区分跨阶段用例
* 测试失败时不要直接 push；先修复后再考虑提交

## 5. Git 协作规则

1. 修改前先 `git status`、确认分支
2. 一个逻辑改动 = 一次提交，使用 Conventional Commits：
   * `feat(core): add order time window validation`
   * `fix(graph): remove node clears in/out edges atomically`
   * `docs: refresh development plan for phase 3`
3. 提交信息保持中文 / 英文皆可，但前缀必须规范
4. **未授权禁止**：`force push`、`reset --hard`、删除他人分支、覆盖其他提交
5. 远程仓库：见 README；不要编造地址
6. 不要在仓库中保存密钥、token、个人隐私数据

## 6. 文档约定

* 项目入口文档：`README.md`
* 架构文档：`docs/architecture.md`
* 阶段规划：`docs/development-plan.md`
* 协作约束：`AGENTS.md`（本文件）
* 新增主题请放入 `docs/` 子目录，并保留 README 中的导航

## 7. 与用户（学习者 / 教师）的协作预期

* 完成每一阶段后立即停止，等待审查
* 给最终交付清单（目录树、对象职责、数据结构设计理由、测试运行结果、commit hash），
  不要承诺尚未完成的工作
* 任何超出当前阶段的功能请求，先与用户确认再实施

## 8. 收到本文件的 AI 助手应当

* 始终在 Phase 1 范围内活动，除非获得明确阶段切换指令
* 修改现有文件前**先 Read**，再 Edit / Write
* 重大重构前先 `EnterPlanMode` 与用户对齐方案
* 拒绝编造 GitHub 地址、commit 历史或 push 状态
