# Phase 7 最终交付报告

## 1. 基线和范围

起始main与origin/main均为 `f0c6bfe69c30e4b3c9677c7290b7ab14ffcd02c0`，工作区干净。独立分支 `codex/final-polish-and-defense`。用户已授权7A–7G；本轮不合并main、不替换核心算法、不修改配送语义。交付源码最终修复提交为 `5c092b0`，随后提交本交付包及证据；含本报告的准确最终HEAD以分支提交历史和最终Git核验为准，避免在文件内伪造自引用提交hash。

## 2. 审计发现与问题分级

| 等级/证据 | 问题 | 最终处理 |
|---|---|---|
|P1源码、浏览器|地图隐藏操作提示|恢复真实后端状态下的下一步说明，保留现有状态机|
|P1源码、浏览器|订单按楼名搜索无结果、位置枚举难读|名称加入搜索，中文仓库/中转/载货/已签收，原ID和Decimal字符串保留|
|P1浏览器实际复现|库存把路由junction显示为中转站|先失败回归再修复，显式只显示warehouse/transfer，实际7设施卡|
|P1实验解释问题，非求解bug|校园初始成本同比例，双目标相同|隔离受控成本实例，固定同输入真实运行，保留校园原数据|
|P2视觉建议|点击目标偏小、辅助说明偏小|局部字号/44px操作控件、抽屉留白和底部说明，四视口核验|
|P2文档|README旧V1说明先于当前产品|当前产品入口、真实调用链、交付包、旧README完整正文存档|

无已确认且尚未修复的新增P0。风险与视觉建议没有冒充bug。ui-ux-pro-max在实际环境中未安装，没有声称调用；使用已有设计规范及computer-use实际浏览器验收。

## 3. 修改与测试证据

先写前端搜索/位置回归，缺少模块时失败，再实现。库存额外回归先因缺少inventoryNodes失败，再修复并浏览器确认。新增Python受控实验测试先观察模块缺失和404失败，再实现；适配原始字符串需求/容量时严格分别转Decimal，没有修改核心数量模型。

五项objective_demo测试覆盖同输入冲突、独立四组合基准、同址独立窗口/等待、不可行身份保留、路况过期计划拒绝及独立API；两项phase7_windows测试验证urgent/critical竞争、拥堵后的真实窗口失效。历史测试文件完全未改动。

## 4. Dashboard与视觉验收

保留全屏地图、可收起抽屉、六车稳定颜色、实际道路折线动画和版本绑定。新增受控实验只在“实验与审计”工作区，不改变当前校园会话；页面明确模拟成本、独立输入及极小枚举边界。

[视口原始测量](../visual/phase7/viewports.json)：1650×900、1366×768、1920×1080、390×844均为实际CSS视口，document.scrollWidth等于视口宽度，主操作高度44px，流程提示可见。路网及路线约2789个SVG path；重复切换视口/车辆后没有累积图层或横向溢出。未取得帧级渲染计时/React Profiler数据，不据此声称60fps或完成严格帧率性能优化。

真实截图导航：

- [全屏地图1650](../visual/phase7/overview-1650.jpg)、[1366](../visual/phase7/overview-1366.jpg)、[1920](../visual/phase7/overview-1920.jpg)、[手机](../visual/phase7/overview-390.jpg)。
- [楼名搜索](../visual/phase7/building-search.jpg)、[严格顺序对照](../visual/phase7/strict-comparison.jpg)、[原路线叠加](../visual/phase7/route-overlay.jpg)。
- [动态特急录入](../visual/phase7/dynamic-add.jpg)、[pending及0.1需求](../visual/phase7/dynamic-pending.jpg)、[车辆配送](../visual/phase7/vehicle-moving.jpg)。
- [库存修复前](../visual/phase7/inventory.jpg)、[仅七设施修复后](../visual/phase7/inventory-final.jpg)、[交通暂停](../visual/phase7/traffic-pause.jpg)、[检查点续程](../visual/phase7/checkpoint-replan.jpg)。
- [24单实际完成](../visual/phase7/campus-complete.jpg)、[动态25单完成](../visual/phase7/dynamic-complete.jpg)、[独立历史审计](../visual/phase7/complete-audit.jpg)、[双目标受控结果](../visual/phase7/objectives.jpg)。
- [后端重启404反馈](../visual/phase7/session-missing.jpg)、[legacy实际规划20/20](../visual/phase7/legacy-final.jpg)。中间legacy.jpg仅为计算中截图，不冒充最终成功。

实际浏览器过程：严格seed42完成24/24并全部返仓；在此真实完成状态下新增DEFENSE-CRITICAL，P01、需求0.1、earliest46.392397、deadline166，先pending再规划。装货后更新一条模拟有向道路并暂停，完成已进入道路至检查点，原载货不变，重新规划续送。最终25/25，六车load=0、position=base、current=null，独立审计valid/complete。snapshot revision267、traffic_version1、最终61.397534模拟分钟，264条真实事件。

刷新页面仍恢复后端存在的会话与25/25；后端重启则404并提供新建恢复路径。运行legacy真实规划得到20/20可行闭环。原一致性测试继续覆盖409、迟到轮询、不同session、比较与交通版本失效。浏览器中没有专门注入一条409竞态，因此不把单元/API证据称浏览器竞态复现。

## 5. distance/cost受控实验

[配置](../../config/phase7-objective-demo.json)、[原始结果](../experiments/phase7-objectives.json)、[独立复验](../experiments/phase7-objectives-recheck.json)。同一有向图、一单、同容量、同窗口、相同指纹；两种目标都用真实生产Dijkstra和两级插入并实际执行。

|目标|距离|模拟成本|行驶分钟|最终返仓|末端实际道路|
|---|---:|---:|---:|---:|---|
|distance|4|18|4|14|H→A→H|
|cost|6|6|6|16|H→X→A→X→H|

直达通道模拟服务成本8元/km、普通通道1元/km；没有修改OSM距离或历史成本，也不称真实收费。独立DFS枚举4种正权简单出入路径组合，当前极小例最小距离4/最小成本6。只在一单一站固定干线范围内适用，不证明一般贪心最优。

两个PYTHONHASHSEED独立进程比较两种完整计划，指纹均为 `8090d7c6ba6d77729ae3fbc1ab48bfec4d2c1f46365cc550fec185eba87b4748`，原始记录见[跨进程证据](../experiments/phase7-objective-processes.json)。

## 6. 时间窗A–G与失败案例

[最终8次实际执行记录](../experiments/phase7-windows-final.json)，每条包括逐单earliest/deadline/completion/slack、未接纳原因、完整道路动作、等待、三指标、返仓及独立审计。

|对照|实际签收|全覆盖|结论|
|---|---:|---|---|
|A校园宽松|24|是|原始窗口，原路线|
|B校园严格|24|是|仅改窗口，WEST真实服务顺序改变|
|C极小窗|0|否|服务本身超预算，明确completion_deadline|
|D推迟earliest|1|是|实际等待，完成恰好32，等于截止合法|
|E urgent竞争|2|是|允许先服务deadline13的normal以保住两单|
|E critical竞争|1|否|同车同批critical优先，normal明确未接纳|
|F同址不同截止|2|是|两ID分别32/34完成，身份不合并|
|G交通更新|0|否|旧计划重新验证无效，新计划如实partial|

保留最初phase7-windows.json。复查脚本时进一步显式传入同一带Network历史的Session，最终版另存phase7-windows-final.json，没有覆盖旧证据；最终结论以final为准。原五seed20次严格/宽松执行与跨进程证据均保留，新样本是受控教学例，不代表真实总体成功率。

## 7. 校园数据真实性

[地图审计JSON](../experiments/phase7-map.json)与[核验说明](../phase7-map-performance.md)：342/768，180条有向边无反向伙伴；全部边几何端点匹配，五seed道路指纹相同、20/4配额一致。地点reference与道路snap坐标、snap距离、OSM引用、近似标记逐项保存。五站按用户描述近似，楼栋参考OSM，周边候选与仓库模拟；未将参考点说成真实楼门。

本轮data/字节、许可及来源文件完全未改动，不重抓数据，不把背景道路视为可通行边。端点检查不证明现实门禁/临时施工或楼门测绘。

## 8. 性能与工程质量

完整表见[性能说明](../phase7-map-performance.md)和[原始计划/计时](../experiments/phase7-performance.json)。12/24单合法配置实际生成0.7372/1.2909秒，distance0.0794/0.2974秒，cost0.0827/0.4009秒，单独严格窗构造1.2580秒。36单因无放回候选池30个被明确拒绝。不是为了凑数量加容量或虚构客户。

真实装货检查点动态重规划0.0511/0.1849秒，24单规模安全但新单未接纳，partial保留。与浏览器“全部返仓后新增单、再更新交通”的25/25成功例输入和时机不同，不混用成功率。

浏览器最终完整API响应804537字节，GET实测0.19997秒，记录含整个实际snapshot，见[API原始数据](../experiments/phase7-browser-session.json)。性能表714601字节是初始Session快照，统计口径不同。没有证明需要改核心算法的严重瓶颈，因此无生产性能优化提交。未来静态地图分离可能减少0.7MB以上轮询负担，本轮保留原协议。

## 9. 测试与扫描

- Python全量 **801/801**，失败0、错误0、跳过0，退出码0，**286.290341秒**。[原始输出](../experiments/phase7-regression.json)。原794项未改动，新增5+2项。
- 定向受控/API/两级16项通过；窗口/受控/原严格/交通17项通过；校园/OSM14项通过，均真实执行。
- 前端最终 **109个断言**通过（原100保留、新增9）；TypeScript及Vite生产构建通过，74模块，JS247.34kB、gzip82.44kB，无新依赖。
- Python全量之后只新增文档、证据、脚本输出路径参数与前端库存展示修复；生产Python及其测试未变化。前端修复后已重新运行全部断言及构建，不无意义重复Python耗时门禁。
- [AST扫描](../experiments/phase7-quality-final.json)：无禁用导入、无新增未审查排序调用。保留并披露7处历史辅助sorted：Dijkstra trace1、图邻接导出1、历史depot初始化/诊断5；当前核心堆、候选插入与排序手写，没有把全仓库扫描说成字面零命中。
- Git diff检查通过；旧测试无删除/断言降低，data/依赖清单与锁文件未变。

## 10. 实际文件与职责

```text
config/phase7-objective-demo.json / phase7-experiments.json  独立教学输入/矩阵
src/logiroute/algorithms/demo_reference.py                  极小独立枚举
src/logiroute/dispatch/controlled_demo.py                   原生产规划与真实执行适配
src/logiroute/api/routes/dispatch.py                       隔离只读实验GET
frontend/src/dispatch/product.*                            楼名搜索/库存展示辅助
frontend/src/dispatch/components/                          订单、库存和受控实验呈现
frontend/src/dispatch/styles/product.css                   局部可读性/44px/流程说明
tests/test_objective_demo.py / test_phase7_windows.py       新增7项回归
frontend/tests/dispatch-product.mjs                         新增9个断言
scripts/experiment_objective_demo.py / experiment_phase7_windows.py
scripts/audit_phase7_map.py / experiment_phase7_performance.py / audit_phase7_quality.py
docs/experiments/phase7-* / docs/visual/phase7/              真实原始结果及视觉证据
docs/final-delivery/                                       统一交付包和历史README
README.md / docs/architecture.md / docs/development-plan.md / AGENTS.md
```

## 11. 课程交付材料

[交付入口](README.md)、[教师讲解/复杂度/问答](defense.md)、[约7分钟脚本](demo-script.md)、[当前README](../../README.md)、[真实架构图](../architecture.md)。旧README完整正文另存，Markdown硬换行转换为显式br，不改旧阶段数字或结论。历史Phase3的5/6与216全覆盖反例继续保留。

## 12. 提交与保护

|提交|逻辑内容|
|---|---|
|bd5073b|7A审计、楼名搜索、真实位置说明及局部交互完善|
|3818e82|隔离双目标JSON、原算法适配、独立枚举、测试及审计页|
|f1fc20c|A–G窗口/优先级实际实验与回归|
|0543428|冻结地图核验、真实性能原始数据及文档|
|5c092b0|浏览器复现后的库存junction过滤修复|

以上每逻辑提交经相关门禁后独立推送，未强推、未重写历史。最终交付文档和剩余验收证据另作提交；最终答复给出其真实hash、远端一致及工作区状态。main须仍为f0c6bfe，其他历史分支及stash保持原引用。

## 13. 剩余边界与停止

尚无实地柜位测绘、真实门禁/收费/交通接入、帧级性能认证或多进程持久化会话。贪心不保证最优，有限生成失败不证明无解，初始严格窗是筛选样本，任意动态变更不保证全覆盖。只验证了记录中的实际输入和操作。

Phase7代码、实验、文档及回归验收完成后停止，不自动合并main，不启动下一阶段。
