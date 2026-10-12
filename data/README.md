# LogiRoute 数据目录

本目录用于存放网络与配置数据。

* Phase 1 **不**包含任何 JSON / 配置文件，仅保留目录路径。
* Phase 2+ 将引入：
  * `network.sample.json` —— 小型示例配送网络（节点 + 边）
  * `vehicles.sample.json` —— 默认车辆清单
  * `orders.sample.json` —— 默认订单清单
  * `traffic.scenario.json` —— 动态交通事件剧本

文件命名规则与 JSON schema 将在对应 Phase 的文档中说明。

## 当前状态

* Phase 1：尚无数据文件。
* 所有数据加载入口应通过 ``logiroute.config`` 模块（Phase 2+ 提供）。
