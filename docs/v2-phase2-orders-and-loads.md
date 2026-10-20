# LogiRoute V2 Phase 2 — 正式设计约束与交付记录

本阶段只实现订单身份验证、手写优先队列、生命周期、Decimal 载荷和多车配置。
不实现多车分配、动态订单管理器、API/UI 改造或完整配送可行性保证。

## 已批准的四项补充约束

1. **节点访问与订单身份分开**：路线记录节点访问顺序；服务分配记录
   `(order_id, visit_index)`。一次访问可服务多张同址订单，一张订单只能服务一次。
   订单分区、节点访问覆盖、实际路径分别验证，禁止以目的地数量推断订单数量。
   旧节点见证仅在订单身份可唯一推断时兼容；同址多单必须提供显式服务分配。
2. **完整生命周期**：保留 `pending / in_transit / delivered / expired` 及默认
   `pending`，补充 `created / planned / cancelled`。不引入自动计时。
3. **可变订单队列契约**：入队记录排序键 `(业务优先级等级, time_window_end, id)`。
   修改 ID、priority、time_window_end 必须先移除再修改再入队。失效逻辑队首
   不自动丢弃，不返回为任务，抛明确错误并保留队列，调用方按入队 ID 移除。
   查看/出队检查被访问项的一致性；不承诺扫描侦测其他项的外部违规修改。
4. **Decimal 全程计算**：逐笔原始需求、容量分别转 Decimal；累加、扣减和比较
   均无浮点中间求和、无 epsilon。数值 JSON 在加载边界读取，精确载荷输出在
   `to_dict()` 边界转换十进制字符串。旧 float 字段仅保留兼容视图，不能用于新载荷计算。

## 生命周期迁移表

| 当前状态 | 允许的下一状态 |
| --- | --- |
| created | pending、cancelled |
| pending | planned、cancelled、expired |
| planned | pending（出发前撤回）、in_transit、cancelled、expired |
| in_transit | delivered |
| delivered | 无，终态 |
| cancelled | 无，终态 |
| expired | 无，终态 |

重复迁移、终态恢复和未列出的迁移均拒绝。过期由明确调用触发，不读墙上时钟。
队列只接受 pending；出队不改变状态、需求和原始订单身份。

## 兼容与门禁

- 开始 HEAD：`464a64b47f27825eca634f00ca6fad6d95e76e84`，指定功能分支，工作区干净。
- 实施前实跑基线：528 项通过，291.541 秒；原 528 项测试和断言全部保留。
- 现有模型明确允许零需求与零容量，继续保留；负数、NaN、inf、bool、数字字符串拒绝。
- JSON 多车配置要求非空车队、非空配送员及完整 1:1 绑定；不更改独立模型的可用范围。
- 保留单车 JSON、原调度算法、Phase 1 道路生成器和 seed 机制。
- 先写 P0 回归再修复；发现新增一致性问题先复现再修复。
- Phase 2 完成后停止，不进入 Phase 3。

## 对象职责、数据结构与复杂度

| 对象 / 接口 | 职责与内部数据 | 时间 | 额外空间 |
| --- | --- | --- | --- |
| `ServiceAssignment` | 不可变 `(order_id, visit_index)`，访问序号允许多对一 | 构造 O(1)，不计 ID 长度 | O(1) |
| `index_orders` | 按 ID 建字典，重复 ID 立即拒绝 | O(K) 平均，不计数值校验位数 | O(K) |
| `validate_order_coverage` | 输入、已服务、未服务 ID 集合；检查完整互斥分区 | O(K+A+U) 平均 | O(K+A+U) |
| `OrderPriorityQueue` | 手写有序数组 + ID 字典；最佳项在数组尾部，即逻辑队首 | 入队/按 ID 移除 O(K)，查看 O(1)，出队摊还 O(1)，查询平均 O(1) | 总 O(K)，单次操作 O(1) |
| `Order.transition_to` | 单一枚举 + 显式合法迁移表 | O(1) | O(1) |
| `check_delivery_load` | 原始容量 Decimal、逐 ID 需求 Decimal；完整精度累加 | O(KD) | O(K+D) |
| `DeliveryLoadState` | 出发时 ID→需求快照、已交付 ID 集合、精确载荷 | 初始化 O(KD)，单笔交付 O(D)，ID 查询平均 O(1) | 总 O(K+D)，单笔 O(D) |

K 为订单数，A/U 为服务/未服务记录数，D 为对齐后的十进制位数。
字典/集合复杂度按平均情况声明；字符串比较和哈希成本随 ID 长度增长。
队列复杂度按课程常用定长标量模型计，未使用链表：尾端出队已经常数时间，
链表仍需线性查找插入位置，反而增加指针与索引维护。字典仅用于身份检索，
顺序由手写比较和移动维护，不依赖字典、集合迭代顺序决定优先级。
没有调用内置排序、第三方堆或第三方优先队列。

队列伪代码：

```text
enqueue(order):
    校验订单、pending 状态和唯一 ID
    snapshot = (显式业务等级, time_window_end, order_id)
    数组尾部加入 entry
    从尾向前，将比 snapshot 更优的旧项右移，直到插入位置
    写入 entry，登记原始 ID 索引
peek_next():
    空队列则抛错
    校验数组尾项仍 pending 且当前键等于入队快照
    失效则抛错并保留；否则返回尾项
pop_next():
    调用 peek_next，移除数组尾和该 ID 索引，返回原订单
remove(original_id):
    从 ID 索引取得 entry，手写遍历数组并删除同一 entry
```

失效项不会被自动丢弃，队列长度包含它；`get()` 允许检查失效记录，
不代表任务发放。非队首的违规键修改不会被全队扫描发现，这是可变对象的
调用方所有权契约，不能把 O(1) 查看描述成全局自动重排。

精确载荷伪代码：

```text
每个原始 demand 和 capacity 分别校验后转换 Decimal
根据各项指数、有效位数及进位上界建立局部 Decimal 精度
逐项 Decimal 相加得到 initial_load，与 capacity 严格比较
出发时保存各订单 ID 和需求快照
deliver(id): 检查已装载且未交付，以 Decimal 扣减后验证不变量，再原子记录交付
```

独立载荷状态满足 `0 <= current_load <= initial_load <= capacity`；
`free_capacity = capacity-current_load`。释放空间不代表可以中途补货。
状态不构造路线、不分车、不改变原 Order/Vehicle，也不隐式迁移订单状态。

## P0 修复与失败案例

实现前先增加同址多单和重复 ID 回归，确认旧实现失败，再修复。
开发过程中发现的新数据一致性问题也先用测试复现；失败案例全部保留为回归：

| 失败输入 / 原因 | 现在的行为 |
| --- | --- |
| 同址订单被 `destination_id -> Order` 覆盖，路线节点集合误当订单覆盖 | 显式服务分配逐 ID 验证；同址一访多单全部保留；有歧义的旧节点见证拒绝 |
| 输入/输出重复订单 ID，遗漏、交叠、未知 ID | 输入重复立即 ValueError；输出完整分区报告逐项给出违反项 |
| 无路线却附服务或未服务引用 | 明确拒绝；纯分区验证使用独立 `validate_order_coverage` |
| 非仓库闭环、空路线或错误服务位置 | 独立路线覆盖检查失败，不靠订单集合掩盖路线错误 |
| 已取消、已过期、已送达等状态重新作为出发服务 | `order.inactive_service`，不再报告路线可配送 |
| 多车总需求被拿来与首车容量比较 | 无逐车分配证据则 `capacity_checked=False`，报告分配未验证 |
| 生成器旧 `capacity+1e-9` 放过 0.3 对 0.2999999999999 | 删除该载荷路径 epsilon，严格 Decimal 拒绝；道路采样与 seed 不变 |
| 低 Decimal 上下文精度或 float 报告提前丢失 `100+1e-40` | 按对齐位数精确累加；报告内部保留 Decimal，容量 100 明确拒绝 |
| 非零载荷 `1e-400` 的 float 视图下溢为零，误判空车 | `Vehicle.is_available` 使用精确载荷判断，拒绝当成空车 |

没有通过删除、跳过或降低原断言取得通过。测试命令曾因未设置 src 导入路径、
误写两个旧模块名而产生 ImportError；改用下列实际模块与 PYTHONPATH 后重跑通过，
这些调用错误不计入有效通过结果。

## 固定实例与原始证据

实际运行 `scripts/experiment_v2_orders.py`，输出位于
[`experiments/v2-phase2-order-results.json`](experiments/v2-phase2-order-results.json)。
文件包含十个生产源码的 SHA-256，审查时已逐一比对当前文件字节。

| 订单 | 目的地 | kg | 优先级 | 截止时间 | 服务访问序号 |
| --- | --- | --- | --- | --- | --- |
| O1 | C12 | 40 | urgent | 1000 | 1 |
| O2 | C12 | 35 | normal | 900 | 1 |
| O3 | C18 | 25 | normal | 1100 | 2 |

路线 `W1 → C12 → C18 → W1`，两次客户节点访问服务三张订单，
覆盖检查及服务位置检查通过；C12 的两张订单分别计时和扣载。
反向入队，peek 为 O1，连续出队 O1、O2、O3；同优先级的平局实例得到 Z、A、B
（Z 截止更早，A/B 截止相同按 ID）。出队不修改 demand 或 status。

容量 100：出发 100 → 交付 O1 后 60 → O2 后 25 → O3 后 0。
O3 改为 26，总计 101，拒绝。精度设为 6 时，100 加 1e-40 仍严格超载。
已服务 O1/O3、明确未服务 O2 是合法完整分区，`all_orders_served=False`，
不能把“结果完整记录”写成“全部送达”。

`config/scenario_fleet.json` 实际有 V1(100 kg, W1)、V2(120 kg, W2)，
D1→V1、D2→V2。20 张订单总需求 200.0 kg，装载量均为零，加载成功。
这只证明配置和 1:1 绑定合法，不使用 220 kg 车队总容量作为单车容量，
不实施任何订单分配，也不证明这 20 张订单在时间窗内可完成。
`config/scenario.json` 原单车配置未改，继续通过加载和旧调度回归。

## 测试、扫描与复现

Windows PowerShell，Python 3.12（满足项目 >=3.11），在仓库根目录运行：

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.test_order_identity tests.test_decimal_quantities tests.test_order_lifecycle tests.test_orders tests.test_vehicles tests.test_scenario_generator_validator
python -m unittest tests.test_order_queue
python -m unittest tests.test_vehicle_load tests.test_multi_vehicle_config tests.test_config tests.test_scenario_generator_backbone_builder
python -m unittest discover -s tests
python scripts/experiment_v2_orders.py --output docs/experiments/v2-phase2-order-results.json
git diff --check
```

| 验证 | 实测结果 |
| --- | --- |
| 修改前完整基线 | 528 项通过，291.541 秒 |
| 身份/模型/生命周期及相关旧回归 | 66 项通过，0.032 秒 |
| 手写队列 | 14 项通过，0.001 秒 |
| 载荷/多车配置及相关旧回归 | 58 项通过，0.203 秒 |
| 中间完整回归（之后仍增加边界用例） | 608 项通过，376.047 秒 |
| 最终完整回归 | 609 项通过，261.060 秒；原 528 项 + 新增 81 项 |

定向测试之间可能重叠，不能相加推算全量项数。全量结果无失败、无跳过；
旧 API 测试发出的既有 `algorithm` 参数弃用提示不影响通过。
最终记录以最后一次完整运行结果为准。

审查使用 Python AST 检查本次变更新增的 18 个 Python 文件：
禁用包导入、`sorted()`、`.sort()` 均为零命中；`pyproject.toml` 未改变，
没有新增第三方依赖。对基线差异检查确认：原测试文件没有 M/D，
只有六个新增测试文件；图、Node/Edge、Dijkstra、手写堆、PathProvider、
旧调度器、道路采样、随机源、旧单车配置及前端均保持不变。
这里只宣称本阶段变更路径的扫描结果，不把仓库既有诊断代码误称为新增算法。

## 文件清单

```text
src/logiroute/
  algorithms/order_queue.py                 新增：手写有序数组队列
  config/loader.py                         修改：原始精度、多车绑定与引用校验
  core/
    __init__.py                            修改：公开身份与载荷接口
    enums.py                               修改：兼容增加三个状态
    orders.py                              修改：精确需求与显式生命周期
    vehicles.py                            修改：精确容量/载荷操作及原子校验
    quantities.py                          新增：标量转换及精确十进制累加
    order_identity.py                      新增：订单身份及互斥覆盖
    delivery_load.py                       新增：单次出发载荷状态
  scenario_generator/
    validator.py                           修改：订单与访问分离、独立验证
    backbone_builder.py                    修改：仅移除载荷判定 epsilon
tests/
  test_order_identity.py                    新增：P0 身份与服务见证
  test_order_queue.py                       新增：队列顺序、一致性与失效状态
  test_order_lifecycle.py                   新增：完整迁移矩阵
  test_vehicle_load.py                      新增：精确载荷、不变量和边界
  test_multi_vehicle_config.py              新增：绑定、引用、精度与兼容性
  test_decimal_quantities.py                新增：原始标量与旧视图兼容
config/scenario_fleet.json                  新增：两车两配送员固定配置
scripts/experiment_v2_orders.py             新增：可复现固定实例及源码哈希
docs/experiments/v2-phase2-order-results.json 新增：实际实验原始输出
docs/v2-phase2-orders-and-loads.md           新增：本设计与交付记录
docs/architecture.md                       修改：Phase 2 职责和依赖
docs/development-plan.md                   修改：阶段状态及后续门禁
README.md                                  修改：当前阶段与报告导航
AGENTS.md                                  修改：当前授权及四项强约束
```

## Git 交付

开始 HEAD 为 `464a64b47f27825eca634f00ca6fad6d95e76e84`。
前三个代码提交：

- `475e62461734dfb15a1b0ba241482956f500d6e6` — 身份、精确模型和生命周期基础。
- `2b9c482934cdcef81c1b4f6877251755627951ea` — 手写确定性队列。
- `6f321f4d4caa20b9fd5eb7de0d612d5a583e1cc0` — 多车配置、独立载荷和生成器严格容量检查。

精确标量及生命周期是身份校验的共享前置，故实际提交按依赖合理调整。
最后一个提交为 `docs(v2): document order queue and load semantics`，含本报告、
架构导航、约束和实验；该提交最终 hash、推送和清洁状态以交付消息的远端实查为准，
避免让报告自引用其尚未存在的提交 hash。

保护引用初始值：Dashboard 分支 `eb6fee0eb67fdcaaca6abcb1ca004767a36ff998`，
本地 main `994414753b19c51a2b0522a4fd12a48feb1f6073`，
stash `15964cc350100869942bf893ac79ff031db5b686`。
未合并 main、未重写历史、未操作真实道路 stash。

## 遗留限制与 Phase 3 入口（仅建议，未实施）

- 旧单车规划器继续原有接口和行为；本阶段未将新队列、生命周期、精确载荷
  接入调度执行。旧算法仍有原来的浮点策略，不能宣称全系统均已 Decimal 化。
- 旧 dataclass 数值字段保留 float 兼容视图，超精度输入应走 `*_decimal` 属性和
  新载荷 `to_dict()` 字符串边界。经旧 asdict/float 输出再重建可能损失额外精度。
  模型拒绝超出有限旧 float 表示上界的数量；下溢视图不用于新载荷判断。
- Order 仍是原有可变模型；运行时迁移用 `transition_to`。为兼容加载/构造，
  直接赋值 status 仍可绕开迁移检查，未来订单管理器应集中持有状态写权限。
- 多车容量必须有逐车订单分配及独立证据；当前验证器不生成该分配，明确标为未验证。
- 随机场景“全部订单可送达”仍需后续阶段独立验证，不能用道路连通性替代。
  本阶段服务见证沿用既有 travel_time 路径及时间窗检查，不代表 distance/cost
  两种实际调度均完成，也没有解决全部返程时间约束。
- 多车全局贪心、时间窗与返程约束、动态订单管理、API 和 Dashboard
  多车状态同步均未实施。

Phase 3 建议先定义逐车分配及逐单未服务原因，再接入队列与载荷快照；
所有车辆路径复用现有 Dijkstra 和单次调度缓存。分别运行 distance/cost，
由独立验证器按订单 ID 检查覆盖、容量、时间窗及返程，再讨论整体完成率。
本次在 Phase 2 交付处停止，等待审查。
