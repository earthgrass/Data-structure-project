# LogiRoute V2 Phase 4 — 可配送多车场景生成

## 1. 授权、基线与保证范围

本阶段从 `feat/multivehicle-dynamic-orders` 的 `c428ac2` 继续。
开始时工作区干净；暂停及恢复期间保留了全部未提交实现和实验 JSON。
本次只新增静态多车生成入口，不改 API、Dashboard、动态订单或既有调度算法。

`generate_fleet_scenario(config, seed=...)` 的成功返回表示：

1. 返回的道路网络通过原双向道路结构验证。
2. 有逐车、逐订单的 distance 和 cost 两份完整可行见证，并通过独立验证。
3. 对同一份最终输入实际执行 `plan_fleet(distance)` 和 `plan_fleet(cost)`，
   两种结果都经独立重新核验，合法且完整覆盖全部订单 ID。

生成可能失败。有限尝试耗尽后抛出 `FleetGenerationError`，保留全部尝试；
不返回一个被标成成功的部分结果。失败不证明原候选无解，也不证明配置永远不能生成。
生产入口的逐次验收保证与实验中某个样本集合的成功率是不同命题。

## 2. 接口、配置和对象

```python
from logiroute.scenario_generator import (
    load_fleet_generator_config, generate_fleet_scenario,
)

config = load_fleet_generator_config('config/fleet_generator.json')
generated = generate_fleet_scenario(config, seed=42)
scenario = generated.scenario
distance, cost = generated.plans
assert distance.is_feasible and cost.is_feasible
evidence = generated.to_dict()  # 数量在此明确边界序列化为 Decimal 文本
```

| 文件 / 对象 | 职责及数据结构 |
| --- | --- |
| `config/fleet_generator.json` | 独立生产配置：道路、车队、仓库绑定、需求候选、优先级、业务时刻、窗口余量、尝试上限 |
| `FleetVehicleSpec` | frozen/slots 记录，容量为原始单值转换的 Decimal；每车一个配送员 |
| `FleetGeneratorConfig` | frozen/slots 配置，车辆与需求候选用 tuple；校验 ID、仓库引用、数量及有限数值 |
| `fleet_witness.construct_candidate` | 原道路生成器 + 逐车精确装载 + 独立订单 ID + 双目标见证派生窗口 |
| `fleet_generator.generate_fleet_scenario` | 有界验收循环，独立验证、双目标真实调度、失败历史和输入变化检查 |
| `GenerationAttempt` | 序号、候选名、阶段、原因、业务指纹、两种目标的 valid/complete/服务数和真实耗时 |
| `FleetGenerationResult` | 场景、两份见证、两份实际计划、完整历史、seed、配置和场景指纹 |
| `FleetGenerationError` | 没有发布场景时的结构化失败记录；`to_dict()` 保留历史 |

JSON 用 `parse_float=Decimal` 读取原始单笔需求和容量，随后分别转换。
支持明确序列化边界输出的 Decimal 字符串无损读回；非法、负数、NaN/Infinity 拒绝。
载荷累加与容量比较始终使用 `exact_sum` 和 Decimal，不经过浮点视图、不用 epsilon。
仅几何、时间等非载荷参数允许转换为 float。

`network` 仅接受原道路默认 JSON 中的道路字段，保留 Phase 1 的物理道路及有向边预算语义。
旧单车的 `capacity`、`orders_count` 等字段不能塞进 `network` 并被静默重新解释。
旧 `GeneratorConfig`、`generate_scenario` 及 Web 使用的单车生成链保持原样。

配置的具体含义：

- 车辆 ID、配送员 ID 唯一；仓库须在生成的 warehouse 前缀及数量范围内。
- `demand_choices` 是显式离散需求分布，按候选项等概率抽样，允许零需求。
- 客户目的地有放回抽样，订单数可多于客户数；订单 ID 由 JSON 前缀及序号生成。
- `initial_time`、`service_time` 是业务时间，不读取墙钟，不自动推进生命周期。
- `witness_horizon` 是初步见证服务开始时间的绝对截止值，不是车辆返仓截止字段，
  也不是最终窗口上限；最终窗口按见证及配置余量派生。
- `window_early_slack` / `window_late_slack` 定义派生窗口余量，至少一个大于零，
  因为既有 Order 模型要求窗口起点严格小于终点。
- `max_attempts` 是本次完整候选重生成的上限，必须是正整数。

## 3. 构造及验收算法

```text
校验配置和显式整数 seed，记录配置指纹，创建一个局部 RandomSource(seed)
for attempt = 1 .. max_attempts:
    复用 Phase 1 道路生成器和独立道路验证器
    初始化每辆配置车辆的精确装载为 Decimal(0)
    对每个订单：
        抽样原始 Decimal 单笔需求
        遍历所有车辆，检查 exact_sum(该车装载, 该单需求) <= 该车容量
        无车能装：记录 capacity 拒绝，重生成整个候选
        从可装车辆中确定性随机选择；抽样目的地和优先级，登记唯一订单 ID
    手写 Fisher-Yates 打乱每车的见证访问顺序
    用 distance / cost 主目标闭包分别构造初步见证
    对每单：
        window_start = max(initial_time, min(两份见证服务开始时刻) - early_slack)
        window_end   = max(两份见证服务开始时刻) + late_slack
        非有限或浮点表达后窗口塌缩：明确拒绝，不补 epsilon 或改约束
    按最终订单重建两份见证；每车回各自仓库
    独立验证两份见证；非法或不完整见证立即失败
    实际运行 plan_fleet(distance) 和 plan_fleet(cost)，不给见证或分配提示
    对两份实际结果再次独立验证；非法结果立即失败
    两份结果均 valid 且 complete：核对输入未变，记录 accepted 并返回
    合法但部分配送：记录每种目标的服务数、每单原因，重生成整个候选
耗尽上限：抛出带全部尝试记录的 FleetGenerationError
```

`loads` 是按车辆 ID 索引的 Decimal 字典；`allocation` 是每车有序订单 ID 列表。
逐单装载只证明这份见证分配，不能将车队总容量当作某一辆车的容量。
局部装载选择失败也不证明不存在其他分配。

见证构造复用现有 `assess_route` 作为构造工具；证明其正确的是另一个独立的
`validate_fleet`，该验证器不导入候选/贪心模块，不调用构造器的时间重演函数。
实际调度仅接收普通 ScenarioBundle；metadata 中不含见证分配或“答案”。

沿用服务开始时间窗规则；评估含真实路径时间、等待、服务、后续传播及返仓。
没有返仓截止字段就不编造该限制；独立报告保留 `return_deadline_checked=False`。

## 4. 可复现性、证书和失败规则

一个 seed 对应一个局部随机源，跨重试继续消费同一随机序列，不修改基础 seed。
不依赖 set 迭代顺序、进程字符串哈希或内置排序。车辆和节点使用现有手写 ID 排序。
复现标识为生成器版本、完整配置指纹、基础 seed、尝试序号及实现版本。
候选名称只是可读标签，不能单独当跨配置全局唯一标识。

完整导出含节点/边及 metadata、逐订单身份、精确需求与容量、绑定、状态、业务时间、
见证和实际路线、拒绝历史。只剔除明确的耗时字段后做跨进程对比。
场景业务指纹复用 Phase 3 规则，不包含与调度无关的 metadata；跨进程实验比较的
则是完整快照内容，包含 metadata、道路 ID 和方向边标识。

返回的 ScenarioBundle 仍是现有可变容器。证书绑定生成时的业务指纹；调用方修改
订单、道路或车辆等业务数据后，`to_dict()` 会拒绝导出旧证书。导出另做 metadata
深拷贝，调用方改导出字典不会反向修改场景。没有宣称支持任意并发写或检测所有 ABA 变化。

非法配置、重复 ID、输入变化和非预期异常不被吞掉，也不靠重试掩盖。
独立验证发现非法结果时立即停止；只有记录明确原因的候选拒绝/合法部分结果进入重生成。
每次重生成都重新抽样整个候选，不能削减订单、扩容、改优先级或临时放宽窗口。
拒绝采样会使输出分布偏向当前贪心可完成的场景，不保证均匀覆盖全部可行场景。

## 5. 复杂度

沿用 Phase 3 记号：G=V+E，M 为订单数，K 为车辆数，U 为仓库和目的地数，
D 为精确十进制对齐位数，A<=max_attempts，R 为原道路构造及结构验证成本。

逐单检查 K 辆车的两个 Decimal 数精确和，装载分配 O(MKD)，附加空间 O(M+K+D)。
一份见证先做输入快照/指纹 F，再建原 PathProvider 闭包并重演路线：

```text
F = O(V² + M² + K² + sum(out_degree²) + E + (M+K)D)
C = O(U G log(V+1) + U²(G+V))
一份见证：O(F + C + MD + K)
```

初步和最终、distance 和 cost 共四次见证构造；没有共享跨候选缓存。
每种实际调度包含原独立验证，本层再核验一次，两份见证也各核验一次。
固定的调用次数不改渐近阶；部分结果的独立失败插入检查仍计入成本。

```text
总时间保守界：
O(A * [R + F + MKD + C + (M⁴ + KM²)(D+1) + L])
```

L 为展开的道路路径记录长度。A 有硬上限，但不保证在上限内成功。
峰值空间包括一份当前候选、闭包及四份最终路线记录，还有所有历史失败原因：
保守 O(G+U²V+(M+K)V+(M+K)D+MK+AM)，另计 metadata 和 ID 文本大小。
导出含手写排序、指纹与完整快照成本，不能声称 O(1)。

## 6. 实际实验与失败证据

原始数据：[v2-phase4-generation-results.json](experiments/v2-phase4-generation-results.json)。
配置：[生产配置](../config/fleet_generator.json)和
[实验矩阵](../config/fleet_generation_experiments.json)。
保留原产物；实验脚本拒绝覆盖已有输出。

矩阵为 seed 0/1/42/100/2026 × 订单5/10/20 × 车辆2/3，共30个请求。
固定40节点、113条物理道路、220条有向边，双向107/113；不改变 Phase 1 道路规则。
30个场景均第一次接受，0个耗尽拒绝；实际调度共60次，两种目标各服务350/350单。
每个场景有两份独立验证完整见证；每份实际结果都在原规划器验证之外再独立核验。

| 目标 | 实际调度 | 合法且全覆盖 | 服务/提交 | 原记录规划秒合计 | 原记录规划器内验证秒合计 |
| --- | ---: | ---: | --- | ---: | ---: |
| distance | 30 | 30 | 350/350 | 1.520442 | 0.209319 |
| cost | 30 | 30 | 350/350 | 1.495806 | 0.218698 |

以上保留原测量，不用恢复后的新耗时替换旧值。整体实验原记录12.076940秒，
包括压力案例、候选重放与跨进程检查；不是纯规划耗时。
见证 DTO 沿用 FleetStats 默认零值，表示未采集独立的见证规划统计，不是测得耗时为零；
见证构造时间包含在真实 attempt 和生成总耗时中。实际贪心的计数及耗时由原规划器采集。

真实紧时间窗案例：seed=2，8单、两车容量各12，需求候选1/2/3，early=1、late=0：

| 尝试 | distance | cost | 处理 |
| --- | --- | --- | --- |
| 1 | valid、7/8 | valid、7/8 | 记录未服务 ID/原因，拒绝 |
| 2 | valid、8/8 | valid、7/8 | 单目标成功仍拒绝 |
| 3 | valid、8/8 | valid、8/8 | 接受 |

配置未变，原始 JSON 保留这三份候选的完整场景、实际部分路线和另一次独立报告。
前两份都有完整可行见证，因此不能把贪心失败说成场景无解。
设置 max_attempts=1 时明确失败，不偷偷接着试。

两个拒绝对照各记录3次尝试：单笔需求2而每车容量1，阶段均为 capacity；
初步见证时域仅540到540.001，阶段均为 witness_route。没有靠扩容或放宽时域成功。

跨进程 hash seed=1/2/73，每进程五固定 seed 加上述真实重试案例，共6个场景。
完整快照、见证、实际路线和拒绝历史去掉实测耗时后完全一致，SHA-256 均为
`0566b778d481707d1e4ef6ad8dbf10bb79505e545b0801649cd093fef9ca3b65`。
原始文件另含12个源码/配置摘要，生成时的工作区字节与记录对应。

## 7. 测试、审查与交付

新增20项生成测试及1项三进程测试；原674项测试及断言保留。
先运行红测试再实现，覆盖同址多单、重复车辆/配送员/订单 ID、0.3 精确容量、
超出边界的微小 Decimal、车队总容量误用、真实部分结果重试、伪造成功、错误来源计划、
两个见证模式缺失、零宽窗口、过短时域、配置无损读回、意外异常和场景修改后证书失效。

暂停前曾报告695项通过、184.627秒；随后第二轮按用户要求中断，未计为通过或产品失败。
旧临时日志已不可用。恢复后的最终回归完整输出保存在
[v2-phase4-acceptance.json](experiments/v2-phase4-acceptance.json)。

| 恢复后检查 | 数量 / 结果 | unittest 秒 | 外层实际秒 | 退出码 |
| --- | --- | ---: | ---: | ---: |
| 新增测试 | 21通过，0失败/错误 | 11.030 | 11.600904 | 0 |
| 相关旧回归 | 164通过，0失败/错误 | 2.011 | 2.455320 | 0 |
| 全量第一轮 | 695通过，0失败/错误 | 192.932 | 194.827101 | 0 |
| 全量第二轮 | 695通过，0失败/错误 | 198.624 | 200.058024 | 0 |

各组有交叠，不能相加推算全量数量。恢复后还将完整实验重新输出到新临时文件，
除实测耗时外与保留的原始 JSON 逐项一致；原实验文件字节未变。

本阶段发现的新入口边界均先用回归复现，再修复：序列化 Decimal 配置无法读回、
零宽窗口策略违反既有 Order 契约、重复同一目标见证可能漏掉另一目标、
返回场景被调用方修改后仍可能导出旧成功证书。对应修复集中在新模块，未改旧调度算法。

7个新增/修改 Python 文件的禁用依赖及内置排序扫描通过；原674项测试文件和断言
未修改，core、图、Dijkstra、原单车生成器和验证器、既有调度模块、API/UI、
pyproject 均与基线一致。完整差异及 `git diff --check` 审查通过。

复现（PowerShell，仓库根目录）：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest tests.test_fleet_generation tests.test_fleet_generation_reproducibility
python -B -m unittest discover -s tests -t .
$replayOutput=Join-Path $env:TEMP ("logiroute-phase4-"+[guid]::NewGuid().ToString()+".json")
python -B scripts/experiment_v2_fleet_generation.py --output $replayOutput
git diff --check
```

全量执行临时申请系统保持唤醒并在 finally 恢复，不永久改变电源计划；
仍须避免主动合盖或显式睡眠。原跨进程测试超时及断言保持不变。

```text
config/fleet_generator.json                 生产参数
config/fleet_generation_experiments.json     实验矩阵及拒绝对照
src/logiroute/scenario_generator/
  fleet_config.py                          精确配置和指纹
  fleet_witness.py                         逐车可行构造
  fleet_generator.py                       验收、有界重生成和证据
  __init__.py                              新入口导出，旧入口保留
tests/test_fleet_generation.py               20项行为/回归测试
tests/test_fleet_generation_reproducibility.py 三进程完整快照比较
scripts/experiment_v2_fleet_generation.py     可复现实验，拒绝覆盖产物
docs/experiments/v2-phase4-generation-results.json 原始实验
docs/experiments/v2-phase4-acceptance.json     最终验收日志
docs/v2-phase4-feasible-generation.md         本报告
README.md / AGENTS.md / docs/architecture.md / docs/development-plan.md 阶段说明
```

最终提交 hash、远端 SHA 和工作区状态在交付消息实查报告。
main、Dashboard 分支、真实道路 stash 及历史提交保留，不合并 main、不强推。
未实施 Phase 5 动态执行或 Phase 6 API/UI 集成；Phase 4 完成后立即停止。
