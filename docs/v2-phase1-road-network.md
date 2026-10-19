# LogiRoute V2 Phase 1 — 双向路网生成与验证

本阶段仅交付道路生成、配置语义、道路验证与实验。V2 Phase 2 订单队列、
Phase 3 多车辆调度、动态订单、API 和 Dashboard 改造均未实施。
路网连通不是完整配送可行性的证明，不宣称 V2 已实现全部订单 100% 送达。

## 1. Git 基线与变更边界

- 基线：`eb6fee0eb67fdcaaca6abcb1ca004767a36ff998`。
- 起始分支：`feat/dashboard-ui-redesign`，工作区干净。
- 新分支：`feat/multivehicle-dynamic-orders`；执行前确认本地及远端均不存在同名分支。
- 不修改 main、原 Dashboard 分支或 `WIP-phase5-real-road-bjut` stash。
- 代码与测试提交：`ca54da3`，`feat(generator): generate reproducible bidirectional road networks`。
- 保留 LogisticsGraph / Node / Edge / Dijkstra / 旧调度算法及原有测试。
- 本阶段不修改手工固定场景 `config/scenario.json`。

## 2. 配置语义与兼容性审计

默认道路参数位于 `src/logiroute/scenario_generator/road_defaults.json`，随 Python
包分发。`GeneratorConfig` 保留现有构造方式；`load_generator_config(path)` 可加载
额外 JSON 配置。JSON 范围数组归一化为 tuple，未知字段拒绝。

| 字段/读取位置 | 含义及兼容处理 |
| --- | --- |
| `LogisticsGraph.edge_count` | 实际有向边条数，保持不变 |
| API `schemas.graph_to_dict` / 前端 `GraphData.edge_count`、App、HeaderBar、SideNav | 原样传递和显示有向边数；未改 API/UI |
| `scheduling.graph_identity` | 有向边数量参与缓存指纹；保持不变 |
| 生成器 `min_edges / max_edges` | 有向边硬预算，保持原义 |
| loader 的 `ScenarioLimits.min_edges` | 固定场景有向边最低规模，保持不变 |
| `physical_road_count` | 精确物理连接数 P；None 时按预算选择 |
| `target_directed_edge_count` | 期望有向边数；仅给目标时选择最接近的可行配额，偏差写入报告 |
| `bidirectional_ratio` | 双向物理连接占比，默认 0.95 |
| `max_extra_edges_per_node` | 原先按节点添加有向边的旧策略参数；废弃，显式传入时报错并提示迁移 |
| 含糊的 `edge_count` 输入配置 | 原生成配置没有此字段；新 JSON 加载器拒绝，不猜测其含义 |
| 测试、脚本与历史文档的边数 | 仍为有向边数；旧实验数据按基线存档，不用新值覆盖旧记录 |

读取位置通过 `rg -n 'edge_count|min_edges|max_edges|max_extra_edges' src tests config
scripts frontend/src docs README.md` 审查。

默认值 `physical_road_count=null`、`target_directed_edge_count=null` 表示在硬预算
内选择最接近 `max_edges` 的可行配额；这是替代旧随机密度策略的显式新规则。
因此默认五个 seed 的边数相同，拓扑和方向权重仍随 seed 变化。

对 P 条物理道路，计算：

```text
B = floor(bidirectional_ratio × P + 0.5)
S = P − B
E = 2B + S = P + B
```

要求 `B >= V−1`、`P <= V(V−1)/2`、`min_edges <= E <= max_edges`。
固定 P 和 E 同时给出时必须一致，否则拒绝。仅给 E 目标时允许整数配额偏差，
选择绝对偏差最小的方案，平局取更少道路；报告实际 E 与偏差。
配置构造时检查节点范围两端，实际生成前再检查抽中的节点数。

示例：

```python
from logiroute.scenario_generator import GeneratorConfig, load_generator_config

cfg = GeneratorConfig(physical_road_count=80)  # B=76, S=4, E=156
cfg = GeneratorConfig(target_directed_edge_count=151)  # E=150，记录偏差 -1
cfg = load_generator_config("my-road-config.json")
```

可以只在 JSON 中写覆盖项，例如 `{"physical_road_count": 80}`。坐标、速度、
成本范围、距离扰动、最小几何距离和节点前缀也由道路 JSON 提供默认值。
订单、车辆等旧业务参数未在本阶段迁移或扩展。

## 3. 算法与数据结构

```text
读取并校验配置
生成确定顺序的节点列表
求满足骨架、配额和有向边预算的 (P, B)
对节点索引做手写 Fisher–Yates 洗牌
对每个非根节点，选一个更早出现的节点作父节点
    建立一条双向物理道路（共 V−1 条，永不裁剪）
按固定索引顺序枚举所有剩余无序节点对
对候选列表做手写 Fisher–Yates，取 P−(V−1) 条
将其中 B−(V−1) 条设为双向，其余设为单向并抽取方向
对每个方向分别采样 distance、travel_time、cost
写入稳定标识，加入现有 LogisticsGraph
运行独立道路验证器；失败则拒绝返回
```

每个新树节点仅连向已有树节点，因此无环并覆盖全部节点。双向树本身已保证
所有节点去程和返程可达，后续添加合法边不会破坏这个性质。

| 数据结构 | 原因 |
| --- | --- |
| 节点索引和候选节点对 list | 提供固定初始顺序，便于手写 Fisher–Yates |
| 骨架节点对 set | 只做成员查询；从不按 set 顺序消耗随机数 |
| 现有邻接表与反向索引 | 保留有向图和 Dijkstra 的全部接口 |
| 验证器 dict 分组 | 按无序端点重数真实道路，与 metadata 交叉检查 |
| 显式 DFS 栈 | 独立检查正向、反向和骨架覆盖，无第三方遍历算法 |

稳定标识保存在现有 `Edge.metadata`：

- `road_id = road:<规范化端点A>:<规范化端点B>`；反向边共享 road_id。
- `edge_id = <road_id>:<source>><target>`；每个方向独立且唯一。
- `bidirectional`、`skeleton` 明确标记道路属性，验证器与实际边交叉校验。

本阶段不引入多重边。相同无序节点对只采样一次，因此单向道路不会被后续采样
意外补出反向边。两个方向分别消费随机数，权重允许不对称。

生成器涉及节点/客户排序的旧 `sorted()` 改为手写稳定插入排序，保持原字典序；
新道路采样本身无需排序。调度器、图导出和 Dijkstra 诊断中的历史排序调用未在
本阶段扩大修改，后续改造对应模块时应单独审查。

## 4. 独立验证与复杂度

`road_validator.py` 不调用调度器：检查图索引、端点、有限非负权重、标识唯一性、
真实方向数量、同一道路的 metadata 一致性、V−1 条双向骨架覆盖、正反向可达、
物理道路配额及有向边预算。道路报告也写入场景 metadata，且不包含耗时等不确定字段。

- 配额扫描：时间 `O(min(V², max_edges))`，额外空间 `O(1)`。
- 树构建：时间和空间 `O(V)`。
- 候选节点对枚举及洗牌：时间和空间 `O(V²)`。
- 权重及边构建：时间和空间 `O(E)`。
- 独立结构验证：时间 `O(V+E+min(V²,max_edges))`，空间 `O(V+E)`。
- 道路生成总计：时间和空间 `O(V²+E)`。
- 字符串插入排序：最坏时间 `O(N²)`，返回列表空间 `O(N)`。

完整场景生成仍包含旧见证构建和 Dijkstra，不能用道路采样复杂度代表整个系统。

## 5. 可复现实验

执行命令：

```powershell
python -B scripts/experiment_v2_roads.py --output docs/experiments/v2-phase1-road-results.json
```

脚本通过 `git archive` 将基线源码读取到独立临时目录，不切换任何仓库分支，
不执行基线提供的 shell 指令。新旧版本分别在 `PYTHONHASHSEED=1、2、73` 的
独立 Python 进程中运行，比较完整场景 SHA-256。指纹涵盖节点、含 metadata 的边、
订单、车辆、配送员、仿真参数、优化参数、场景 metadata 和配送见证。
原始 JSON 保存全部指纹、源码摘要与测量值。

本次默认五个 seed 均无需改变初次采样图；旧版没有双向生成树契约，其骨架完整性
记为不适用，而不是伪造 PASS。

| seed | V | P | 双向 B | 单向 S | 有向 E | 双向比例 | 骨架 | 去程/返程 | 跨进程复现 | 道路生成 ms | 场景生成 ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| 0 | 57 | 113 | 107 | 6 | 220 | 94.6903% | PASS | PASS | PASS | 2.0468 | 6.1831 |
| 1 | 34 | 113 | 107 | 6 | 220 | 94.6903% | PASS | PASS | PASS | 1.4892 | 4.2720 |
| 42 | 50 | 113 | 107 | 6 | 220 | 94.6903% | PASS | PASS | PASS | 1.7725 | 8.9771 |
| 100 | 34 | 113 | 107 | 6 | 220 | 94.6903% | PASS | PASS | PASS | 3.5890 | 11.6226 |
| 2026 | 33 | 113 | 107 | 6 | 220 | 94.6903% | PASS | PASS | PASS | 2.6231 | 5.9065 |

目标偏差为 −0.3097 个百分点，小于 `0.5/113 = 0.4425` 个百分点的整数舍入界。
耗时为每个 seed 的一次实际测量；道路耗时包括道路验证，场景耗时包括旧业务生成；
不据此宣称性能提升。

旧版同机同脚本实测：

| seed | V | P | 双向 B | 单向 S | 有向 E | 双向比例 | 道路生成 ms | 场景生成 ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 57 | 178 | 4 | 174 | 182 | 2.2472% | 5.4470 | 15.8628 |
| 1 | 34 | 99 | 1 | 98 | 100 | 1.0101% | 2.1479 | 7.7061 |
| 42 | 50 | 153 | 4 | 149 | 157 | 2.6144% | 3.9392 | 10.5506 |
| 100 | 34 | 90 | 1 | 89 | 91 | 1.1111% | 0.9530 | 2.6569 |
| 2026 | 33 | 97 | 4 | 93 | 101 | 4.1237% | 0.7791 | 2.7748 |

旧版先构建有向环，再独立采样有向边；反向边只偶然被选中，没有控制物理道路的
双向配额，故比例约 1%–4%。新版直接在物理连接层分配 B/S，再展开为有向边，
目标比例由整数配额控制。两版拓扑、边数、随机数消耗和订单属性会变化，本实验
不能作为新旧调度算法路线质量的公平对比。跨版本相同 seed 不承诺相同场景。

## 6. 测试、拒绝实例与后续 P0

新增 `tests/test_road_network.py`：20 项 unittest，包含五 seed 和多种损坏输入的
subTest。测试先于实现创建，最初因缺少道路验证模块失败，随后逐项实现。
新增测试中还发现并修正了一个与 60 节点预算不兼容的测试夹具，以及 JSON 数组
与 Python tuple 未统一的问题；没有删除或降低原有测试。

| 检查 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_road_network` | 20 项通过 |
| 图、Dijkstra、随机生成器及 Phase 4 相关回归 | 124 项通过 |
| `python -B -m unittest discover -s tests -t .` | 最终 528 项通过，198.089 秒，退出码 0 |
| 五 seed × 三个 PYTHONHASHSEED 完整场景复现 | 新旧版本均通过；指纹见原始 JSON |
| wheel 构建、临时安装后 seed=42 生成 | 通过，道路 JSON 随包可用 |
| 新增/修改生成路径的 AST 禁用排序与算法依赖扫描 | 通过，无新增第三方依赖 |
| 实验源码 SHA-256 与最终工作区源码核对 | 通过 |
| `git diff --check` | 通过 |

全量测试中的旧 API `algorithm` 字段弃用警告属于既有兼容行为，未出现测试失败。
本阶段未改 API/前端，不重复把 Phase 0 的 UI 构建结果冒充本阶段端到端验收。

明确拒绝的输入包括：

- 60 节点、95% 双向比例、有向边上限 120：双向树及整数配额至少需 121 条边。
- 物理道路 80、目标有向边 155：应为 76 双向 + 4 单向 = 156 条有向边。
- 物理道路不足、超过完全图、非法比例/非整数/布尔数量、非法权重范围。
- 继续传入废弃的 `max_extra_edges_per_node`，或含糊的 `edge_count` 配置。

验证器能拒绝缺失骨架反向边、单向道路意外反向、方向 ID 重复、road_id 冲突及
NaN/inf/负权。指定五 seed 的本阶段道路实验没有失败实例。

**后续可行场景生成 P0（未修复）**：旧 `validator.py` 以目的地集合及
`destination_id -> order` 字典检查覆盖，会错误合并同址不同 ID 订单。
V2 Phase 3 和 Phase 4 必须逐订单 ID 验证唯一分配、恰好覆盖、容量、真实时间传播、
闭环及指标；并运行 distance、cost 两种目标的真实调度结果验证。独立验证器和
小实例穷举也必须保留订单身份，不能用“连通”替代配送可行性。

40 单默认生成的客户点数量/容量问题及旧时间上界口径同样留待后续场景阶段处理。
V1 单车辆业务接口继续兼容，不代表 V2 多车辆配送已经交付。

## 7. 实际文件清单

```text
AGENTS.md                              V1/V2 授权边界
README.md                              新报告导航及旧数据存档口径
pyproject.toml                         分发道路 JSON 默认参数
src/logiroute/
  algorithms/ordering.py               手写稳定字符串排序
  scenario_generator/
    __init__.py                        导出道路报告及配置读取接口
    config_spec.py                     物理/有向计数、预算与配置校验
    road_defaults.json                 道路默认参数
    graph_sampler.py                   双向树与物理道路采样
    road_validator.py                  独立道路结构验证及统计
    generator.py                       记录道路报告、替换旧排序
    backbone_builder.py                仅替换旧排序，保留订单业务语义
tests/test_road_network.py              20 项新增测试
scripts/experiment_v2_roads.py          隔离的新旧版本实验与复现
docs/
  architecture.md                      道路架构导航
  development-plan.md                  阶段门禁及后续 P0
  v2-phase1-road-network.md             本报告
  experiments/v2-phase1-road-results.json 真实原始测量与指纹
```

代码与测试、实验文档分别以独立 Conventional Commit 提交；最终提交 hash 及远端
核验结果见交付消息。原有 508 项测试文件未修改或删除。
