# 单车配送：Dijkstra 距离矩阵 + 有向 TSP 搜索

## 问题定义

路网有 `V` 个节点、`E` 条有向边，订单有 `K` 笔。车辆从选定仓库出发，
每笔订单服务一次，最后返回同一仓库；容量和订单时间窗是硬约束。
主目标单选 `distance` 或 `cost`，实际到达时间取**选中道路路径**的
`cross_metrics['travel_time']`。

这属于带时间窗与容量约束的单车有向旅行商问题。求解分两层：

1. **道路层**：对仓库及不同订单目的地各运行一次 Phase 2 手写单源 Dijkstra，
   回溯路径，形成 `(K+1)×(K+1)` 的有向最短路矩阵。相邻配送站之间的路径
   可以经过矩阵之外的路网节点。
2. **顺序层**：在矩阵上搜索订单排列。每个状态记录已服务订单位掩码、
   当前位置、主目标累计值、服务完成时刻、载重和访问顺序。
   扩展时立即检查容量和时间窗，只保留得分最好的 `B` 个状态；
   `B = optimization.tsp_beam_width`，固定与随机场景默认均配置为 1024。

### 为什么不用 21 点 Floyd

把仓库与 20 个订单目的地的**直接道路边**放进 Floyd，会遗漏需要经过其余路网节点的
路径。若先用完整路网 Dijkstra 得到这 21 个站点之间的最短路，矩阵已经
满足最短路意义，再运行 Floyd 是重复计算。项目要求配送路径复用已有
Dijkstra，因此采用单源 Dijkstra 填矩阵；路网节点数为 50 时，无需
对全部 50 个节点运行 Floyd 再截取 21×21 子矩阵。

## 伪代码

```text
orders ← 手写稳定排序(订单 ID)
nodes ← [仓库] + 每笔订单的目的地
for each 不同的 source in nodes:
    dist, prev ← Phase 2 Dijkstra.single_source(完整路网, source, 主目标)
    for each target in nodes:
        matrix[source,target] ← 沿 prev 回溯道路路径及三项指标

beam ← {空顺序状态}
for layer = 1 .. K:
    candidates ← 手写有界最大堆(容量 B)
    for each state in beam:
        for each 未服务订单 target:
            leg ← matrix[state.last,target]
            if leg 不可达、载重超限或服务开始晚于时间窗上界: continue
            next ← 加入 target 并传播实际道路行驶时间
            lower_bound ← 当前累计值 + 未访问点的必需出边下界
            candidates.保留最小 B 个(lower_bound, 累计值, 订单顺序)
    beam ← candidates
    if beam 为空: break

从访问订单最多的状态中选择最短/最低成本的可回仓闭环
重建 legs、stops、总指标与未服务订单记录
```

下界是当前位置到某个未访问点的最小出边，加上每个未访问点到
其他未访问点或仓库的最小出边。完整闭环必须使用这些出边，故其和
不会高估剩余距离/成本。束宽截断仍可能删除最优路线，所以
`RoutePlan.notes['optimality_proven']` 仅在**未发生任何截断且找到完整
可行回路**时为真。其余情况只声明有界近似解，不宣称全局最优。

## 复杂度与数据结构

设 `U ≤ K+1` 为不同起点数，`B` 为束宽。单源 Dijkstra 仍使用课程
手写索引堆。距离矩阵为二维 `list[PathResult]`；已访问集合为整数位掩码；
每层候选由手写最大堆保留最佳 `B` 个，无 `heapq`、`sorted()` 或现成
规划求解包。

* 矩阵：时间 `O(U·((V+E)log V + K·V) + K²)`，路径缓存最坏
  空间 `O(U·K·V)`。
* 搜索：最多 `K` 层、每层 `B·K` 次扩展、每次下界 `O(K²)`；
  时间上界 `O(K⁴·B + K²·B·log B)`，束状态空间 `O(B·K)`。
* 显式设置 `B<1` 的非法配置被拒绝；未配置时按订单数平方取默认值。

固定场景与 seed=42 随机场景均 20/20 送达。seed=42 的最短距离路线为
`1717.315 km`，最低成本路线为 `3993.425 ¥`；两者分别最小化自己的
主目标，其他两列仅用于对比。历史 NN、CFI、2-opt 仍可通过内部
`algorithm` 参数运行课程实验，产品默认流程不再调用它们。
