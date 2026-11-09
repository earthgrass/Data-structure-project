# 北工大校内快递站、四门外卖柜与校内订单

## 本轮确认与模型

2026-11-09 用户确认：校内快递站在游泳馆稍北侧；东、西、北、南门分别有外卖柜。
五个地点在课程模型中作为**同一级中转点**，沿用“校外集配仓 → 中转点 → 收货点”的两级配送。
一辆干线车补货，每个中转点绑定一辆末端车，共六辆。备用仓保留，不虚构配送任务。
没有增加“中央站 → 门柜 → 客户”的第三层转运。

学校公开的[校园快递服务项目公告](https://www.bjut.edu.cn/info/1119/3623.htm)
说明了集中快递站与智能自提柜的服务模式；本轮具体位置依据用户的校园知识，
不将该公告当作柜位测量数据。

### 位置来源与精度

| 模型 ID | 地点 | 定位依据 | 参考点至道路服务锚点 |
| --- | --- | --- | --- |
| T_CENTER | 校内快递站（游泳馆北侧） | 用户描述；OSM 游泳馆轮廓北缘向北约 20m 的初始参考 | 9.94m |
| T_EAST | 东门外卖柜 | 用户确认门外有柜；OSM 东门外侧约 12m 参考 | 9.72m |
| T_WEST | 西门外卖柜 | 用户确认门外有柜；OSM 西门外侧约 12m 参考 | 4.66m |
| T_NORTH | 北门外卖柜 | 用户确认门外有柜；OSM 北门外侧约 12m 参考 | 12.00m |
| T_SOUTH | 南门外卖柜 | 用户确认门外有柜；OSM 南门外侧约 12m 参考 | 3.67m |

20m/12m 是用于初始落点的建模参考，不是用户提供的实测距离。实际图节点仍在原始道路上；
柜位、快递站和楼栋入口均未实地测绘。节点保留 `reference_lon/lat`、`location_source`、
`approximate`、`location_note` 和 `snap_distance_m`，点击地图可看到近似定位说明。
北门服务锚点恰为道路门口节点，不能据此将其说成柜体精确坐标。

## 校内候选池与任务分布

此前周边模式的 30 个候选点中只有 2 个位于学校主体边界内。本轮单独增加校内模式：

- 固定 30 个候选点：22 个校内、8 个学校周边道路服务点。
- 校内点以 OSM 楼栋为参考，覆盖 1～9 号、10/11 号、12～14 号宿舍，
  第一至第四教学楼、逸夫图书馆、北图书馆、信息楼、知新园和科学楼。
  OSM 中 10/11 号宿舍是一处共同楼栋轮廓，保留共同参考，不伪造独立楼体坐标。
- 初始 24 张订单：**校内 20 单、周边 4 单**，约 83.3% 在校内；按整数配额抽取，
  不用随机概率冒充每次必达配额。初始目的地无放回，动态订单仍允许同址多单。
- 默认 24 单相对旧周边模式的 8 单增加到三倍。不同 Seed 改变任务，固定道路和地点不变。
- 楼栋参考中心至服务锚点约 18～86m，配置超过 100m 明确拒绝。
  这些点表示楼栋附近道路接驳点，不冒充宿舍门口精确位置；没有画穿楼接驳道路。

实际图为 **342 个节点、768 条有向道路**。较旧图增加的 13 个节点是原有道路上的形状点，
为地点落点而拆分现有道路链；方向和折线保留，不制造新道路或反向边。

## 文件、职责与数据结构

```text
data/bjut/campus-config.json            校门/游泳馆/楼栋 OSM 引用、参考偏移、阈值
data/bjut/campus-network.json           派生固定路网、区域分组、地点来源、校园边界
config/dispatch_bjut_campus.json        24 单、20/4 配额、五中转点、六车独立容量
src/logiroute/algorithms/
  campus_locations.py                 手写点在多边形内判断、确定性最近道路锚点
  regional_sampling.py                精确区域配额校验与无放回采样
  osm_network.py                      复用道路提取与 SCC，保留/拆分地点锚点
src/logiroute/dispatch/real_map.py      显式 profile 与地点分组引用校验
frontend/src/dispatch/                 校园边界、实际楼名、六种车辆颜色、标签避让
tests/test_campus_delivery.py          新增七项回归测试
```

伪代码：`resolve OSM references → locate inside campus polygon → scan reachable road
nodes deterministically → reject excessive snap → reserve distinct anchors → split original
road chains → validate disjoint candidate regions → sample exact quotas → existing planner`。

点在多边形内使用手写射线交叉，时间/空间 O(B)，B 是边界点数。地点匹配扫描稳定节点顺序，
时间 O(LVB+V²)，L 为地点数；没有依赖 set 迭代顺序、字符串哈希或库排序。
区域采样先验证分组互斥、配额非负整数、总数一致和每组供给足够，再从剩余数组中抽取并移除，
最坏时间 O(N²+R²)、空间 O(N)。图仍使用原 LogisticsGraph、Node/Edge、手写 Dijkstra，
调度候选比较、时间窗、Decimal 容量、库存流转和独立验证器没有改写。

新增 API `profile="bjut-campus"`，Dashboard 新建场景使用该模式。
原 `random` 和 `bjut` 保留；旧 8 单/3 中转点入口、原始 OSM 提取、旧派生数据及历史实验不覆盖。
校园边界和六车选择栏适配窄屏；标签按屏幕尺寸避让，六辆车各有独立颜色。

## 实际验收

先写七项新 unittest，观察旧接口不接受新 profile、配置加载签名不匹配的失败后再实现。
新测试覆盖五个中转点位置来源、候选池分组、五个 Seed 的精确配额、非法配额拒绝、
全部候选点/中转点的 Dijkstra 往返、distance/cost 实际执行、同址动态身份和旧模式兼容。

- **全量 788/788 通过**，failure/error/skip 均为 0，退出码 0，真实耗时 508.314 秒。
  [完整结果](experiments/campus-delivery-regression.json)。原 781 项测试及其断言未删改。
- 新定向测试 7/7 通过；前端 90 项断言通过，其中新增 4 项标签分离/稳定性/坐标不变性断言。
  TypeScript 和 Vite 生产构建通过；未新增依赖，禁用算法依赖与排序扫描无新增命中。
- 五个 Seed（0、1、42、100、2026）× distance/cost，共 10 次实际执行，均独立验证 valid/complete。
  每次为 20 校内单、4 周边单。另在两个 PYTHONHASHSEED 独立进程核对完整输入及两种完整路线指纹，
  五个 Seed 均一致。道路指纹在全部 Seed 间一致。
  [原始结果](experiments/campus-delivery-results.json)，脚本 `scripts/experiment_campus_delivery.py`。
- seed=42 的默认分配为中央快递站 7、东门 5、西门 5、北门 2、南门 5；继续按真实图上的
  行驶时间聚类，不强制把全部校内订单分给中央站。
- 无拥堵初始数据使用统一每公里成本，distance/cost 两目标成比例、结果相同，不据此声称算法提升。
  两模式总距离（km）依次为：seed0 14.156、seed1 14.406、seed42 14.387、seed100 11.900、seed2026 13.489。
- 装货后插入并取消同址紧急单，原货物与车辆位置保持不变；检查点按 cost 重规划后实际完成原 24 单。
  [在途操作证据](experiments/campus-delivery-dynamic.json)。
- 浏览器实际完成 24/24 签收及全部返抵，并验证了地点来源提示、楼名标签和窄屏六车横向选择栏。

旧数据重建 SHA-256 仍为 `e086100e807051ab6d9a7b61b0268c2b2cebc574cae8b82c670b2bdca2a29b84`；
校园数据重建为 `f4aec16275070c81a352f4a4aece39610a7561b2bc38fb23e5e882504150a3ba`，两者均字节一致。
重建：`PYTHONPATH=src python -B scripts/build_bjut_map.py campus-config.json`。

提交分别为核心 `06f2c21`、配置换行属性修复 `ded2fe0`、界面 `921eb61`，保留完整历史。
配置原本为 Windows CRLF；首次暂存检查发现 CR 字符问题后，用独立提交设置
`text eol=crlf`，Git 中归一化存储，工作区仍按 CRLF 检出。配置的实际字节与实验记录哈希一致，
未改动 JSON 语义或原始实验结果；完整 `git diff --check` 已重新通过。

截图：[校内待播放总览](visual/campus-delivery/desktop-ready.jpg)、
[定位说明](visual/campus-delivery/station-location.jpg)、
[签收返抵](visual/campus-delivery/complete.jpg)、[窄屏](visual/campus-delivery/mobile.jpg)。

尚待实际柜位/快递站入口坐标精校；真实门禁、楼门接驳、转向限制和车辆通行许可仍沿用
[前轮边界](bjut-map-workbench.md)。本轮没有声称接入真实交通、真实快递业务或保证任意动态订单全覆盖。
