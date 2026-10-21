# LogiRoute V2 Phase 3 — 静态车队全局可行插入与独立验证

本报告对应用户正式批准的 Phase 3；不包含 Phase 4 生产可行场景生成闭环、
动态执行、API、Dashboard 或真实道路改造。以下实验为真实运行，设计局限另列。

## 1. 基线、计时修复和测试证据

起始分支 `feat/multivehicle-dynamic-orders`，HEAD
`1efaa731d13494691190fdf03ca28c0d73d4eee0`，工作区干净且远端同步。
只读审计曾实跑 609 项，241.565 秒，因旧 NN 的 `runtime_seconds=0.0` 失败一项；
本机 Python 3.12.10 的 monotonic 是 GetTickCount64，分辨率 15.625 ms；
perf_counter 是 QueryPerformanceCounter，分辨率 1e-7 秒。

3A0 先加回归：模拟粗时钟不动、精时钟前进 125 ns，旧代码实测失败后仅将
旧 planner 两处计时及说明改为 perf_counter。不睡眠、不填充假耗时、不改变原断言。
新增回归和原计时断言连续 20 轮，共 40 次通过，实耗 8.939894 秒。
之后代码保持不变，连续两轮完整测试通过，才进入 3A。

| 检查 | 实测结果 |
| --- | --- |
| 3A0 全量第一次 | 610 项，194.647 秒，OK |
| 3A0 全量第二次 | 610 项，192.634 秒，OK |
| 3A 模型与相关旧回归 | 83 项，0.018 秒，OK |
| 3B 路径、插入与相关旧回归 | 94 项，0.227 秒，OK |
| 3D 独立验证与相关旧回归 | 101 项，0.194 秒，OK |
| 3C 调度及相关旧回归 | 103 项，55.618 秒，OK |
| 车队、边界、穷举、跨进程定向测试 | 64 项，2.466 秒，OK |
| 首次最终回归（失败现场保留） | 674 项，1060.724 秒，673 通过 / 1 error，退出码 1 |
| P0 定向连续复验 | 原 seed=42 测试连续 3 次通过，30.437 秒，6 个真实子进程指纹一致 |
| P0 原命令不插桩复验 | 1 项通过，外层实耗 9.818976 秒，退出码 0 |
| P0 相关图 / Dijkstra / 场景 / 规划回归 | 135 项，3.874 秒，退出码 0 |
| P0 后全量第一次 | 674 项，184.553 秒，外层实耗 186.447386 秒，退出码 0 |
| P0 后全量第二次 | 674 项，179.180 秒，外层实耗 181.034327 秒，退出码 0 |

原 609 项测试文件及断言全部保留，未添加 skip。既有 API algorithm 字段弃用提示仍在。
各组定向测试有交叠，不能相加推算全量项数。

首次最终回归的错误是测试期间合盖待机约 833.822 秒，超过原 180 秒预算。
CPython Windows 最终等待层把剩余预算 -666.25 秒写入 TimeoutExpired；
不是调用方传入负数。原始完整 traceback、系统事件及可控复现见
[P0 诊断](v2-phase3-timeout-diagnosis.md)和
[验收原始记录](experiments/v2-phase3-acceptance.json)。修复执行环境后连续全量复验；
正式源码和原跨进程测试均零修改，不加大期限、不吞错、不替换场景输出。

复现命令（仓库根目录 PowerShell）：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest tests.test_planning_clock
python -B -m unittest tests.test_fleet_types tests.test_fleet_paths tests.test_fleet_insertion
python -B -m unittest tests.test_fleet_validator tests.test_fleet_greedy tests.test_fleet_audit
python -B -m unittest tests.test_fleet_exhaustive tests.test_fleet_reproducibility
python -B -m unittest discover -s tests -t .
$replayOutput=Join-Path $env:TEMP ("logiroute-fleet-"+[guid]::NewGuid().ToString()+".json")
python -B scripts/experiment_v2_fleet.py --output $replayOutput
git diff --check
```

## 2. 对象、接口与数据结构

公开入口：

```python
from logiroute.scheduling import plan_fleet
result = plan_fleet(scenario, objective="distance")  # 或 cost；travel_time 拒绝
payload = result.to_dict()  # 载荷字段在此边界转 Decimal 字符串
```

| 对象 / 模块 | 实际职责、结构与理由 |
| --- | --- |
| FleetInput / fleet_paths | 用原 core 构造器复制图及业务数据，需求/容量读取 *_decimal；不经旧 float DTO 重建。局部 ID 字典支持平均 O(1) 检索 |
| PathClosure | 同次调度全车共享的 `(source,target) -> FleetLeg/不可达` 字典。内部只调用原 PathProvider 单源批量查询，不重写最短路 |
| FleetVisit | frozen tuple：节点 ID + 有序订单 ID 元组；一访多单、重复访问均可表达 |
| FleetLeg | 原图上的有向道路节点元组和三项有限非负指标；不暴露可变 cross_metrics 字典 |
| FleetService | 每单服务事件：ID、访问/服务序号、到达、等待、开始、结束、Decimal 剩余货物 |
| VehicleRoutePlan | 车/配送员/本仓、visits/legs/services、精确容量及初始装载、出发/返仓、三指标 |
| FleetScheduleResult | 按车路线、未服务单及原因、不可用车辆及原因、选择轨迹、统计、输入指纹和独立报告 |
| FleetValidationReport | valid 与 complete 分开；不能以合法部分结果宣称全覆盖 |

公开结果使用 frozen dataclass、slots 和元组；数量是 Decimal。全局指标由最终每车
路线报告汇总，并由验证器从真实道路独立核对，不把候选增量累加当最终指标。
结果构造拒绝非有限全局总量、可变嵌套记录及矛盾的成功标记。

复用 Phase 2 的手写有序数组队列构造初始任务扫描顺序：入队 O(M)，总建队
O(M²)，查看 O(1)，出队摊还 O(1)，空间 O(M)。随后扫描所有活跃任务，
使用 ID 集合仅做成员判断，不从 set 遍历顺序决定候选。
无需链表、第三方队列、内置排序或新算法依赖。

## 3. 业务与兼容契约

- 只接纳 IDLE、精确物理载荷为零、位于真实仓库的车，且其唯一绑定配送员必须 IDLE。
  不可用车列出原因，不伪造路线。可用闲置车为 `(depot,depot)` 零行驶闭环。
- 只规划 pending。其他状态仍进入完整订单结果分区，原因 order_not_pending；
  不自动撤回 planned、不恢复终态、不修改输入订单、车辆或配送员。
- 原始订单 ID 唯一；同址不同 ID 不合并。覆盖分区以全部提交订单为准。
- 窗口末端限制服务开始，允许服务完成晚于末端；新入口严格比较窗口，不加 epsilon。
  旧 V1 容差不变。等待从该任务就绪时刻计算，同访后续任务承接前单服务结束。
- 一次出仓装载分配给该车的全部货物；逐车初始载荷 <= 容量。交付按 ID 扣减；
  释放空间不意味着补货，不支持跨车交换或途中装货。
- 每车回自己的出发仓库；初始业务时间来自现有全局 simulation.initial_time。
  当前模型没有返仓截止字段，报告 return_deadline_checked=False，不编造营业期限。
- 当前仅使用主目标对应的规范最短路径；其行驶时间来自同一路径实际边权。
  不借用另一条最快路径的时间，不枚举替代道路，不做全局回溯。
- 原 plan_deliveries、RoutePlan、ScheduleResult、API 和前端结构保留。
  旧 planner 唯一生产行为改动是计时精度；新入口独立命名，不包装 K 次旧单车调度。

输入快照只复制参与规划的字段，不把无关 metadata 当业务语义。原输入在调用期间
禁止并发修改；快照前后及规划完成时核对指纹，检测到变化明确拒绝。私有图确保
后续候选不读到外部边权变更；旧 PathProvider 本身不因此获得自动失效能力。

## 4. 全局贪心、目标和时间传播

两种模式使用同一个流程，仅切换 distance/cost 主目标：

```text
J_distance = 所有车辆实际闭环道路边的 distance 之和
J_cost     = 所有车辆实际闭环道路边的 cost 之和
delta      = 受影响车插入后完整闭环主目标 - 插入前完整闭环主目标
```

候选比较明确按八字段升序，手写逐字段比较：

```text
(priority_rank, time_window_end, delta_main_objective,
 vehicle_id, order_id, candidate_kind, visit_index, service_index)
```

urgent=0、normal=1；candidate_kind=0 表示同址访问内增加服务，1 表示新增节点访问。
ID 使用显式字典序平局规则，不把枚举字符串当业务等级；无加权和、无隐式排序。
优先级是候选接纳/分配优先级，**不保证各车实际服务时刻服从全局优先级顺序**。

```text
校验输入，复制精确业务快照，构造主目标共享闭包
为每辆可用车创建空闭环
使用现有队列获得 pending 扫描顺序，其余单保留状态原因
while 仍有未分配 pending:
    best = 无
    对全部活跃订单、全部可用车辆：
        枚举每个新增节点位置，以及已有同址访问的每个服务位置
        严格检查该车全部分配订单的 Decimal 总载荷
        重新推演该车从出发到返仓的整条路线
        仅完整可行的候选参与八字段比较
    没有 best：结束；保留最后一轮失败原因
    否则原子接纳一张订单，登记唯一车归属
汇总最终真实路线指标，调用独立验证器后返回
```

每次接纳一张新订单，最多 M 轮。当前无可行候选的 urgent 不阻塞其他订单，
也不会提前永久丢弃；下一轮重试，最后才形成未服务记录。

每车候选重演：

```text
initial_load = exact_sum(每张已分配订单原始 demand_decimal)
严格比较 initial_load <= capacity_decimal，构造 DeliveryLoadState
clock = initial_time
每个下一访问：
    查当前主目标闭包中的真实有向路径；不可达则拒绝
    arrival = clock + 该路径 travel_time
    按访问内服务顺序：
        start = max(clock, arrival, window_start)
        检查 start <= window_end
        end = start + service_time
        检查时刻有限，按 ID 扣载，clock = end
    实现中 clock 在到达时已先更新为 arrival
最后访问是本车仓库，检查返程可达，记录真实返仓时刻
```

新增插入可能延误原已分配订单，因此不能只检查新单或三条局部边。
所有出仓、途中、返程边均计入距离、成本和行驶时间；等待与服务时间单独保留。

## 5. 独立车队验证

依赖顺序先实现 fleet_validator，再接入 fleet_greedy。验证器不导入候选模块或
贪心模块，不调用 assess_route；恶意测试把 assess_route 换成必抛异常的函数，
独立验证仍通过手工正确见证。

验证器从原输入另建快照和 PathProvider，独立执行：

1. 全输入 ID、服务/未服务互斥分区、跨车唯一归属。
2. 各车与配送员的原始可用性、绑定及本仓闭环，全部车辆都有路线或不可用原因。
3. 访问中的订单 ID 与实际事件逐一对应，目的地、访问序号及同访内序号正确。
4. 每条上报路径的所有真实边、方向与端点，逐边重新累加三指标。
5. 用原 Dijkstra 核验主目标最短路径；允许等主目标的不同真实路径，但时间从
   上报实际道路重新计算，不能相信上报 cross_metrics 或总量。
6. 用原始需求独立计算逐车 Decimal 总量及扣载，重新传播等待、服务、返仓。
7. 对比上报每单、每车及全局的时间、载荷和指标。
8. 对未服务单独立枚举最终路线的插入位置，核验确无当前可行插入，并检查原因集合。
   此处使用验证器自己实现的时间重演和位置枚举，不调用规划器相应函数。

因此最终部分结果的验证比原设计中仅重算最终路线更贵，复杂度已修正。
它证明的是本次静态闭包及最终路线下的插入失败，不证明不存在重新分配后的全覆盖解。

valid 与 complete 独立：合法部分结果是 valid=True/complete=False；
status=invalid 的结果不能被描述为启发式搜索失败；未验证也不标成功。
search_outcome 只会返回 full_plan_found、heuristic_incomplete、invalid_result 或 unverified。

## 6. 与实际实现一致的复杂度

记 G=V+E，M 为订单数，K 为车辆数，U 为不同仓库/目的地数，P<=U²，
D 为载荷对齐十进制精度，L 为最终道路路径展开总长度。

原 Dijkstra 使用索引式手写二叉堆，每节点至多一个堆条目，trace=False：
时间 O(G log(V+1))，辅助空间 O(V+最大出度)，保守 O(G)。
不走 trace 中的历史诊断排序。

指纹使用手写插入排序建立规范记录，单次成本不能当 O(G)：

```text
F = O(V² + M² + K² + sum(out_degree²) + E + (M+K)D)
```

原 PathProvider 缓存键含完整图指纹元组，其哈希 O(G)；批量结果每对最坏需
O(V) 路径回溯和三指标计算。因此共享闭包时间为
O(U G log(V+1) + P(G+V))，空间 O(PV+G)。建好后局部表平均 O(1) 查询。

车辆已有 r 张订单时，新访问和同址服务插入共有 O(r+1) 个位置。
单个候选的复制、精确载荷计算和完整时间重演为 O((r+1)(D+1))，
空间 O(r+D)；候选不重复拼接全部道路节点，只引用闭包路径。

已接纳 t 单的一轮扫描：

```text
O((M-t)(D+1) * sum_v((r_v+1)²))
sum(r_v)=t，所以 sum((r_v+1)²) <= t²+2t+K
```

全调度最坏时间：

```text
O(F + U G log(V+1) + P(G+V) + (M⁴+KM²)(D+1))
```

队列总 O(M²) 已被覆盖。仅保存当前最佳候选，不存全部候选方案。
最后独立验证另建闭包，全覆盖结果成本为
O(F+U G log(V+1)+P(G+V)+L+MD)；
部分结果核验失败插入再加 O((M³+KM)(D+1))。不能忽略这部分时间。

总空间保守为 O(G+PV+(M+K)V+(M+K)D+MK)，含完整输出路径、服务记录和失败证据。
字典查询按平均情况声明，ID 长度和标量位数成本不假定绝对常数。

## 7. 实际固定、穷举与随机实验

原始结果在 [v2-phase3-fleet-results.json](experiments/v2-phase3-fleet-results.json)。
包含输入指纹、逐车访问/道路/服务/Decimal 载荷、未服务原因、统计与真实耗时；
十个源文件/配置 SHA-256 对应生成时当前工作区字节。

### 7.1 固定生产规模配置

读取未改动的 config/scenario_fleet.json：35节点、192有向边、20订单，
V1容量100位于W1，V2容量120位于W2，绑定D1/D2。两种目标使用同一输入快照。

| 目标 | 服务 | 验证 | 距离 | 行驶时间 | 成本 |
| --- | --- | --- | ---: | ---: | ---: |
| distance | 20/20 | valid、complete | 65.887 | 203.678 | 102.343 |
| cost | 20/20 | valid、complete | 72.041 | 228.031 | 78.573 |

表中仅展示四舍五入的小数；原始浮点量、路线及每车载荷保留在 JSON。
生产容量判断没有任何此类舍入。

### 7.2 固定接受与恶意篡改

test_fleet_greedy 覆盖一车一单、多车争单、全局增量、一访多单、等容量、
跨车分担、异构容量、去程可达而返程不可达、过紧窗口、等代价平局、双目标异车、
不同仓库、空订单、重复ID、非pending状态、零需求、1e-40超载、不可用车和输入排列。
基础三节点夹具每边三指标为1：单单闭环三指标各2，合并两单访问不同点各3，
容量迫使两车分担各4；同址两单行驶各2但分别服务，返仓时刻4。

test_fleet_validator 使用手写见证，不以调度器输出生成正确答案，篡改 ID、
跨车归属、访问位置、道路方向/缺边/非最短路径、容量、初始与剩余载荷、
到达/等待/服务/返程、三指标、未服务原因、来源指纹与伪造成功标记。
验证器拒绝遗漏一条可用车路线，以及明明可插入却声称容量不足的部分结果。

### 7.3 独立穷举反例

scripts/fleet_reference.py 手写递归分车和排列，使用原 Dijkstra；不导入贪心、
候选或车队验证模块。每个完整有序分配组合都独立计算精确容量和时间窗。
M<=6、K<=2，组合数 M! * C(M+K-1,K-1)，不是生产调度策略。
若计入 Python 切片式排列生成器递归栈，穷举辅助空间保守为
O(M²+K+U²V)，而不是将排列栈视为 O(M)；路径闭包构造成本另计。

JSON 固定反例：两车容量各10，六单同址，需求依ID为6、5、3、2、2、2。

| 目标 | 枚举组合 | 全覆盖可行组合 | 完整最优主指标 | 贪心服务 | 贪心验证 |
| --- | ---: | ---: | ---: | --- | --- |
| distance | 5040 | 216 | 4 | 5/6 | valid、partial |
| cost | 5040 | 216 | 4 | 5/6 | valid、partial |

完整见证：V1分O1/O4/O5=10，V2分O2/O3/O6=10。
贪心留下各车1单位空余，最后2单位订单无法插入；没有把失败写成“无解”。
部分路线与完整路线指标不用于直接宣称质量提升。穷举结论仅覆盖规范主目标路径域。

### 7.4 可复现随机矩阵

config/fleet_experiments.json 明确配置：seed 0/1/42/100/2026，订单5/10/20，
车辆2/4，目标distance/cost，共60次调度；固定40节点，物理道路113、有向边220，
双向道路107，比例107/113。规模与比例来自每次原始道路报告，不是伪造常量输出。

现有生成器仍单车。实验先生成其原始场景，再根据 JSON 构造标记为
derived_fleet_research_fixture 的车队研究夹具；这不是生产多车生成器或Phase4闭环。
各目标共用同一场景对象，执行前后指纹核验一致；没有按目标分别生成场景。

| 模式 | 次数 | 合法 | 全覆盖 | 部分 | 服务/提交 | 规划秒合计 | 独立验证秒合计 |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| distance | 30 | 30 | 30 | 0 | 350/350 | 2.061578 | 0.321320 |
| cost | 30 | 30 | 30 | 0 | 350/350 | 2.248490 | 0.309102 |

耗时为一次真实同机运行合计，不宣称普遍性能提升，不预估大规模耗时。
规划秒包含快照/闭包/候选；验证秒单列，total_call_seconds另记录整体调用。
PathProvider缓存计数与局部path_table_hits分开，不能把表命中当Dijkstra调用减少的估计值。

另在 PYTHONHASHSEED=1、2、73 三个独立进程中，每进程运行五seed×双目标，
共30次复现调度；去掉两个耗时字段，其余输入、路线、载荷、验证及计数完全一致，
SHA-256 均为 a453c841c8c9b34d4907e3f69cd174703dfcba2ffb9035e78194c966ea681362。

P0 诊断后再次把完整实验输出到独立临时文件，未覆盖本节原始 JSON。
去除明确的实测耗时字段后，新旧全部记录逐项相同，十个源码摘要匹配；
60 次矩阵与固定实例均重新独立验证通过，5040 / 216 / 贪心5单的反例口径不变。
这些复验不计入原60次样本，不用新的耗时覆盖原测量值。

## 8. 失败记录、审计与已验证边界

每个新模块先有红测试再实现；发现以下边界后也先复现，再最小修复：

- 快照中若先复制车容量再捕获指纹，期间变更可能漏检；现在先捕获再复制，测试注入
  容量变更时明确拒绝。禁止将此检查当作支持任意并发写或可检测所有ABA变更的锁机制。
- 冻结外层结果还不足以禁止嵌套list；构造时检查嵌套元组、轨迹类型和指纹类型。
- 每车指标有限但全车相加仍可能溢出；全局结果现在明确拒绝，不能输出Infinity。
- invalid与heuristic_incomplete不是一回事；状态、搜索结果和验证违反项不能矛盾。

禁用依赖/内置排序检查、原测试不变检查、源码摘要及完整diff审查见最终交付门禁。
图容器、Node/Edge、堆、Dijkstra、原PathProvider、Phase2载荷及队列、生产生成器、
固定配置、API、Dashboard、pyproject均保持原样。没有新增第三方依赖。

## 9. Git、文件清单与停止边界

依次完成并推送：

- 73b160e — 3A0，高精度计时与回归。
- 10033d0 — 3A，车队结果契约。
- 0438351 — 3B，私有快照、共享路径及插入评估。
- 6a9e842 — 3D，独立验证器。
- 79cfca0 — 3C，全局可行插入与入口。
- b25f0d6 — 3E边界审计修复；未改旧断言。
- 最后实验/文档提交的hash及远端、清洁状态在交付消息实查报告，避免文档自引用未生成的hash。

```text
src/logiroute/scheduling/
  planner.py                         修改：仅V1计时器与说明
  __init__.py                        修改：保留旧入口，新增plan_fleet
  fleet_types.py                     新增：不可变结果、精确序列化及状态
  fleet_paths.py                     新增：输入规范快照和闭包
  fleet_validator.py                 新增：独立道路/时间/载荷/覆盖/失败证据
  fleet_planner.py                   新增：统一静态入口及验证装配
  algorithms/fleet_insertion.py      新增：两类位置、八字段比较及整车重演
  algorithms/fleet_greedy.py          新增：全车全单全位置扫描
tests/
  fleet_fixtures.py                  新增：小规模内存夹具
  test_planning_clock.py             新增：计时精度回归
  test_fleet_types.py                新增：结果契约
  test_fleet_paths.py                新增：快照、绑定、可达与一致性
  test_fleet_insertion.py            新增：时间窗、Decimal、同址服务、比较
  test_fleet_validator.py            新增：手写见证与恶意篡改
  test_fleet_greedy.py               新增：固定接受实例及兼容
  test_fleet_audit.py                新增：输出边界与比较优先序
  test_fleet_exhaustive.py           新增：独立最优基准与失败反例
  test_fleet_reproducibility.py      新增：随机夹具及跨进程复现
config/fleet_experiments.json        新增：研究矩阵、异构车队及反例参数
scripts/fleet_reference.py           新增：仅研究用独立手写穷举
scripts/experiment_v2_fleet.py        新增：实际计时、双目标对比和复现
docs/experiments/v2-phase3-fleet-results.json 新增：完整原始证据
docs/experiments/v2-phase3-acceptance.json 新增：P0 原始失败与复验记录
docs/v2-phase3-timeout-diagnosis.md   新增：待机事件、异常机制与环境修复
docs/v2-phase3-fleet-scheduling.md    新增：本报告、复杂度、答辩依据
README.md / AGENTS.md                修改：导航与本次正式授权
docs/architecture.md / development-plan.md 修改：新调用链和后续门禁
```

保护引用保持：main=9944147，Dashboard=eb6fee0，真实道路stash=15964cc。
没有新建/切换分支、合并main、强推或重写历史。

已经验证：指定固定实例、60次随机研究运行、30次独立进程复现、极小穷举域、
恶意篡改拒绝、精确载荷及原有回归。仍不成立的承诺：全局最优、所有随机输入
均能全覆盖、任意并发写安全、替代道路空间内无解证明、生产多车生成保证。

Phase4只建议后续将候选场景→双目标实际调度→独立全覆盖验证→有限拒绝重试串成
生产闭环，必要的修复/回溯另行设计并授权。本次未实施该闭环，也未改变API、UI
或动态执行流程，Phase3交付后立即停止等待审查。
