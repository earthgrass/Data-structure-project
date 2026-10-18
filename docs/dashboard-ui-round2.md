# Dashboard 第二轮 UI / UX 重构交付记录

日期：2026-10-18。范围：Phase 5 前端展示与交互，继续使用 `feat/dashboard-ui-redesign`。

## 审计与根因

- 修改前工作区干净；原 HEAD `7754130`。根目录 AGENTS.md 适用，前端没有额外 AGENTS.md。
- React 18.3 / TypeScript 5.6 / Vite 5.4（锁文件安装 Vite 5.4.21）。入口 `main.tsx → App`，无路由器。开发 `npm run dev`，类型检查 `npm run typecheck`，生产构建 `npm run build`。package.json 没有前端 test 脚本，没有引入测试框架或 UI 依赖。
- `.dashboard-shell` 强制 `min-width:1280px`，窄屏规则又给 `.app` 设最小宽度，阻止正常收缩。
- 固定 `100vh` 外壳叠加固定最小网格行高；侧栏 stack 与算法组分别滚动，长场景名不换行，形成嵌套滚动与横向撑宽。
- 网格区域声明 `compare`，比较组件使用 `grid-area:comparison`，生成隐式轨道。比较区另有 `max-height:280px; overflow:hidden`，完整结果被裁切。
- Header 定义四列却只渲染三个直接子项；统计徽章不换行，额外本地时钟错误地称为数据时间。
- `REAL` 仅由场景名 / 数据非空推导，不能证明真实道路来源。
- 路线边错误地使用 stop_sequence（配送站点）匹配道路边，且与普通边一起被开关隐藏。成本方案的路段距离直接取 total_weight，混淆主目标权重与距离。
- CSS 由 tokens / global / dashboard 三处导入，无其他组件样式文件；移除旧 dashboard 布局与无用 legacy 卡片规则，统一重建，不在旧文件末尾叠加补丁。

## 新结构与组件职责

```text
App（唯一场景 / 规划 / 比较资源，唯一地图与时间轴选中节点）
├── HeaderBar（全宽品牌、真实场景摘要、验证状态）
├── SideNav（种子、目标、操作、数据来源、折叠算法说明）
└── main.workspace
    ├── 工作区标题与请求状态
    ├── workspace-grid
    │   ├── NetworkMap → RouteSchematic → Edge / Node layers
    │   └── ResultPanel → KPI / PlaybackStrip / 折叠统计、时间轴、路段详情
    └── ObjectiveComparison（正常文档流，全工作区宽）
```

- App 继续使用原 useAsyncResource 和 usePlayback，未新增第二份业务状态。生成新场景时还会使旧规划 / 比较请求 ID 失效；请求期间禁用冲突操作。结果增加场景名、目标一致性检查；比较保留双目标完整性检查，并校验两个结果属于当前场景。
- HeaderBar 删除伪数据时间与 REAL 徽章，窄屏收起次要场景名称。车辆数来自 `scenario.vehicles.length`。
- SideNav 由多层白色小卡片改为深色分区，核心操作靠前，算法帮助默认折叠。侧栏不再独立滚动，长 ID 允许换行。
- ResultPanel 独立呈现 idle / loading / error / success，错误复用 ErrorState。六个等大 KPI；不把计划中的订单数冒充动画已送达进度。回放累计值仍由原 PlaybackStrip 展示。
- 时间轴保留真实到达 / 等待数据与地图联动，支持键盘 Enter / Space。等待为零显示“无等待”，不再误称“不停”。
- RouteLegDetails 优先读取 cross_metrics，仅对应主指标缺失时回退 total_weight；未知值显示破折号，距离 km / 时间 min / 成本元。
- RouteSchematic 使用后端 road_node_sequence，普通边先画，配送路线后画；开关只控制普通边，不删除图数据。仓库 / 客户 / 中转的颜色与形状保持原语义。
- ObjectiveComparison 独立错误与重试、加载状态，补齐单位。不再按目标名称将指标标绿冒充胜出。差异方向使用中性文本；不同主目标值标注“不同语义”。零基准不计算百分比，负值不适用，相同值显示相同，非有限值显示破折号。
- types.ts 移除重复合并的 CompareResponse 声明，不改变实际接口契约。

## Tokens 与布局

主背景 `#F3F5F9`，白卡片，侧栏 `#14213D`，主按钮 `#2563EB`；辅助文字改为 `#64748B`。tokens.css 集中管理颜色 / 字号 / 间距；正文 14px，辅助 12–13px，标题 24px，KPI 24px；按钮 40px。卡片统一细边框 / 10px 圆角，间距 8 / 12 / 16 / 24px。

外层 Grid = `260px minmax(0,1fr)`，Header 跨列。工作区 Grid = `minmax(0,1.6fr) minmax(340px,.9fr)`；1400px 以下减少间距、调整比例，1150px 以下内容单列，760px 以下控制栏改为顶部双列分组。地图 SVG 使用容器宽度与原始 viewBox 等比缩放，图例放在画布下方的正常流中。

页面级纵向滚动；地图 / 侧栏 / 比较区不设独立纵向滚动。展开的时间轴和路段列表保留必要的限高滚动。极窄屏比较表有局部横向容器，页面本身不溢出。focus-visible 使用可见轮廓与焦点环。

## 数据来源核验

真实 `/api/scenario/current` 返回：`name=logiroute.random.30.seed42`、`mode=fixed`、`metadata.generator=logiroute.scenario_generator`。来源按 generator 判断为“随机示意场景”，不能把 mode 或 Validator PASS 当作真实道路证明。非生成器数据保守显示“固定 / 未核验来源场景”。当前 API 无已验证真实道路来源契约，本轮没有发明该契约。

距离、时间、成本单位由 core/edges.py 文档核实：公里、分钟、元。到达时间是仿真时间，不伪造现实时间戳。

## 验证记录

- `PYTHONPATH=src python -m unittest discover -s tests -t .`：495 用例通过，40.695s。仅存在原有 API algorithm 字段弃用提示。
- `npm run typecheck`：0 错误；`npm run build`：成功，51 modules。项目没有前端测试脚本。
- 浏览器使用临时同源 iframe 验收页，以真实 CSS 视口渲染完整 Dashboard；预览仅按工具窗口宽度等比缩放，应用内部没有 zoom 或缩小字号。不是原生浏览器窗口最大化截图。

| 实际视口 | scrollWidth / clientWidth | 布局 |
| --- | --- | --- |
| 1654 × 900 | 1639 / 1639 | 地图、结果并排，比较在下方 |
| 1440 × 900 | 1425 / 1425 | 地图、结果并排，比较在下方 |
| 1366 × 768 | 1351 / 1351 | 地图、结果并排，比较在下方 |
| 1024 × 768 | 1009 / 1009 | 地图、结果上下排列，比较在下方 |

15px 差值为浏览器纵向滚动条。四个尺寸均无页面水平溢出。1654 视口实测地图约 837px、结果约 471px，卡片顶部对齐；比较区位于两张卡片之后。

实测状态：初始 / 生成后空状态、距离规划加载与成功、成本目标选择与规划、双目标加载与成功、普通边开关、时间轴联动、回放与重置、seed=43 生成清空旧结果。seed=42 距离方案 1887.92km / 4475.23元；成本方案 1808.70km / 4128.65元；均20/20订单、一辆车，与既有冻结结果一致。控制台正常流程未发现 warn / error。

错误验证：独立临时 Vite 代理将目标 API 指向不可达端口，实际触发场景生成、规划、比较 proxy_error；错误提示与重试入口可见，比较重试仍如实失败，无成功表格。没有停止或改动原后端服务。服务恢复后同一错误卡片直接重试成功、所有错误种类、旧场景失败保留和恶意乱序响应未逐一注入实测；保留原状态机并加固请求防护。

## 文件与边界

修改：frontend/src/App.tsx、types.ts；layout/HeaderBar.tsx、SideNav.tsx；map/NetworkMap.tsx、RouteSchematic.tsx、NetworkEdgeLayer.tsx、NetworkNodeLayer.tsx；results/ResultPanel.tsx、ObjectiveComparison.tsx、RouteTimeline.tsx、RouteLegDetails.tsx；styles/tokens.css、global.css、dashboard.css；README.md。

新增：本交付记录。删除：无源文件删除（旧样式规则直接清理）。临时验收页和错误代理配置均在交付前删除，未加入生产产物。截图保存在本地交付附件目录，页面地址为 http://localhost:5172 。

没有修改 src/logiroute、后端 API / 数据结构、Dijkstra、MinHeap、CFI、2-opt、生成器、Seed机制、容量与时间窗校验、单车辆规则；没有接入 OSM / Leaflet / 真实道路 / 实时交通。没有更改依赖、main 或 WIP-phase5-real-road-bjut 存档，没有 push。

限制：当前附件只有任务文本，未获得参考报告 Figure 6 PDF 与原始1654×900截图，因此按文字定义的视觉原则设计，没有声称逐像素比对。大图和完整比较结果需要页面纵向滚动，空结果卡片不会人为拉高。回放沿用既有客户端动画模型，未改后端调度或引入真实车辆定位。
