# 第一问 v001 基线：首轮与超时重试合并结果

原实验 `exp002_20260924_baseline`；重试实验 `exp003_20260924_single_retry`。算法和原始评估材料哈希一致。

只用成功重试补充此前失败项；原始失败记录未覆盖。各行 `experiment` 和 `source_result` 标明结果来源。

仅覆盖选定的 8 张图，不代表全部 100 张图，也没有与改进算法比较。

| 核数 | 完整评分 / 计划 | 平均加速比 | 比单核快的用例数 |
|---:|---:|---:|---:|
| 1 | 7 / 8 | 未完整，暂不汇总 | 0 |
| 2 | 7 / 8 | 未完整，暂不汇总 | 4 |
| 3 | 7 / 8 | 未完整，暂不汇总 | 3 |
| 4 | 7 / 8 | 未完整，暂不汇总 | 3 |
| 5 | 7 / 8 | 未完整，暂不汇总 | 3 |

重试记录：

- case_014 n1: timeout。evaluator exceeded 300.0 seconds
- case_016 n1: ok。

逐用例结果：[combined_summary.csv](metrics/combined_summary.csv)。分组汇总：[combined_aggregate.json](metrics/combined_aggregate.json)。

并发数、超时预算不同，因此只合并相同算法的模拟周期与搬运量；不将各次墙钟时间混合后用于比较运行效率。
