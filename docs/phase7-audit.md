# Phase 7A 审计登记与实施门禁

基线 `f0c6bfe69c30e4b3c9677c7290b7ab14ffcd02c0`，main 与 origin/main 一致，工作区干净。新分支 `codex/final-polish-and-defense`；所有原分支、stash 和历史实验保留。首次 fetch 遇到 TLS 握手失败，第二次正常完成，未关闭证书校验。

用户本轮明确授权 7A→7G，覆盖旧阶段停止约定；不改变核心配送语义，不替换算法，不合并 main。ui-ux-pro-max 未安装（项目、用户 skills 及插件缓存检查），采用现有样式和状态机制。

## 真实调用链

React Dashboard / useDispatchSession → FastAPI routes/dispatch.py → 加锁、deepcopy 事务与 revision 校验 → Session → State/Network → dispatch.algorithms.planning.plan_dispatch → Paths（既有 Dijkstra、手写堆、单次路径缓存）/build_route → 独立 validation.validate_plan → Session.step 原子动作 → audit.audit_session。校园离线图由 real_map 加载；window_calibration 只构造输入；动画由后端 Action 和已确认快照驱动。

注意：当前两级入口是按优先级/截止/ID逐单接纳、按 travel_time 查找最近可行中转站，再进行完整两级路线插入。它与历史 Phase 3 八字段全局车队插入入口并存，答辩不得混为同一算法。

| 等级 | 状态/证据 | 项目 | 处理与验收 |
|---|---|---|---|
| P1 | 源码确认 | map-workbench.css 将 .d-toolbar-hint 隐藏，地图主流程失去后端状态说明 | 恢复真实状态提示，窄屏不遮住主按钮；浏览器验证未规划、待出发、检查点 |
| P1 | 源码确认 | OrderTable 搜索只匹配 ID/destination/hub，输入“第二教学楼”无结果，位置展示原始英文枚举 | 用节点名称参与搜索，展示位置语义但保留 ID；Node 断言与浏览器复现 |
| P2 | 源码尺寸证据/视觉改善 | 地图按钮 30–38px、时间窗辅助文字 11–12px | 局部字号与点击尺寸改进，保留全屏地图，四尺寸实际检查 |
| P1 | 已有数据确认，实验解释问题，非算法 bug | 校园初始 cost 为 distance 统一倍数，双目标相同 | 独立 JSON 模拟成本场景；同输入两目标真实规划、验证、执行及独立穷举 |
| P2 | 文档确认 | README 顶部仍突出旧 V1 单车阶段 | 当前产品入口、真实模块架构、统一答辩包，历史材料完整保留 |
| 风险 | 尚待本轮实测 | 动态增单/交通后快照与比较是否保持一致、严格窗边界、地图几何及性能 | 不预先称为 bug；回归/实验/浏览器核验后登记结果 |

目前未确认新增 P0；这不是不存在 P0 的证明。发现身份、库存、方向或版本错误，必须先回归复现再修复，不能以 UI 绕过。

## 文件级计划与验收

- 7B：Operations/OrderTable、轻量展示辅助模块、局部 CSS；不增加第二套业务状态管理。先写搜索/位置/提示断言，再实现，保留现有前端断言。
- 7C：config/phase7-objective-demo.json、隔离实验适配与脚本、unittest；固定输入、实际道路、单车容量、同一订单覆盖，枚举仅为极小图的独立基准。不污染校园默认配置或历史结果。
- 7D：新增 A–G 时间窗实验和测试；逐订单完成/截止/slack/等待/覆盖/返仓/独立报告，不把筛选样本当总体概率。
- 7E：核对地点参考坐标与服务锚点、许可、几何方向、固定道路和 20/4 配额；不重新抓取 OSM。
- 7F：perf_counter 测生成/构窗/两目标/step/重规划/验证/审计/JSON大小；先测量，不为了提交制造优化，不改核心算法。
- 7G：README、架构、复杂度、5–8 分钟脚本及统一交付索引。最终真实全量回归、Node断言、类型/构建、禁用依赖、diff、四尺寸浏览器截图，核验远端与保护引用。

原 794 项 unittest 和原 100 个前端断言保持完整；新增测试只验证本轮新增或实际修复行为。每逻辑阶段验证后提交推送；最终结果以新生成数据为准。

## 验收补充发现

实际浏览器进入库存页复现P1：`InventoryPanel`以type!='customer'过滤，因而将junction也列为中转站。先新增inventoryNodes回归观察缺少实现失败，再以显式warehouse/transfer过滤；浏览器确认仅五中转点和两仓库七卡，设施名称与ID同时保留。修复前inventory.jpg与修复后inventory-final.jpg均保存，未更改后端库存模型。

最终Python801/801通过（新增7项）；前端109个断言通过（新增9个）。未发现本轮新增且尚未解决的P0。正式结果、性能限制及已分类历史辅助排序见[最终报告](final-delivery/report.md)。
