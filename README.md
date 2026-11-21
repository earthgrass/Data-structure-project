# LogiRoute — 校园两级智能配送系统

数据结构课程设计：在北工大校园及周边离线真实道路上，演示多车辆配送、严格签收时间窗、动态订单、模拟拥堵与安全重规划。核心图、最小堆、Dijkstra、优先队列及可行插入自主实现；React界面只展示后端事实。

**[最终课程交付包](docs/final-delivery/README.md)** · [答辩讲解](docs/final-delivery/defense.md) · [7分钟演示脚本](docs/final-delivery/demo-script.md) · [Phase 7验收报告](docs/final-delivery/report.md)

**新版：[运营参数工作台与真实路线试算](docs/operations-studio.md)**。默认3个运营站、4辆车，备用站点按需启用；逐车载重、油耗、模拟油价、行驶工时和维护费可调整，由原后端规划器重新计算。参数试算保留同一批订单与时间窗，创建隔离的新会话，不重置在途货物。历史5站6车的 `bjut-campus` 档案保持不变。

**地图更新：[订单标记与路线变化对照](docs/route-visibility.md)**。初始规划默认展示全部车辆路线；包裹标记显示活跃订单与紧急等级。同址多单按订单 ID 保留身份，已签收、已取消和已过期的订单从地图标记中移除，历史仍可查询。

**自动插单：[订单变更自动停靠与重规划](docs/order-change-replanning.md)**。Dashboard 新增、取消订单后自动完成已进入动作并在检查点重规划，显示变更前、当前路线及新增/移除路段；新计划应用后等待用户继续配送。受保护任务、容量或签收窗不允许接纳时，保留真实原因。

**规划解释：[影响摘要、拒单证据与订单时间轴](docs/planning-insights.md)**。“路线变化”显示同一检查点的剩余距离、模拟成本和预计签收变化；订单可展开真实失败候选；“时间窗”逐单展示窗口、预计到达／签收及实际签收。过时预测隐藏，硬约束保持不变。

后续[边界修复与验收](docs/planning-insights-followup.md)：手动失败提案可查看具体原因，刷新后保留后端拒单说明，时间轴支持地点名称搜索，无关路况版本不再误报全部车辆行程变化。

## 当前校园场景

**[特急插单预检](docs/critical-admission.md)**：手动新增特急先验证完整续程；必要时未装车的低优先级订单让位。无法验证按时签收时不插入，提示调整时间，保留原计划与真实载货。

**[第二次检查：道路拥堵与车辆载重](docs/second-inspection-traffic-capacity.md)**：对照课程题目、代码入口、可复现实例与演示步骤，列明已实现功能及剩余扩展提示。

- 固定342个路由节点、768条有向道路，保留真实道路方向和折线。
- 30个固定候选配送地点；默认24单，校内20、周边4。Seed改变订单，不改变校园路网。
- 游泳馆北侧校内快递站与东、西、北、南门外卖柜五个设施。新版默认启用中央/东/西3站、1辆干线车和3辆末端车；北/南两站备用。历史档案仍为5站6车。
- critical / urgent / normal三级优先级，逐车Decimal精确容量，同址多订单分别追踪。
- 新建校园场景默认严格预约窗，earliest限制服务开始、deadline限制签收完成，支持宽松对照。
- 动态新增、合法取消/显式过期、订单变更自动检查点重规划、方向性模拟交通、逐动作动画及独立历史审计。
- 全屏地图、逐订单包裹标记、加粗多车路线、路线变化/订单/车队/时间窗抽屉；实验工作区提供独立双目标受控实例。

![校园配送地图](docs/visual/phase7/overview-1650.jpg)

## 架构与数据结构

```mermaid
flowchart TD
    UI[React Dashboard / Action动画] --> API[FastAPI /api/v2]
    API --> TX[revision校验 / 锁 / Session副本事务]
    TX --> ST[State: 订单ID / 货物位置 / 车辆]
    ST --> P[两级规划: 最近可行中转站 + 可行插入]
    P --> D[单次Paths缓存 / 手写Dijkstra / 索引最小堆]
    P --> V[独立计划验证]
    V --> X[Session原子执行 / Network路况版本]
    X --> A[独立历史审计]
    X --> UI
```

邻接表与反向索引维护唯一图真相；字典保留订单身份，事件列表提供可重演事实。当前两级入口与历史Phase3全局车队插入、V1单车接口并存，不能混用语义。详见[架构](docs/architecture.md)与[复杂度和算法讲解](docs/final-delivery/defense.md)。

## 安装与运行

Python ≥3.11，Node.js使用支持当前Vite的版本。核心算法只依赖标准库；完整Web/API测试还需要FastAPI、Uvicorn、HTTPX。项目采用src布局，配置位于config/。

```powershell
# 项目根目录，首次安装
python -m pip install -e .
python -m pip install fastapi uvicorn httpx
npm --prefix frontend ci

# 终端A：后端
$env:PYTHONPATH="src"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000

# 终端B：前端
npm --prefix frontend run dev -- --host 127.0.0.1
```

打开 [Dashboard](http://127.0.0.1:5172/)，后端接口说明位于 [API Docs](http://127.0.0.1:8000/docs)。历史单车界面保留在 [/legacy](http://127.0.0.1:5172/legacy)。会话保存在单个后端进程内存，重启需新建；不要用多个worker假设共享会话。

## 演示操作

1. 创建校园场景，默认Seed42。可在“场景与管理”选择严格/宽松模式再新建。
2. 打开订单，按楼名或ID搜索；点击地图候选点可在该地点下单。
3. 点击规划路线。打开“时间窗”，查看WEST服务顺序变化与原宽松路线灰色叠加。
4. 开始配送，播放/暂停动画或单步；“下一节点暂停”才请求业务检查点。装卸、等待和签收均由后端动作确认。
5. 动态新增或取消订单后，查看“等待停靠 → 规划完成／规划受阻”的自动流程。检查真实接纳/未接纳原因与路线变化，再点击播放继续；新货物只在仓库装载。
6. 点击“专注地图”收起统计、车队与播放浮层，观察新增橙边或移除灰虚线；“退出专注”恢复控制。它只调整界面，不替代暂停配送。
7. “场景与管理”进入库存、交通、实验与审计；输入变化后旧比较失效。受控实验与校园会话隔离。

重规划后可在“路线变化”查看影响摘要，在未接纳订单上展开“为什么未接纳”，并在“时间窗”搜索逐单时刻和筛选低余量任务。提示阈值只影响展示，不放宽签收约束；详情见[解释工作台说明](docs/planning-insights.md)。

## 测试与实验

```powershell
$env:PYTHONPATH="src"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m unittest discover -s tests -t .
Get-ChildItem frontend/tests/*.mjs | ForEach-Object { node $_.FullName; if($LASTEXITCODE -ne 0){throw "frontend test failed"} }
npm --prefix frontend run build
```

原794项Python测试及100个前端断言完整保留。Phase 7全量801/801、前端109个断言通过，详见[历史最终报告](docs/final-delivery/report.md)。运营工作台升级在原801项之上新增9项测试，当前门禁与135个前端断言见[新版验收说明](docs/operations-studio.md)，不混用历史测试数量。

上一轮订单标记与路线对照更新：前端215项断言、相关Python回归14项及真实API场景342项断言通过，见[历史验证与口径](docs/route-visibility.md)。该轮未重跑历史810项全量测试；本次自动停靠流程的完整回归和严格/宽松在途插单实验，见[新的验收记录](docs/order-change-replanning.md)。

当前三项规划解释功能的新增回归及最终验收记录单独保存在[规划解释文档](docs/planning-insights.md)，不复用上一轮测试数量作为本轮通过结果。

- [双目标受控实验](docs/experiments/phase7-objectives.json)：同输入distance距离4/模拟成本18，cost距离6/模拟成本6；独立执行均完整。仅极小例枚举基准，不证明一般贪心最优。
- [严格窗A–G](docs/experiments/phase7-windows-final.json)：包括宽松/严格、极小不可行窗、等待、紧急竞争、同址不同截止与路况失效；保留partial案例。
- [五seed原严格实验](docs/strict-time-windows.md)：保留原始20次执行和跨进程指纹，不把受筛选教学样本当真实总体成功率。
- [性能与地图](docs/phase7-map-performance.md)：12/24单真实测量，36单因候选池不足明确拒绝；动态单不一定能立即被接纳。

## 数据真实性与边界

道路和建筑几何来自离线OpenStreetMap，保留原件、下载来源、SHA256与ODbL许可（[数据目录](data/bjut/README.md)）。校园快递站/柜位按用户描述近似定位，楼栋参考点与道路服务锚点不同；未测绘的设施不是精确真实楼门。订单、道路成本和交通均为模拟，不是实时导航、真实收费或真实配送业务。

启发式不保证全局最优；主目标最短路径闭包不枚举所有替代道路。valid不等于complete；计划接纳不等于签收；部分方案不能与完整方案直接宣称质量优劣。[历史贪心5/6反例](docs/v2-phase3-fleet-scheduling.md)继续保留。

## 历史与协作规范

[最终交付索引](docs/final-delivery/README.md) · [原README完整存档](docs/final-delivery/readme-history.md) · [阶段计划](docs/development-plan.md) · [AGENTS约束](AGENTS.md)

禁止以NetworkX、OR-Tools、NumPy、SciPy、heapq等替代课程核心实现；统一unittest，所有实验保留真实输入及测量，不覆盖历史证据。

MIT（项目代码）；OSM数据按ODbL及来源说明使用。
