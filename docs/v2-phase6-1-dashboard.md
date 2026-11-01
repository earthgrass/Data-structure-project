# Phase 6.1 — Enterprise Logistics Command Center

## 范围与基线
基线6362aa939f28a3034f2e00984e266e5a484ad9dd，本地/远端相同，初始工作区干净。
独立分支feat/phase6-1-dashboard-redesign，创建前本地和远端均无同名分支。
本轮只改前端及交付文档；Phase 6后端、全部既有测试与/legacy业务保持冻结。

## Skill实际情况
检查项目.agents/.codex、用户.agents/skills（含Junction）、.codex/skills、插件缓存，
未发现ui-ux-pro-max，也无原生skills.list工具提供该包；没有安装或声称调用。
采用用户给定的Enterprise Logistics Command Center方向与本项目实际状态结构自行设计。

## 改造前证据与设计决策
[1650×900原页面](visual/phase6-1/before-1650.png)：五张KPI挤占高度、地图约在y=517开始，
深色细线和小字拥挤，车队/行程/订单/交通/事件同页展开；所有操作同等突出。
比较结果独立state不会随输入更新失效，页头常绿且404没有专属恢复状态。

采用深海军蓝232px导航、68px工作栏、浅灰主背景、白色容器、橙色单一主操作。
六个真实切换工作区：总览、车队、订单、库存与中转、交通与路线、实验与审计。
总览最多四个业务KPI，地图在操作栏下成为主画布；右侧选中车辆详情。
站点用形状和标签区别，客户默认不铺满标签；选中路线高亮、普通道路低对比。
不采用无业务依据的装饰KPI，不引入地图/状态/UI依赖，不计算物流决策。

## Token
沿用frontend/src/styles/tokens.css语义变量；在.dispatch作用域覆盖色板、字号、间距和尺寸，
旧页面仍继承原:root值，不再保留旧dispatch暗色字面量主题。
正文15px、辅助14px（仅地图/版本辅助12px），标题28/24/18px；8px主间距、4px微调。
白色容器14px圆角、控件8px；轻阴影；180ms反馈；键盘focus-visible蓝环，尊重reduced-motion。
蓝/青/紫/绿对应车辆，红色仅错误、封路/风险，橙色承担主操作。

## 验收记录
后续按真实执行补充状态测试、截图、视口几何检查、构建、Python全量及Git核验。
不得将本设计计划当成已完成验收。
