# Phase 3 P0：待机导致的跨进程超时诊断

## 现场与结论

诊断基线为 `b25f0d6ed63186ebdcb56de234fa85252c400845`，本地与远端一致。
工作区原有 3E 文件全部保留；修改报告前记录了报告和原始实验 JSON 的 SHA-256。
未 reset、clean、切换分支、操作 stash 或更改算法。

本次故障由测试执行期间的合盖待机触发。`-666.25` 是 CPython Windows
子进程等待层计算出的**剩余预算**，不是测试传入的超时配置，也不是运行耗时。
工作区、HEAD 和远端基线中的 `_run_with_hash_seed()` 一致，传入整数 `180`。

从原会话的完整命令执行记录恢复了原始 traceback（不是根据行号猜测）：

```text
test_seed42_is_identical_across_hash_seeds → _run_with_hash_seed("1")
subprocess.run                          subprocess.py:550
Popen.communicate                      subprocess.py:1228
  self.wait(timeout=self._remaining_time(endtime))
Popen.wait                             subprocess.py:1264
Popen._wait                            subprocess.py:1593
  raise TimeoutExpired(self.args, timeout)
TimeoutExpired ... timed out after -666.25 seconds
Ran 674 tests in 1060.724s
FAILED (errors=1), exit code 1
```

Windows System 日志提供独立的环境证据，以下均为 UTC：

| 事件 | 时间 | 证据 |
| --- | --- | --- |
| Kernel-Power 506 | 2026-10-20 11:30:47.5301754 | 进入 Modern Standby，Reason=Lid，LidOpenState=false |
| Kernel-Power 507 | 2026-10-20 11:44:41.3438687 | 退出待机，Reason=Lid，LidOpenState=true，DurationInUs=833821689 |
| 原全量命令完成 | 2026-10-20 11:44:42.509 | 恢复后约 1.2 秒报告错误 |

待机约 833.822 秒，超过 180 秒预算。原始异常对应
`endtime - now = -666.25`，即从建立截止时间至最后等待约 846.25 秒。
二者相符，但不能把整个 846.25 秒都说成待机时间。
同时出现的系统墙钟校准仅 -7 ms，不能解释数百秒超期；这里使用的也不是墙钟。

## 标准库机制与可控复现

实测环境：Python 3.12.10 / Windows，`subprocess` 来自 Python312/Lib/subprocess.py；
`subprocess._time` 使用 monotonic（GetTickCount64，分辨率 15.625 ms）。
计时诊断另用 perf_counter（QueryPerformanceCounter）测量，不替换正式测试时钟。

`communicate(timeout=180)` 先建立 `endtime = _time() + 180`，等待输出读取线程。
输出读取完成后，再执行 `wait(timeout=endtime-_time())`。
Windows `_wait` 将非正剩余值转成零毫秒等待；进程尚未退出时，抛出带该剩余值的
TimeoutExpired。因此异常发生于**最终等待进程退出**，不是 JSON 解析，也不是负值传参。
原 traceback 已到该位置，说明 stdout/stderr 读取步骤已经返回。

隔离诊断程序用真实 Python 子进程关闭两个输出管道后继续存活；仅在诊断父进程中
临时控制 `subprocess._time`：前三次为 100.0，其后为 946.25。
仍向 `subprocess.run` 传入整数 180，于同一标准库调用链复现 `timeout=-666.25`。
子进程由 subprocess.run 的原有异常清理机制终止并回收，mock 随作用域恢复。
这一实验仅复现异常机制，不生成或伪造任何配送场景输出；没有让机器再次实际休眠。

最小复现（仅 Windows 上的独立诊断进程，不能放进正式场景测试）：

```python
import subprocess, sys
from unittest.mock import patch

ticks = iter((100.0, 100.0, 100.0))
with patch('subprocess._time', side_effect=lambda: next(ticks, 946.25)):
    subprocess.run(
        [sys.executable, '-c',
         'import os,time; os.close(1); os.close(2); time.sleep(30)'],
        capture_output=True, text=True, timeout=180,
    )  # 预期抛出 TimeoutExpired，timeout 属性为 -666.25
```

## 修复与影响

**正式 Python 源码差异为零。** 根因是环境中断，故不修改测试 helper、断言、
180 秒期限或生产逻辑，也不捕获异常后重试来伪装成功。

本次验证在保持系统唤醒的执行会话中进行。临时父进程调用
`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`，检查返回成功，
在 finally 中恢复先前线程状态；不永久改变电源计划，不请求保持显示器亮屏。
这项请求用于防自动空闲休眠，**不保证阻止用户合盖或显式睡眠**。
未来若主动睡眠，原 180 秒超时仍可合理失败；必须保留错误现场并在连续清醒环境重验。

所有正式命令继续使用 `python -B -m unittest`，环境设置 PYTHONPATH=src、
PYTHONDONTWRITEBYTECODE=1。额外 UTF-8 输出设置仅用于日志编码。
诊断记录完整命令、解释器、工作目录、相关 Python 环境、timeout 类型、
异常 traceback/cmd/timeout 属性、真实耗时以及输出 SHA-256。
未收集或提交无关环境中的认证秘密；提交证据中的用户路径以占位符替换。
历史环境没有事先完整快照，因此不声称事后恢复了历史每个环境变量或子进程内部阶段耗时。

## 验证与证据

原测试通过插桩只记录 subprocess 参数，连续 3 次通过：30.437 秒，
6 个真实场景进程（hash=1/2 各三次）均传入 int 180，完整 stdout SHA-256 均为
`d552aa0e5eb285a8f8dd03a308a2371f3a9461ffd24bad36950df254cea04a37`。
原来的节点、边及权重、订单、distance/cost 路线与总量七组断言全部执行。
另以不插桩的 unittest 命令再次运行原测试，并完成相关回归和连续两轮全量。
准确计数、退出码及耗时见[验收原始记录](experiments/v2-phase3-acceptance.json)
和[阶段报告](v2-phase3-fleet-scheduling.md)。

原 3E 实验 JSON 未覆盖；另写临时输出重新执行整个实验。
去除明确的实测耗时字段后，60 次矩阵、固定实例、穷举反例及跨进程结果逐项相同。
原 10 个源码摘要全部匹配。原有测试文件零修改，未添加 skip 或降低断言。

剩余限制：没有历史 CPU/线程调度追踪，不能重建待机前后每条指令的时刻；
这不影响事件日志、异常栈和可控复现共同证明的超期原因及负数来源。
本修复只处理测试环境，既不增强贪心算法，也不形成 Phase 4 生产可行性保证。
