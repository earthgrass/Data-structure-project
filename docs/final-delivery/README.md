# LogiRoute 最终课程交付包

从这里阅读当前产品，历史阶段报告继续保留。Phase 7 完整测试和 Git 结果见 [交付报告](report.md)。

1. [当前产品入口与启动](../../README.md)
2. [真实架构](../architecture.md)
3. [数据结构、算法、复杂度与教师问答](defense.md)
4. [5–8分钟操作演示](demo-script.md)
5. [Phase 7A问题登记与文件级计划](../phase7-audit.md)
6. [地图、数据边界与性能](../phase7-map-performance.md)
7. [严格时间窗原理及原五seed实验证据](../strict-time-windows.md)
8. 本轮原始实验：[受控双目标](../experiments/phase7-objectives.json)、[A–G窗口最终结果](../experiments/phase7-windows-final.json)、[地图](../experiments/phase7-map.json)、[性能](../experiments/phase7-performance.json)。

复现脚本位于 scripts/，实验脚本默认拒绝覆盖原始结果。本轮各脚本可传一个新文件名，例如 `python -B scripts/experiment_phase7_windows.py my-new-windows.json`、`python -B scripts/experiment_objective_demo.py my-objectives.json`、`python -B scripts/experiment_phase7_performance.py my-performance.json`、`python -B scripts/audit_phase7_map.py my-map.json`。设好PYTHONPATH=src后运行，结果写入docs/experiments，不删除历史证据换取成功。

## 历史入口

- [原README完整存档](readme-history.md)：保留当时的单车口径与统计，不作为当前使用说明。
- [V2 Phase 2](../v2-phase2-orders-and-loads.md)、[Phase 3](../v2-phase3-fleet-scheduling.md)、[Phase 4](../v2-phase4-feasible-generation.md)、[Phase 5](../v2-phase5-dynamic-orders.md)、[Phase 6](../v2-phase6-integration.md)。
- [Phase 6.1 UI](../v2-phase6-1-dashboard.md)、[全屏地图](../bjut-map-workbench.md)、[校园设施](../bjut-campus-delivery.md)。
- [V1 Phase 3](../PHASE3_SUMMARY.md)、[V1 Phase 4](../PHASE4_SUMMARY.md)、[历史算法索引](../data-structures-and-algorithms.md)。
