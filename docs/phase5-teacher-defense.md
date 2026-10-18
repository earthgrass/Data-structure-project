# Phase 5 课程检查答辩说明（2026-10-17 冻结版）

> 本文件面向周一课程检查，回答「系统现在能演示什么、数据是什么、边界在哪里」。
> 与本文件配套的实测结果见 `README.md` 的「课程检查冻结基线」。

---

## 一、一句话结论

LogiRoute 当前演示的是**随机生成的假设物流场景**：单车辆从仓库出发、访问全部
待配送点并返回仓库；后端用手写的 Dijkstra + 可行插入 + 受约束 2-opt 计算路线，
前端只负责调用与展示。**没有接入真实道路网络、真实 POI 或实时交通数据**，
地图是**示意底图**，规划结果是**启发式可行解，不是全局最优**。

---

## 二、5 分钟讲解稿

1. **题目与约束**：教师原题要求单车辆配送 —— 从仓库出发遍历所有待配送点后
   返回仓库。项目从 Phase 1 起就把它写成硬约束：生成器只造一辆 `VH1`，
   `RoutePlan` 构造时校验首尾必须是同一仓库。
2. **数据结构**：`LogisticsGraph` 以邻接表为唯一可变状态，邻接矩阵按需导出；
   手写 `ArrayQueue`、索引式 `MinHeap`；不使用 `heapq` / `networkx` / `numpy`。
3. **算法**：Phase 2 手写 Dijkstra，支持 distance / travel_time / cost 三种
   边权；Phase 3 实现最近邻基线、可行插入（CFI）、受约束 2-opt；当前
   默认规划器以 **Dijkstra 配送站距离矩阵 → 有向 TSP 状态搜索** 规划。
4. **场景生成**：Phase 4 生成强连通有向图、客户 backbone、订单与扁平宽时间窗；
   独立 validator 不调用 planner，单独校验覆盖性、容量、时间窗、可达性与闭环。
5. **Dashboard**：FastAPI 提供 `/api/scenario/random`、`/api/plan`、
   `/api/compare`；React/Vite 前端展示场景、路线、时刻表与双目标对比。
   前端不重算任何调度算法。
6. **当前版本**：seed=42 可跨进程复现；默认规划已切换为 Dijkstra 距离矩阵
   与有向 TSP 有界搜索。未启动 Phase 6。

---

## 三、演示脚本（固定 seed=42）

```bash
# 终端 A —— 后端
PYTHONPATH=src python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000

# 终端 B —— 前端
cd frontend
npm run dev
# 浏览器打开 http://localhost:5172
```

操作顺序：

1. seed 保持 **42**，点击「生成场景」。
2. 校验面板应显示：`feasible=True`，50 节点 / 157 有向边 / 20 订单。
3. 选择 **distance**，运行规划，记录总距离 / 总成本 / 送达数。
4. 选择 **cost**，再次运行；使用「双目标比较」并排查看两条路线。
5. 结果面板检查：车辆只有 `VH1`，起点与终点都是 `W1`，20/20 送达，
   峰值载重 194.9 / 250.0 kg。

命令行复核：

```bash
PYTHONPATH=src python -m unittest discover -s tests -t .          # 508 OK
PYTHONPATH=src python -m unittest tests.test_seed_reproducibility -v
```

---

## 四、实测数字（seed=42，必须按实际输出讲）

| 指标 | distance 模式 | cost 模式 |
| --- | --- | --- |
| 可行 / 送达 | True / 20 of 20 | True / 20 of 20 |
| 单车辆 | VH1（250 kg） | VH1（250 kg） |
| 闭合回路 | W1 → … → W1 | W1 → … → W1 |
| 总距离 | 1717.315 | 1732.588 |
| 总成本 | 4037.206 | 3993.425 |
| 总行驶时间（仅对比） | 2194.306 | 2226.081 |
| 峰值载重 | 194.9 / 250.0 | 194.9 / 250.0 |

**如实说明**：distance 模式得到较短距离，cost 模式得到较低成本。
两者在同一场景上分别搜索有向 TSP 顺序，每条 leg 的 `metric` 分别为
`distance` / `cost`，三个总额均来自各自实际选中的道路路径。

---

## 五、当前边界（答辩时必须主动说明）

| 项目 | 当前状态 |
| --- | --- |
| 场景来源 | 随机生成的**假设**物流场景（seed=42）；固定场景也是手工构造 |
| 地图 | 北京 16 区 GeoJSON + 抽象坐标投影，**示意底图** |
| 真实道路导航 | **未接入** |
| 实时交通 | **未接入**；`traffic_status` 默认 `clear` |
| 订单 | 生成器构造的**模拟订单**，不是真实电商订单 |
| 车辆 | **严格单车辆** VH1；其余车辆设计已作废 |
| 最优性 | 有界 TSP 状态搜索；束宽截断时**不保证全局最优** |
| 未服务订单 | 如存在会如实列出原因，不伪造 100% |
| 下一阶段 | BJUT 周边真实道路网络：仅设计存档，本轮未下载数据 |

---

## 六、常见提问与回答

### Q1：这些数据是真实的吗？
不是。场景由 `logiroute.scenario_generator` 按 seed=42 生成，节点、边权、
订单、时间窗都是模拟值。固定场景 `config/scenario.json` 也是手工构造的
确定性场景，同样不代表真实道路或真实订单。

### Q2：地图是真实地图吗？
不是。前端用北京 16 区示意 GeoJSON 与抽象坐标投影展示节点和路线，属于示意
底图；没有使用 OSM 瓦片，也不提供真实道路导航。

### Q3：有实时交通数据吗？
没有。`travel_time` 与 `cost` 来自生成器的规则采样，`traffic_status` 默认
`clear`。实时交通接入方案放在下一阶段设计文档中，本轮未实施。

### Q4：为什么地图上相近的配送点不连续服务？
图上坐标只是示意位置；订单之间是否相邻，要看完整路网的**有向道路最短路**
与整条闭环总量。先用 Dijkstra 形成仓库 + 配送站的距离矩阵，再在矩阵上
求 TSP 顺序。seed=42 中 C4 与 C26 虽近，但彼此没有直接道路，
强行相邻可能增加整条路线距离。束宽截断时仍不保证全局最优。

### Q5：怎么证明没有把两种指标混在一起？
每个 leg 的 `PathResult` 带 `metric` 与 `cross_metrics`。测试
`tests/test_phase5_objective_tradeoff.py` 逐 leg 校验：
`Σ cross_metrics["distance"] == total_distance`，
`Σ cross_metrics["cost"] == total_cost`，
`Σ cross_metrics["travel_time"] == total_travel_time`，且每条 leg 的
`metric` 等于请求的主目标。seed=42 的实测也已逐 leg 复核。

### Q6：为什么必须保证单车辆闭环？
教师原题要求从仓库出发、遍历所有待配送点后返回仓库。项目把它写成
`RoutePlan.__post_init__` 的硬不变量：`stop_sequence[0] == stop_sequence[-1]
== depot_id`，且调度器只选一辆 IDLE 车辆。生成器也只造一辆车。

### Q7：所有订单都能送达吗？
seed=42 场景 20/20 全部送达。系统如实记录 `unserved_orders` 及原因
（容量、时间窗、不可达等）；若无法全部服务，`is_feasible` 会为 False，
不会伪造 100%。

### Q8：容量怎么约束？
车辆容量 250 kg，总需求 194.9 kg；`DeliveryStop.cumulative_load` 单调累计，
`check_feasibility` 校验峰值不超过容量。

### Q9：时间窗怎么处理？
生成器为所有订单构造扁平宽窗口，覆盖保守时间上界 H；调度器按
`arrival → max(arrival, tw_start) → + service_time` 传播，
校验 `service_start ≤ time_window_end`。`travel_time` 只作为对比列，不能作主目标。

### Q10：用了现成的算法包吗？
没有。图、堆、Dijkstra、TSP 搜索、队列、NN、CFI、2-opt 全部手写；不使用
`networkx`、`numpy`、`scipy`、`ortools`、`heapq`。FastAPI / React / Vite
仅在 Phase 5 Dashboard 层授权使用，不参与算法核心。

### Q11：复杂度是多少？
Dijkstra 用索引式二叉最小堆：`O((V+E) log V)`；对至多 `K+1` 个
不同配送起点各运行一次。TSP 有界搜索的保守上界为
`O(K⁴·B + K²·B·log B)`，`B` 是束宽。详见 `docs/algorithms-tsp.md`。

### Q12：为什么地图上的路线看起来绕？
地图直接绘制抽象坐标；路线是图上的有向最短路径（可经过中转节点），
不是地理直线；看起来绕主要由稀疏随机路网造成，不代表真实导航路径。

### Q13：seed=42 真的可复现吗？
可复现。本轮修复了 `graph_sampler` 直接迭代 `set` 导致跨进程边权漂移的 P0，
并新增 `tests/test_seed_reproducibility.py`：用不同 `PYTHONHASHSEED` 启动
两个独立进程，比较图、订单、distance/cost 路线与总额，结果完全一致。

### Q14：前端会重新计算调度吗？
不会。前端只调用 `/api/*`，所有 Dijkstra / TSP / 生成器逻辑都在
Python 后端；这是 AGENTS §3.7 的强约束。

### Q15：为什么 Phase 5 能引入 FastAPI？
项目约束明确：fastapi / uvicorn / React / Vite **仅** Phase 5 Dashboard
已授权，且只作为 Web/UI 层，不替代算法核心；Phase 6 动态重规划仍未启动。

### Q16：如果老师换一个 seed 呢？
任意整数 seed 都走同一生成器；场景可能因容量/时间窗不可行而重试，重试失败
会明确报错而不是伪造结果。演示固定用 42，便于复现。

### Q17：未服务订单怎么报告？
`ScheduleResult.unserved_orders` 是 `Violation` 列表，含订单 ID、类型
（容量 / 时间窗 / 不可达等）与消息；`is_feasible` 与之一致，不会只报总量。

### Q18：下一阶段做什么？
接入 BJUT 周边真实道路网络（OSM 等数据源、道路图构建、坐标处理、许可与
交通数据方案）已写入 `docs/phase6-bjut-road-network-design.md`，本轮只做
设计存档，没有下载或接入真实数据，也没有启动 Phase 6。

---

## 七、答辩禁忌

* 不要说“数据是真实的”或“地图是真实道路导航”。
* 不要说“结果全局最优”或“distance 一定优于 cost”。
* 不要说“已接入实时交通”或“已实现动态订单”。
* 不要展示未经本轮命令实测的测试数量或构建结果。
* 如果被问到未实现功能，直接指向设计文档与本文件的边界表。
