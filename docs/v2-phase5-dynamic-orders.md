# LogiRoute V2 Phase 5 — 动态订单与安全重规划

## 1. 基线、范围和入口

本阶段从 `feat/multivehicle-dynamic-orders` 的 `6ddc35c` 继续，开始时工作区干净。
实现统一订单入口、显式自动事件、仓库检查点重规划、配送执行和独立状态审计。
旧静态规划、路网生成、核心模型、FastAPI、Dashboard 均保留；Phase 6 未实施。

```python
from logiroute.dynamic.config import load_dynamic_config
from logiroute.dynamic.session import DynamicSession

config = load_dynamic_config('config/dynamic_orders.json')
session = DynamicSession(scenario, config)  # 普通 Phase 4 场景或合法固定场景
outcome = session.replan('distance')
if outcome.status == 'applied':
    session.depart()
session.step()  # 最早的一个道路到达 / 等待结束 / 服务结束 / 返仓事件
session.submit_automatic(seed=42)  # 显式一次事件，无后台循环
observation = session.snapshot().to_dict()
```

会话从新的、尚未执行的输入启动：订单必须 pending/created，车辆空载、在仓库、
状态 IDLE 或 MAINTENANCE；没有上下文的已装货/在途输入明确拒绝，不猜测货物或历史。
会话自行保存后续所有已完成配送，再规划不会丢失这些历史。尚未实现进程重启后的持久化恢复。
输入被复制，调用方修改原 Order、Vehicle 或图不会改变会话私有状态。

## 2. 统一订单入口和队列

| 操作 | 契约 |
| --- | --- |
| `submit(order, source=...)` | initial/manual/automatic 共用同一校验及入队流程；automatic 还须提供整数 source_seed |
| `submit_manual(destination, demand, start, end, ...)` | 可显式提供 ID；否则使用 JSON 前缀和会话序号分配唯一 ID |
| `submit_automatic(seed=...)` | 从 JSON 的目的地/需求/优先级/窗口分布产生一单，经同一 submit 入队 |
| `update_pending(id, priority=..., time_window_end=...)` | 先验证独立副本，再从队列移除原 ID、替换并重新入队 |
| `cancel(id)` / `expire(id)` | 显式状态事件，不依赖后台计时；取消/过期的 ID 永远不复用 |
| `next_pending()` | 返回不可变 OrderView；原队列的失效队首仍明确报错，不静默跳过 |

输入检查包含模型、有限时间值（布尔值不能冒充时间）、真实客户目的地、截止未过，
以及至少一辆未来可用车辆可以装下该单并完成去返仓的道路可达性检查。
不能用车队总容量代替单车容量。此处验证结构性单单条件，**不保证联合可行或能在当前行程服务**。
只有后续实际规划和独立验证才决定是否纳入路线。

`OrderReceipt.status='queued'` 表示已入待处理队列，不是已分配或已送达。
来源、唯一 ID、自动 seed、数量和事件时间留在记录中。相同 seed 的自动事件还取决于
同一配置、初始图、业务时钟和已占用 ID 序列，不宣称脱离会话上下文仍有相同 ID。

全部原始单笔需求由 Decimal 模型保存。JSON 先 parse_float=Decimal，载荷累计、
装载和扣减仅用 exact_sum/exact_difference；不经 float 中间求和，不用 epsilon。
JSON 导出是明确边界，数量使用十进制字符串。几何/时间仍为既有浮点标量。

队列复用 Phase 2 手写有序数组，仅新增 `snapshot_ids()` 只读观察接口：返回记录的
原 ID、顺序和失效项，不出队、不改状态、不修复失效队首。原有排序和复杂度契约保留。

## 3. 生命周期与安全检查点

沿用既有枚举、默认 pending 及迁移表，没有新增互相矛盾的状态：

| 原状态 | 本阶段允许的操作 / 新状态 |
| --- | --- |
| created | 接受时显式转 pending；原输入对象不变 |
| pending | 规划成功 → planned；显式取消 → cancelled；截止已过且显式 expire → expired |
| planned | 成功替换前内部撤回 pending，再变 planned；取消/过期会撤回整个尚未出发计划 |
| planned | 仓库实际装载并出发 → in_transit |
| in_transit | 完成该订单服务并精确卸货 → delivered；不允许取消/过期丢掉在车货物 |
| delivered / cancelled / expired | 终态，不能重用 ID、重新入队或再次分配 |

取消一个 planned 订单会明确使原计划失效，其余 planned 订单退回 pending 请求重规划。
这与普通新增导致的重规划失败不同：后者保留原有效计划。
expire 只有显式调用且 `current_time > time_window_end` 才生效，不自动计时。
窗口限制服务开始，服务结束可以晚于窗口末端。

首版只在**本批所有执行车辆均完成返仓后**应用下一份全局计划；不把一辆正在配送的车
改装成空闲仓库车辆。仍在执行时请求规划返回 `deferred`，新订单保持 pending。
不做行程中途补货、跨车交接或在途路线替换。一次行程结束后，可以显式派出下一批
动态订单；这不是修改静态 VRP 去优化多趟补货。

## 4. 草案、原子替换和失败回退

```text
prepare_replan(objective):
    要求没有活动执行程序，车辆实际空载在各自仓库
    保存 revision，构造隔离的普通 ScenarioBundle
    只取 pending/planned；在副本中撤回 planned → pending
    initial_time = 当前业务时间；不修改真实车辆位置或载荷
    复用 plan_fleet，保存输入指纹、目标及结果，检查规划没有修改输入
    返回不可变 ReplanProposal，不改当前计划或订单

commit_replan(proposal):
    核对 revision、输入指纹、请求目标及安全检查点
    用原独立 validate_fleet 重新验证，忽略结果自带的成功标记
    非法结果 / 陈旧草案：抛出明确错误，保留当前状态
    valid 但 partial：返回 incomplete 及完整未服务原因，保留原计划及其 planned 状态
    valid 且 complete：发布新 planned 状态和计划，清空已分配待处理队列
    revision 前进；保存成功计划历史和 plan_applied 清单
```

`replan()` 是显式便利入口；没有偷偷增车、改需求、宽限截止或调用生成器重新造订单。
新订单造成联合容量冲突时，调用方可以继续执行保留下来的有效原计划，新增订单仍在队列。
如果原本没有有效计划，incomplete 不会凭空产生一份可发车计划。

业务时钟推进会使尚未出发计划的旧出发时刻失效；`needs_replan` 会反映这一点，
`depart()` 拒绝把过时计划自动平移。取消一个无关 pending 订单也不能掩盖这种失效。
原计划即使仍留作历史，也不等于仍可发车。

revision 检查用于显式事件交错及陈旧草案，不是任意并发写安全承诺。
会话要求单一所有者；所有观察均为 frozen/slots DTO 和 tuple，避免把可变排队订单暴露出去。

## 5. 实际执行、位置和独立审计

`depart()` 先再次独立核验计划，逐车在仓库装载清单中的全部原始需求，订单变
in_transit，车辆/配送员变配送中。排队新增订单不会被装上在途车辆。
编译器只把已验证静态路线展开成事件，不新增最短路径算法或改写闭环 RoutePlan。

事件按 `(结束时间, 车辆ID, 该车动作序号)` 手写逐字段比较并线性取最小，禁止现成堆/排序。
每个事件包括：实际整段道路到达、等待结束、逐订单服务结束、最终返仓。
同址多个订单仍有多个服务 ID，可能共享一次节点访问。

`current_node_id` 是最后确认到达的节点。在整段行驶期间，观察同时提供 action_kind、
action_start/end、in_flight_path 和全局业务时间，明确车辆在该实际路径上，不能把该节点
误读成车辆仍可从仓库装货。不声称提供实时 GPS 或中间道路点插值。

`step()` 推进一个最早事件；`advance_to(t)` 先执行所有到期事件，再推进业务时钟。
不允许时间倒退，不使用 sleep，不读取墙钟作为配送时间。
服务完成按订单 ID 卸货且只执行一次；所有货物送完后车辆为 RETURNING，返到本仓且
载荷为零后才变 IDLE，配送员同时空闲。

`dynamic.validator.validate_dynamic_snapshot(graph, snapshot)` 是另一套事件审计，
不导入会话或事件编译器。它从原图、装载清单和完整事件序列重建：

- 初始/新增订单身份、来源、数量及自动 seed，合法生命周期和终态。
- 每辆车的出发清单、订单唯一归属、逐次 Decimal 扣货和真实剩余载荷。
- 实际路径每条道路的存在与方向，distance/travel_time/cost 和行驶时刻。
- 等待、服务开始时间窗、服务时长、返仓、当前位置及车辆/配送员状态。
- pending 队列完整分区和优先级顺序、planned 分区、in_transit 载货清单与重规划标记。

合法的动态观察可以有 pending 订单；审计 valid 不等于“所有订单已经送达”。
计划的可行性仍由原静态独立验证器证明，实际执行状态则由事件审计另行复核。

## 6. 数据结构、文件与复杂度

| 文件 | 职责 |
| --- | --- |
| `dynamic/config.py` | 独立 JSON 自动订单分布与默认目标，无损数量读取 |
| `dynamic/models.py` | 不可变订单/车辆观察、事件、草案、结果和快照 |
| `dynamic/session.py` | 订单注册表、手写队列、修订号、计划、执行游标和历史的单一所有者 |
| `scheduling/algorithms/dynamic_execution.py` | 编译固定路线、线性比较下一事件 |
| `dynamic/validator.py` | 原图与事件/清单的独立重演 |
| `algorithms/order_queue.py` | 只增加只读 snapshot_ids，原派单行为保留 |

字典保存所有订单（终态也保留，保证 ID 不复用）、车队、清单和执行游标，平均 O(1) 检索。
tuple 保存已验证路线和观察；列表追加事件及成功计划历史。课程小车队使用 O(K) 事件扫描，
无需引入新堆。原手写优先数组保持 priority/deadline/ID 的顺序。

记 N 为累计订单，Q 为 pending 数，M 为检查点未完成订单，K 为车辆数，G=V+E，
D 为十进制对齐精度，H 为事件数，J 为所有装载清单 ID 总数，L 为实际行驶路径边总数。

- 直接 submit：O(K²+KG log(V+1)+Q+D)；包括手写车辆排序、逐车去返仓路径和入队。
  手动分配 ID 另有最坏 O(N) 冲突扫描；自动抽样全部客户时另有 O(V²) 手写排序。
- 更新队列键：O(Q+D)，原对象移除后才替换并重新入队。
- 取消/过期：复制注册表、必要的计划撤回和重建队列，O(N+MD+Q²)。
- prepare：原 Phase 3 静态规划复杂度加隔离副本/历史过滤 O(N)，不是把新单单独规划。
  commit：另一次独立验证（部分结果也含失败插入核验）及 O(N+MD) 状态发布。
- 一条路线编译：Time/Space O(访问数+服务数)，实际路径使用不可变引用。
- step：O(K+R+D)，R 为该车剩余清单长度；advance_to 执行若干这样的事件。
- snapshot：手写排序 O(N²+K²)，另有事件/计划引用复制；JSON 导出再计全部记录、
  路径和十进制文本大小，不能当 O(1)。
- 独立审计保守时间 O(N+K+HN+KJ+(H+J)D+L)。计划/撤回事件扫描状态，
  每次出发还检查其他清单，因此不能声称简单线性。工作空间 O(N+K+D)，
  另计违反项报告输出。实验每个执行事件都审计一次，所以累计审计可能呈二次增长。

保存完整事件与成功计划历史使空间随会话增长，不承诺恒定内存；没有无限后台生成。
ID 文本长度与字典最坏情况成本应另计，以上采用常见平均字典访问界。

## 7. 测试与真实实验

新增33项测试，原695项测试和断言保留：

```text
tests/test_dynamic_orders.py              27项入队、生命周期、回退、陈旧草案、篡改和载荷测试
tests/test_dynamic_queue_view.py           1项只读队列契约
tests/test_dynamic_networks.py             2项真实路网/双目标两批执行及独立性测试
tests/test_dynamic_config.py               2项精确 JSON 和参数边界
tests/test_dynamic_reproducibility.py      1项三进程完整状态/回退轨迹复现
```

计数以最终 unittest 记录为准，各组回归有交叠，不能相加推算全量数量。
所有新增入口先有红测试；联调发现以下边界也先复现后修复：时钟导致计划失效但标记未更新、
取消无关 pending 清掉失效标记、自动 seed 未记录、草案目标不一致、时间布尔值被当数字、
入队记录或空闲配送员被篡改未拒绝，以及非有限容量导致审计异常。

[正式实验 JSON](experiments/v2-phase5-dynamic-results.json)记录五 seed
0/1/42/100/2026 × distance/cost，共10个正常会话。每个原图对象供两种模式共用，
各会话复制自己的可变状态，避免两个目标各自生成不同输入。
实验 JSON 在会话创建前将自动窗口跨度设为1000到2000，手动窗口跨度10000；
这是固定实验输入，不是在失败后放宽。默认自动分布100到200不承诺所有新单联合可行。
每个会话初始5单，在途再加入1张手动单和1张显式自动单，先 deferred，返仓后规划新批次。
共70/70单送达；每个执行事件均通过独立审计，第二份计划恰好包含新增2单。
JSON 保存66个里程碑快照、全部执行事件及成功计划历史。

两个额外容量冲突对照分别使用 distance/cost：一车容量1，原订单需求1，新增需求1。
合并重规划实际只服务1/2，返回 valid/partial；原完整单单计划保持不变，先完成原单，
返仓后再服务新单。各对照最终2/2，未把部分结果冒充完整，也未为失败方案改容量或订单。
这4单不混入上述70单的正常矩阵统计。

每个 hash seed=1/2/73 的独立进程重放同样10个正常会话和2个回退对照，
只移除 runtime_seconds / validation_seconds 测量字段，其余初始图、订单、载荷、
业务时间、事件、队列、成功计划及回退历史均一致；SHA-256 均为
`8a8b26c198be8af75a44b1222332104b607e5ab656f159a81041c9b8e1c8c273`。

正式实验总耗时4.355324秒，含源场景生成、动态流程和三进程复现；
其中跨进程部分3.557676秒。逐会话 runtime_seconds 从共有输入准备好后开始，
包括会话、规划、执行和逐事件审计；静态规划自身的统计也保留，不能混为纯算法提速。

`-initial.json` 保留初次测量；`-before-shared-input.json` 保留复杂度注释修正后的测量。
最终修正了实验中两个目标复用同一初始对象的组织方式并重新测量。
三份记录除测量/源码摘要外，所有实际状态、路线和历史一致；最终文件含10个当前源码/配置摘要。

## 8. 验收、Git 与停止边界

[完整验收记录](experiments/v2-phase5-acceptance.json)保存定向、相关回归和全量的原始输出，
全量期间临时保持系统唤醒并在 finally 恢复，不修改测试期限或断言。

| 检查 | 通过 / 失败 / 错误 | unittest 秒 | 外层实耗秒 | 退出码 |
| --- | --- | ---: | ---: | ---: |
| 新增测试 | 33 / 0 / 0 | 5.279 | 5.819617 | 0 |
| 相关回归 | 206 / 0 / 0 | 0.766 | 1.252665 | 0 |
| 全量第一轮 | 728 / 0 / 0 | 210.363 | 211.603943 | 0 |
| 全量第二轮 | 728 / 0 / 0 | 203.060 | 204.708644 | 0 |

13个新增/修改 Python 文件的禁用依赖及内置排序扫描通过；原695项测试文件及断言
保留。唯一修改的既有算法文件是队列的只读观察方法；图、Dijkstra、核心模型、
静态调度、场景生成器、API/UI、pyproject 均与基线一致。完整差异和 `git diff --check` 通过。

复现（PowerShell，仓库根目录）：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest tests.test_dynamic_orders tests.test_dynamic_networks tests.test_dynamic_reproducibility
python -B -m unittest discover -s tests -t .
$replayOutput=Join-Path $env:TEMP ("logiroute-dynamic-"+[guid]::NewGuid().ToString()+".json")
python -B scripts/experiment_v2_dynamic.py --output $replayOutput
git diff --check
```

交付文件：上述模块和测试、`config/dynamic_orders.json`、`config/dynamic_experiments.json`、
`scripts/experiment_v2_dynamic.py`、三份原始实验、验收记录、本报告与 README/架构/阶段约束导航。
提交按实现与回归、实验、文档分开，最终 hash 和远端状态在交付消息实查报告。

当前限制：全车返仓检查点会推迟在途新任务；不做行程中插入、实时交通扰动、实时 GPS、
跨车交接、后台无限生成、任意并发写或重启恢复。动态输入可能联合不可行，必须读取
queued/deferred/incomplete/applied 结果；合法动态快照不等于所有订单都已完成。
main、Dashboard 分支与真实道路 stash 保留。完成 Phase 5 后停止，不进入 Phase 6 API/UI 集成。
