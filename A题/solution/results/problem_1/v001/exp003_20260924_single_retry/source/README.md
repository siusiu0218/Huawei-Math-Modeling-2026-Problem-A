# A 题第一问实验

自编代码与结果均在本目录；`../code`、`../data`、`../docs` 只读。仅需 Python 标准库，当前验证环境为 Python 3.11。

## 从工作区根目录运行

```powershell
python -B -m unittest discover -s A题/solution/tests -v
python -B A题/solution/experiments/run_baseline.py profile --experiment exp001_20260924_profile
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp002_20260924_baseline --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --blocks-per-core 4 --timeout 60 --workers 2
```

实验目录已存在时拒绝覆盖。重跑须换新的 `--experiment` 名称；按已归档代码复现时，把脚本路径换成对应实验的 `source/experiments/run_baseline.py`，仍使用本项目原始数据和评估器。清单记录它们的 SHA-256，复现前应核对。

## 当前实现

- `src/graph_analysis.py`：输入校验、保留经 COPY 传递的操作依赖、静态特征与代表用例选择。
- `src/baseline.py`：v001 基线；确定的拓扑顺序按计算量分块，依次选择预计完成较早的核心。估计只用计算周期和 Task 等待，不作为最终成绩。
- `experiments/run_baseline.py`：特征统计和小范围评估入口；调用原始评估脚本，并显式指定所有输出路径，防止写入原始数据目录。
- `tests/`：保留已有测试，增加手算搬运/等待、COPY 依赖、确定性及方案合法性的边界检查。

结果入口为 [实验目录](experiments/INDEX.md)。每次实验保存源代码快照、manifest、指标及报告；基线实验还保存调度方案、原始评估 JSON、进程日志、复现参数及 Perfetto Trace。

`summary.csv` 是逐用例结果，`aggregate.csv` 按核数及 tune/holdout 分组。若单核参考或多核成绩缺失，对应组不生成完整平均加速比。`completed` 只代表该实验的预定范围结束，不代表第一问全部完成。

评估超时会终止对应评估子进程并记为 timeout，不替换用例或排除失败。两个评估进程并发时，墙钟时间受竞争影响，不能把它当作严格的独占运行性能测试。
