# 规划解释边界修复（2026-11-17）

本轮基于 `fa3f618`，继续修复影响摘要、拒单解释和订单时间轴。工作分支为 `codex/operations-studio`。不改变规划选择、逐车Decimal载荷、签收完成截止、动态订单状态或失败命令的事务语义。

## 复现与修复

| 问题 | 复现证据 | 修复 |
|---|---|---|
| 无关道路更新误报全部车辆行程变化 | Seed42修改未被路线使用的W1→C6路段，4辆车动作、时刻和指标相同，只有traffic_version变化，原changed均为true | 行程比较忽略证据版本；保留车辆、动作、方向、时刻、清单、批次及全部指标比较 |
| 手动规划失败只显示通用错误 | 实际API在保护货物无法续送时返回422，report内含逐单解释；前端RequestError原来丢弃report | 保留该响应为独立前端失败提案，明确标注未应用，不替换后端计划或物理状态 |
| 首份部分计划及刷新后无法从路线面板查看拒单原因 | 无本地路线对照时changes=null，原面板提前返回，遗漏现有拒单ID和解释 | 拒单概览独立于地图路线对照渲染，覆盖首份计划和刷新场景 |
| 地点名称搜索无结果 | 时间轴显示地点名称，但过滤只匹配地点ID | 用节点名称索引辅助搜索；同址订单逐ID保留，ID和车辆搜索继续适用 |
| 时间轴复选框与文字上下分离 | 全局label的flex-direction:column被新控件继承 | 局部明确横排，保留可点击标签及44px高度，不更改其他表单 |

## 证据与状态边界

- `changed`只描述业务行程变化。**已完成动作的过滤仍使用完整Action身份，包含traffic_version**，防止把另一个路况版本的动作当作已执行。
- 手动422仍然是失败事务。后端原计划、revision、位置、货物、事件、历史诊断以及只读GET结果保持不变；无需新增写入API。
- 前端`rejected_proposal`仅是展示附件，使用真实错误响应绑定`session_id + input_revision + traffic_version`。同版本轮询保留；发起新命令、参数试算、新建场景或收到其他输入版本时清除。
- 失败提案不会成为已应用路线，不产生预计签收或优化成果，也不参与自动出发。刷新页面后该临时HTTP响应不持久化；后端已有的应用／自动受阻解释仍可读取。
- 拒单解释继续只是实际启发式候选证据，不证明全局无解。地点搜索和筛选布局只影响展示。

## 文件与复杂度

- `src/logiroute/dispatch/insights.py`：增加业务行程签名，仅用于影响摘要；线性比较动作数及清单项，沿用原投影复杂度。
- `frontend/src/dispatch/hooks/useDispatchSession.ts`：独立保存失败响应；实际后端快照与计划保持原对象。
- `frontend/src/dispatch/planning-insights.mjs`：响应绑定和失效判定为O(1)，地点索引与逐单过滤为O(V+N)（不计文本长度）。
- `Dashboard.tsx`及`components/PlanningInsights.tsx`、`RouteChanges.tsx`、`OrderTable.tsx`：同一解释来源贯通三个入口。
- `tests/test_dispatch_insights_followup.py`、`tests/test_dispatch_insights_failures_api.py`、`frontend/tests/dispatch-insight-boundaries.mjs`：新增回归，原测试文件及断言不变。

## 验证记录

后端3项影响摘要回归先复现4辆车误报，再验证真实字段变化仍可见及完整完成身份不变。另有2项真实API回归，覆盖首次手动422和自动受阻后的手动重试。32项相关新旧定向测试通过，6.257秒。

前端新增24项断言覆盖首份部分计划真实组件渲染、同址地点名称搜索、失败提案来源和版本失效。先复现首份部分计划缺少解释，再修复；原301项断言保留，合计325项通过。TypeScript检查及Vite生产构建通过，83个模块。

完整回归 **849/849通过**（原844项＋新增5项），失败0、错误0、退出码0；unittest计时251.977秒，外部单调计时254.4593540999922秒。[原始输出](experiments/planning-insights-followup-regression.json)单独保存；仅出现历史单车API弃用警告。

原Python及前端测试文件、依赖清单均未修改。AST扫描未发现禁用库导入，无新增排序调用；7处历史sorted调用所在源文件与fa3f618逐字一致。`git diff --check`通过，另经独立只读复审，无P0/P1阻塞问题。

### 浏览器实际验收

1. 严格Seed42场景中搜索“知新园”，返回O1与原预计签收时刻；检查复选框实际样式为横排，控件16×16px、关联标签高度44px。
2. 新建严格Seed42场景，首份规划前加入`FOLLOWUP_WINDOW`（P27、urgent、1kg、截止0.001分）。实际首份计划接纳24单、未接纳此单，路线面板直接显示失败证据；刷新页面丢失本地路线对照后，拒单概览及详情仍存在。
3. 在该隔离会话封闭原路线没有使用的`W1→R1808717125`，实际快照revision5中的4辆车changed均为false，距离、成本、行驶时间差额均为0。
4. 再封闭`W1→R1808717400`后自动续程受阻，点击“重试规划”。界面显示绑定campus1输入v6的“失败提案，未应用”，O12详情指出干线`W1→T_CENTER`不可达，并列出实际阻塞清单。原应用计划和物理记录保留。
5. 恢复两条测试道路为畅通，并取消测试订单。界面清除旧失败提案，原24单重新处于已规划、可开始配送状态。时间轴搜索“知新园”仅显示O1：预计签收25.33分、截止27.33分、余量2.00分，实际签收仍为“未签收”。

截图见[地点搜索和筛选布局](visual/planning-insights-followup/search.jpg)、[刷新后拒单详情](visual/planning-insights-followup/refreshed-rejection.jpg)、[手动失败提案](visual/planning-insights-followup/manual-rejection.jpg)、[恢复后的预计与实际签收](visual/planning-insights-followup/final-timeline.jpg)。仅验证实际默认窄视口，不宣称穷尽所有屏幕尺寸。此前阶段的数据与截图保留不覆盖。

服务仍使用单进程内存会话；本轮没有扩展持久化、回放、算法或其他附加功能。
