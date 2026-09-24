# 第一问小范围调度试验

算法 `v004` / `forks`；实验 `exp012_20260924_forks_development`。

仅评估选定用例，不代表第一问完成。参数预先固定，检验用例没有用于按成绩选择参数。

每核目标块数倍率：4；每配置 1 个候选；评估超时：60.0 秒；并发评估进程上限：2。

| 核数 | 完成评分 / 计划 | 平均加速比 | 比单核快的用例数 |
|---:|---:|---:|---:|
| 2 | 1 / 2 | 未完整，暂不汇总 | 1 |
| 3 | 1 / 2 | 未完整，暂不汇总 | 1 |
| 4 | 2 / 2 | 2.8618 | 2 |
| 5 | 2 / 2 | 3.4127 | 2 |

查看 `metrics/summary.csv` 获取逐用例成绩和状态；`logs/*_trace.json` 可查看执行时间线。

`task_busy_fraction` 是各核 Task 时间段占总核时间的比例，包含搬运和等待，不等于计算单元利用率。

失败与超时：

- case_016 n2: timeout — evaluator exceeded 60.0 seconds
- case_016 n3: timeout — evaluator exceeded 60.0 seconds
