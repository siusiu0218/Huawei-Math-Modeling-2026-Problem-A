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
- `src/component_scheduler.py`：v002；保留完整弱连通计算分量再均衡分组、分核。只有一个分量时回退 v001 算法，但使用当次 `--blocks-per-core` 参数，不保证与倍率 4 的冻结基线方案相同。
- `src/branch_scheduler.py`：冻结的v003依赖收缩候选；合法收缩可能损失并行。
- `src/fork_preserving_scheduler.py`：v004仅合并串行连接，保护分叉与汇合；可能产生大量任务，仍是候选。
- `experiments/run_baseline.py`：特征统计和小范围评估入口；调用原始评估脚本，并显式指定所有输出路径，防止写入原始数据目录。
- `tests/`：保留已有测试，增加手算搬运/等待、COPY 依赖、确定性及方案合法性的边界检查。

结果入口为 [实验目录](experiments/INDEX.md)。每次实验保存源代码快照、manifest、指标及报告；基线实验还保存调度方案、原始评估 JSON、进程日志、复现参数及 Perfetto Trace。

`summary.csv` 是逐用例结果，`aggregate.csv` 按核数及 tune/holdout 分组。若单核参考或多核成绩缺失，对应组不生成完整平均加速比。`completed` 只代表该实验的预定范围结束，不代表第一问全部完成。

评估超时会终止对应评估子进程并记为 timeout，不替换用例或排除失败。两个评估进程并发时，墙钟时间受竞争影响，不能把它当作严格的独占运行性能测试。

## 只重试失败项

`--cases` 和 `--cores` 可限制为已冻结名单内的用例、核数子集，不改变切图算法。首轮两个单核参考超时后，按下列命令重试：

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp003_20260924_single_retry --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_014 case_016 --cores 1 --blocks-per-core 4 --timeout 300 --workers 1
python -B A题/solution/experiments/summarize_recovery.py A题/solution/results/problem_1/v001/exp002_20260924_baseline A题/solution/results/problem_1/v001/exp003_20260924_single_retry
```

汇总工具只允许成功重试补充失败项，拒绝替换原有成功结果，并核对算法源码、切块参数和原始材料哈希一致。汇总结果入口为重试目录中的 `COMBINED_REPORT.md` 和 `metrics/combined_summary.csv`；首次超时及重试仍各自留档。汇总脚本实际版本另存为 `source/recovery_summary.py` 并登记哈希。重新运行实验产生新的目录后，可用这份快照重建汇总；目标目录已有汇总时拒绝覆盖。

本轮已取得 32 个多核结果和 7 个单核参考（39/40 项）；`case_014` 的单核参考在 300 秒重试中仍超时，因此 8 张图的总体平均加速比暂不报告。具体状态见 [CONTEXT.md](CONTEXT.md)。

当前没有 Git 提交基点；通过每个实验的源代码快照与哈希追溯，不将工作区内其他未跟踪材料一并提交。

## 第二版的调参与检验

固定配置、原始评估器与 v001 相同。调参阶段分别测试每核目标 Task 倍率 4 与 16；选择倍率 16 后在 [v002_selection.json](experiments/v002_selection.json) 冻结，再运行检验集合。下面给出最终设置命令；重跑同样须更换实验名：

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --algorithm components --experiment exp005_20260924_components_tune16 --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_093 case_061 case_034 case_014 --cores 2 3 4 5 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --blocks-per-core 16 --timeout 60 --workers 2
python -B A题/solution/experiments/run_baseline.py benchmark --algorithm components --experiment exp006_20260924_components_holdout --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_078 case_095 case_039 case_016 --cores 2 3 4 5 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --blocks-per-core 16 --timeout 60 --workers 2
python -B A题/solution/experiments/compare_versions.py --baseline A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --runs A题/solution/results/problem_1/v002/exp005_20260924_components_tune16 A题/solution/results/problem_1/v002/exp006_20260924_components_holdout --selection-decision A题/solution/experiments/v002_selection.json
```

倍率 4 的调参复现：将第一条命令的实验名换成新名称，`--blocks-per-core` 改为 `4`。全部历史实验见 [INDEX.md](experiments/INDEX.md)。

查看 [v002 结论与限制](results/problem_1/v002/exp006_20260924_components_holdout/FINDINGS.md) 和 [逐配置比较表](results/problem_1/v002/exp006_20260924_components_holdout/metrics/version_comparison.csv)：最终 32 项全部评估成功，25 快、1 平、6 慢；检验集合为 9 快、1 平、6 慢。不是全部 100 张图的正式结论。版本间时间比不等于单核/多核加速比；当前仍不报告缺少 case_014 单核分母的完整平均加速比。

诊断入口 `experiments/diagnose_singlecore.py` 会创建独立副本，只作探索性阶段计时和栈采样，不提供正式成绩。记录在 `results/scratch/case014_stage_probe_safe_20260924/`；已定位到全局事件循环反复扫描操作列表的热点，原程序未改。

## 退步图的算法与粒度对照

新增 exp007（v002、倍率4）与 exp008（v001、倍率16），各评估 case_016/095 × 2～5核，全部成功。它们是查看既有检验结果后的诊断；原选择标签保留，但不构成新的独立检验。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp007_20260924_components_diagnosis4 --algorithm components --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp008_20260924_baseline_diagnosis16 --algorithm baseline --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 16 --timeout 60 --workers 2 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/diagnose_partition_regressions.py --output A题/solution/results/scratch/partition_regression_recheck
```

前两条重跑须更换实验名；诊断脚本默认核对既有四次实验，可直接用第三条在新目录重建报告。如需分析另一次复跑，另存脚本并更新 `RUNS`，保留原脚本。输出包括输入哈希、脚本快照、32格对照与最晚完成核心的时间线分解。参见 [诊断报告](results/scratch/partition_regression_20260924_final/REPORT.md)。这阶段尚未实现第三版。

## 第三版：单连通图依赖收缩

新增 `src/branch_scheduler.py` 与 `--algorithm branches`。在计算量上限内安全收缩依赖边，再按关键路径优先分核；多分量图沿用v002。固定倍率4，每配置1个候选。该倍率用于收缩计算量上限，不保证任务数量正好等于核数×4。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp009_20260924_branches_development --algorithm branches --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp010_20260924_branches_holdout --algorithm branches --selection A题/solution/experiments/v003_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp011_20260924_baseline_holdout --algorithm baseline --selection A题/solution/experiments/v003_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
```

复跑须更换实验名。`experiments/summarize_v003.py` 核对固定实验的参数、原始材料、冻结源码、候选数量及完整配置后汇总；拒绝覆盖已存在输出，复跑汇总需另存脚本并修改输出位置。开发集4快4慢，新检验8快；case_016仍未利用多核。13项测试及400个方案合法性检查通过，尚未全量模拟。详见 [v003结果](results/problem_1/v003/summary_20260924/REPORT.md)；检验前决策见 [v003_selection.json](experiments/v003_selection.json)。

## 第四版：保留分叉边界

使用 `--algorithm forks`。固定倍率4，仅修改合并条件；原始评估器不变。case_016实现多核并行，但大量任务与搬运增加；新检验4快4慢，不作为统一替代。共15项测试通过。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp012_20260924_forks_development --algorithm forks --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp013_20260924_forks_holdout --algorithm forks --selection A题/solution/experiments/v004_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp014_20260924_baseline_holdout --algorithm baseline --selection A题/solution/experiments/v004_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp015_20260924_forks_retry --algorithm forks --selection A题/solution/results/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 --cores 2 3 --blocks-per-core 4 --timeout 120 --workers 1 --single-reference A题/solution/results/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
```

所有复跑都须更换实验名。汇总脚本 `experiments/summarize_v004.py` 核对输入哈希、参数、配置、冻结源码及重试方案一致性；保留首次状态，只补失败项。输出已存在时拒绝覆盖。重建汇总需另存脚本并修改输出目录和对应实验路径。结果见 [v004报告](results/problem_1/v004/summary_20260924/REPORT.md)，选择记录见 [v004_selection.json](experiments/v004_selection.json)。
