# A 题第一问实验

## 第三问 v003 全量入口（2026-09-26）

**全量已完成并通过审计：500/500配置，无失败或超时。** 择优后69项改善、431项持平，五核逐图耗时降幅平均0.3940%；直接候选有166项退化，仍需保留基线保护。见[正式报告](outputs/10_problem3/v003_full_20260926/REPORT.md)、[500份方案包](outputs/10_problem3/v003_full_20260926/selected_plans.zip)。图表与附表已核验，下一步整理第三问正文与结果解释。

新入口支持逐操作保存、断点恢复、结果哈希核验、同方案去重、并发锁及超时进程树清理。算法仍为冻结的v003：baseline+width1按Cache Makespan择优。旧冻结入口保留原样。

```powershell
# 新实验目录必须未占用；exp121为本次正式全量编号。
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_v003_full.py' --experiment exp121_20260926_v003_full
# 中断后用同一参数与 --resume；成功结果不重新计算，失败/超时不自动重试。
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_v003_full.py' --experiment exp121_20260926_v003_full --resume
# 完成后独立核验500配置与全部A/B/C/D对照。
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/report_problem3_v003_full.py' 'A题/solution/outputs/10_problem3/raw/problem_3/v003/exp121_20260926_v003_full'
```

仅基础设施预检查可以指定`--cases`、`--cores`、`--max-actions`、`--no-reuse`，其结果不标为全量。正式运行不修改算法、输入、配置或冻结脚本；变更会触发恢复拒绝。预检查见[记录](outputs/10_problem3/raw/scratch/full_preflight_20260926/REPORT.md)。

图表脚本`experiments/publish_problem3_v003_full.py`使用已有基础Python环境中的Matplotlib；评估仍使用A题虚拟环境。生成的PNG/SVG/PDF、图数据与500份方案包均保存在outputs/10_problem3下。

## 第二问入口

**v011 全量已完成：400/400 项成功，五核均值 4.040692。** 见 [正式报告](outputs/09_problem2/v011_summary_20260926/REPORT.md)与[400 个方案](outputs/09_problem2/v011_summary_20260926/v011_plans.zip)。69 项测试和完整审计通过；本轮新增 1327 次完整评估，复用的 v010 前置成本另列。所有本轮进程已结束。新入口 `experiments/run_problem2_active_cores.py --experiment 新编号 --cases 用例列表 --cores 2 3 4 5 --freeze A题/solution/experiments/problem2_v011_selection.json`。可选 `--generation-cache A题/solution/outputs/09_problem2/raw/problem_2/v010/exp107_20260925_portfolio_full` 复用经哈希核对的旧生成与同核数结果，所有新方案重新评估。省略缓存参数可冷启动；当前选择增量验证，成本须包含已披露的前置成本。已有实验目录不可覆盖，脚本没有自动续跑功能；中断后先读 CONTEXT 和清单，另建恢复批次。


### 历史 v010

**v010 全量已完成。** 100 图 × 2～5 核共 400 项全部成功，五核均值 **4.006185**。见 [正式报告](outputs/09_problem2/v010_summary_20260925/REPORT.md)与[400 个方案](outputs/09_problem2/v010_summary_20260925/v010_plans.zip)。固定双候选真实评估择优，共生成 800 候选、执行 613 次完整评估，额外成本已披露，65 项测试通过。全量及后续三图探索进程均已结束。

复现使用新的实验编号，入口 `experiments/run_problem2_portfolio.py`，`--cases` 指定用例，`--cores 2 3 4 5`，`--freeze A题/solution/experiments/problem2_v010_selection.json`。全量结果由 `experiments/summarize_problem2_portfolio.py` 核对；该汇总器目前固定指向 exp107，不可误用为新批次汇总。旧实验目录禁止覆盖。

当时的自动选择活跃核数方向现已由 v011 完成；[三图机制验证](outputs/09_problem2/raw/scratch/idle_cores_probe_20260925/REPORT.md)保留为探索记录。详细状态以 [CONTEXT.md](CONTEXT.md)为准。

### 以下为历史 v009 及更早版本记录

**v009 全量已完成。** 当前完整交付见 [v009 报告](outputs/09_problem2/v009_summary_20260925/REPORT.md)，全部 100 图 × 2～5 核成功结果已核对；五核均值 3.9774。旧暂停/恢复批次已结束，不要直接重跑。复现需新实验编号，并披露最多四个候选的核内准备成本、60 秒初始生成预算及 300 秒超时补测预算。完整尝试和失败均有记录。

下面保留各阶段入口说明，当前完成状态以上述报告为准。


本轮按暂停记录恢复，使用 `experiments/resume_problem2_adaptive.py`：核对旧结果后，exp104 复用两个已生成方案并补跑 295 项未启动配置；exp105 顺序处理生成超时。旧暂停清单保留。恢复入口同样拒绝覆盖已存在的新批次，后续如再次暂停必须先读最新 CONTEXT.md。汇总使用 `experiments/summarize_problem2_adaptive.py`，包含所有失败与人工中断的成本边界。


最新优化候选：`--algorithm adaptive`（问题 2 v009），最多四个核内评分候选、一次最终全局评估，生成预算须显式设为 60 秒。设计见 [v009 设计](experiments/problem2_v009_DESIGN.md)，全量运行入口为 `experiments/run_problem2_adaptive_full.py`，两个工作进程分别覆盖 50 图 × 2～5 核，已有目录拒绝覆盖。完成后使用 `experiments/summarize_problem2_adaptive.py` 审计并汇总；当前是否完成以 CONTEXT.md 为准。


新增优化候选为 `--algorithm split_components`（问题 2 v008）：按计算权重识别过大的连通块，允许拆分后重新分核；未触发的图保持 v007。设计及固定预算见 [v008 设计](experiments/problem2_v008_DESIGN.md)。复现时使用独立实验编号，例如：

```powershell
python -B A题/solution/experiments/run_problem2.py --algorithm split_components --experiment expNEW_split --cases case_056 --cores 2 3 4 5
```

新版完整覆盖范围以 [v008 五核报告](outputs/09_problem2/v008_summary_20260925/REPORT.md)为准；下面的 v007 仍为原 2～5 核完整交付。运行器对 Windows 临时文件锁只重试清单原子写入，不自动重跑生成或评估。

仅对一个输入生成第二问 v007 方案（`--plan` 使用新文件名，父目录须已存在）：

```powershell
python -B A题/solution/experiments/run_problem2.py --worker generate --algorithm paired_order --input A题/data/case_001.json --config A题/data/config.txt --n 4 --plan A题/solution/outputs/09_problem2/example_case001_n4.json
```

正式成绩应另用 `A题/code/multicore_cut_evaluate_problem_2.py` 与同一配置评估，或使用下述完整实验入口自动保存记录。

全量分批入口：`python -B A题/solution/experiments/run_problem2_full.py`；每批 10 图，依次运行 v007、v002、单核，共 900 个评估配置，生成/评估预算保持 30/180 秒。已启动的目录不能重复创建；`--resume` 只跳过已经完整结束的批次，发现部分目录会拒绝并要求另立恢复实验。全量结束后用 `python -B A题/solution/experiments/summarize_problem2_full.py` 核对并导出逐图表、曲线和方案 ZIP。

当前固定方法为 `--algorithm paired_order`（问题 2 v007），900 次全量评估已全部成功并核对，见[正式全量结果](outputs/09_problem2/full_summary_20260925/REPORT.md)。`component_order`（v005）和 `operation_order`（v006）为无收益的历史探索，仅用于复现。v007 保持每配置一个候选；全量既有目录不能直接重跑覆盖。

固定用例与预算见[第二问实验方案](experiments/problem2_PLAN.md)，当前开发基线见[结果报告](outputs/09_problem2/开发集基线.md)。静态用例选择脚本为 `experiments/prepare_problem2_selection.py`；开发报告脚本为 `experiments/summarize_problem2_development.py`，两者均拒绝覆盖已存在产物。

第二问工作流程与当前步骤见 [CONTEXT.md](CONTEXT.md)，已完成的规则与运行基础见[阶段报告](outputs/09_problem2/规则验证与对照.md)。新实验使用独立名称：

```powershell
python -B A题/solution/experiments/run_problem2.py --experiment expNEW_scene_b --algorithm baseline_b --cases case_093 case_078 --cores 2 3 4 5
```

算法选项为 `baseline_a`、`baseline_b`、`regions_a`、`regions_b`、`single`；后缀指分配时的等待近似，全部由问题 2 评估器评估。单核使用 `--algorithm single --cores 1`。默认生成预算 30 秒、评估预算 180 秒，可通过 `--generation-timeout`、`--evaluation-timeout` 显式设置；不覆盖旧实验、不自动重试。早期 `run_problem2_baseline.py` 和 `run_problem2_regions.py` 仅作为原型复现入口保留。

自编代码与结果均在本目录；`../code`、`../data`、`../docs` 只读。仅需 Python 标准库，当前验证环境为 Python 3.11。

按解题顺序浏览代码、报告和汇总表，请从 [outputs/README.md](outputs/README.md) 进入。每步的 `raw/` 保存完整原始运行记录，`原始运行记录.zip` 是对应备份。实验脚本通过 `experiments/result_paths.py` 读写这些按步骤分类的目录。

## 从工作区根目录运行

```powershell
python -B -m unittest discover -s A题/solution/tests -v
python -B A题/solution/experiments/run_baseline.py profile --experiment exp001_20260924_profile
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp002_20260924_baseline --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --blocks-per-core 4 --timeout 60 --workers 2
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

成本感知合并候选（v005/v006）按串行边的直接张量字节数/60 bytes per cycle 与100/1000周期等待估算合并收益，并限制合并计算量；v007预计算张量边界索引。开发对照见 [报告](outputs/05_cost/raw/problem_1/v005/summary_20260924/REPORT.md)。这些版本尚未证明能减少连通图碎片，也没有进入独立检验；不要作为默认算法。

`summary.csv` 是逐用例结果，`aggregate.csv` 按核数及 tune/holdout 分组。若单核参考或多核成绩缺失，对应组不生成完整平均加速比。`completed` 只代表该实验的预定范围结束，不代表第一问全部完成。

评估超时会终止对应评估子进程并记为 timeout，不替换用例或排除失败。两个评估进程并发时，墙钟时间受竞争影响，不能把它当作严格的独占运行性能测试。

## 只重试失败项

`--cases` 和 `--cores` 可限制为已冻结名单内的用例、核数子集，不改变切图算法。首轮两个单核参考超时后，按下列命令重试：

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp003_20260924_single_retry --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_014 case_016 --cores 1 --blocks-per-core 4 --timeout 300 --workers 1
python -B A题/solution/experiments/summarize_recovery.py A题/solution/outputs/01_baseline/raw/problem_1/v001/exp002_20260924_baseline A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry
```

汇总工具只允许成功重试补充失败项，拒绝替换原有成功结果，并核对算法源码、切块参数和原始材料哈希一致。汇总结果入口为重试目录中的 `COMBINED_REPORT.md` 和 `metrics/combined_summary.csv`；首次超时及重试仍各自留档。汇总脚本实际版本另存为 `source/recovery_summary.py` 并登记哈希。重新运行实验产生新的目录后，可用这份快照重建汇总；目标目录已有汇总时拒绝覆盖。

本轮已取得 32 个多核结果和 7 个单核参考（39/40 项）；`case_014` 的单核参考在 300 秒重试中仍超时，因此 8 张图的总体平均加速比暂不报告。具体状态见 [CONTEXT.md](CONTEXT.md)。

当前没有 Git 提交基点；通过每个实验的源代码快照与哈希追溯，不将工作区内其他未跟踪材料一并提交。

## 第二版的调参与检验

固定配置、原始评估器与 v001 相同。调参阶段分别测试每核目标 Task 倍率 4 与 16；选择倍率 16 后在 [v002_selection.json](experiments/v002_selection.json) 冻结，再运行检验集合。下面给出最终设置命令；重跑同样须更换实验名：

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --algorithm components --experiment exp005_20260924_components_tune16 --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_093 case_061 case_034 case_014 --cores 2 3 4 5 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --blocks-per-core 16 --timeout 60 --workers 2
python -B A题/solution/experiments/run_baseline.py benchmark --algorithm components --experiment exp006_20260924_components_holdout --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_078 case_095 case_039 case_016 --cores 2 3 4 5 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --blocks-per-core 16 --timeout 60 --workers 2
python -B A题/solution/experiments/compare_versions.py --baseline A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv --runs A题/solution/outputs/02_components/raw/problem_1/v002/exp005_20260924_components_tune16 A题/solution/outputs/02_components/raw/problem_1/v002/exp006_20260924_components_holdout --selection-decision A题/solution/experiments/v002_selection.json
```

倍率 4 的调参复现：将第一条命令的实验名换成新名称，`--blocks-per-core` 改为 `4`。全部历史实验见 [INDEX.md](experiments/INDEX.md)。

查看 [v002 结论与限制](outputs/02_components/raw/problem_1/v002/exp006_20260924_components_holdout/FINDINGS.md) 和 [逐配置比较表](outputs/02_components/raw/problem_1/v002/exp006_20260924_components_holdout/metrics/version_comparison.csv)：最终 32 项全部评估成功，25 快、1 平、6 慢；检验集合为 9 快、1 平、6 慢。不是全部 100 张图的正式结论。版本间时间比不等于单核/多核加速比；当前仍不报告缺少 case_014 单核分母的完整平均加速比。

诊断入口 `experiments/diagnose_singlecore.py` 会创建独立副本，只作探索性阶段计时和栈采样，不提供正式成绩。记录在 `outputs/01_baseline/raw/scratch/case014_stage_probe_safe_20260924`；已定位到全局事件循环反复扫描操作列表的热点，原程序未改。

## 退步图的算法与粒度对照

新增 exp007（v002、倍率4）与 exp008（v001、倍率16），各评估 case_016/095 × 2～5核，全部成功。它们是查看既有检验结果后的诊断；原选择标签保留，但不构成新的独立检验。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp007_20260924_components_diagnosis4 --algorithm components --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp008_20260924_baseline_diagnosis16 --algorithm baseline --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 16 --timeout 60 --workers 2 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/diagnose_partition_regressions.py --output A题/solution/outputs/02_components/raw/scratch/partition_regression_recheck
```

前两条重跑须更换实验名；诊断脚本默认核对既有四次实验，可直接用第三条在新目录重建报告。如需分析另一次复跑，另存脚本并更新 `RUNS`，保留原脚本。输出包括输入哈希、脚本快照、32格对照与最晚完成核心的时间线分解。参见 [诊断报告](outputs/02_components/raw/scratch/partition_regression_20260924_final/REPORT.md)。这阶段尚未实现第三版。

## 第三版：单连通图依赖收缩

新增 `src/branch_scheduler.py` 与 `--algorithm branches`。在计算量上限内安全收缩依赖边，再按关键路径优先分核；多分量图沿用v002。固定倍率4，每配置1个候选。该倍率用于收缩计算量上限，不保证任务数量正好等于核数×4。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp009_20260924_branches_development --algorithm branches --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp010_20260924_branches_holdout --algorithm branches --selection A题/solution/experiments/v003_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp011_20260924_baseline_holdout --algorithm baseline --selection A题/solution/experiments/v003_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
```

复跑须更换实验名。`experiments/summarize_v003.py` 核对固定实验的参数、原始材料、冻结源码、候选数量及完整配置后汇总；拒绝覆盖已存在输出，复跑汇总需另存脚本并修改输出位置。开发集4快4慢，新检验8快；case_016仍未利用多核。13项测试及400个方案合法性检查通过，尚未全量模拟。详见 [v003结果](outputs/03_branches/raw/problem_1/v003/summary_20260924/REPORT.md)；检验前决策见 [v003_selection.json](experiments/v003_selection.json)。

## 第四版：保留分叉边界

使用 `--algorithm forks`。固定倍率4，仅修改合并条件；原始评估器不变。case_016实现多核并行，但大量任务与搬运增加；新检验4快4慢，不作为统一替代。共15项测试通过。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp012_20260924_forks_development --algorithm forks --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 case_095 --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 2 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp013_20260924_forks_holdout --algorithm forks --selection A题/solution/experiments/v004_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp014_20260924_baseline_holdout --algorithm baseline --selection A题/solution/experiments/v004_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 60 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp015_20260924_forks_retry --algorithm forks --selection A题/solution/outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/metrics/selected_cases.json --cases case_016 --cores 2 3 --blocks-per-core 4 --timeout 120 --workers 1 --single-reference A题/solution/outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/metrics/combined_summary.csv
```

所有复跑都须更换实验名。汇总脚本 `experiments/summarize_v004.py` 核对输入哈希、参数、配置、冻结源码及重试方案一致性；保留首次状态，只补失败项。输出已存在时拒绝覆盖。重建汇总需另存脚本并修改输出目录和对应实验路径。结果见 [v004报告](outputs/04_forks/raw/problem_1/v004/summary_20260924/REPORT.md)，选择记录见 [v004_selection.json](experiments/v004_selection.json)。

## 第八版：保留长分支、合并小分叉与汇合

`src/region_scheduler.py` / `--algorithm regions` 从 v004 分区出发，按当前 Task 的
张量生产/消费集合计算精确边界搬运差值，以有方向的计算路径损失上界筛选局部合并。
公式、手算边界与限制见 [v008_DESIGN.md](experiments/v008_DESIGN.md)。共享带宽时间、
内存溢出和最终 Makespan 仍由原始评估器给出。新版本保留在当前 worktree。

固定倍率4、每配置1个完整方案、180秒评估预算、单进程。下面为原运行命令；复跑必须换新实验编号。

```powershell
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp022_20260924_regions_development --algorithm regions --selection A题/solution/experiments/v008_development_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 180 --workers 1
python -B A题/solution/experiments/run_baseline.py benchmark --experiment exp025_20260924_regions_holdout --algorithm regions --selection A题/solution/experiments/v008_holdout_cases.json --cores 2 3 4 5 --blocks-per-core 4 --timeout 180 --workers 1
```

对应 `forks` / `baseline` 对照使用相同 selection、核数及预算，分别归档为 exp023/024（开发）
和 exp026/027（新检验）。新检验选择与此前看过的用例清单见
[冻结决策](experiments/v008_holdout_selection.json)。`metrics/*_partition.json`
记录每次接受的合并、前后 Task 数、计算关键路径和边界字节。

汇总脚本 `experiments/summarize_regions.py` 接受 `--candidate`、`--comparators`、
`--freeze`、`--split development|holdout`、`--output`；输出目录须不存在。
它核对源码冻结哈希、输入与预算一致、完整配置、CSV与原始指标一致，
并逐配置核对边界预测和原始评估器。汇总目录另存脚本快照与输入文件哈希。
26项测试已通过；测试通过与方案合法不代表全量性能完成。

本轮已完成的[总报告](outputs/06_regions/raw/problem_1/v008/summary_20260924/REPORT.md)：
48次评估全部成功；v008开发8项及新检验8项均快于v004，相对v001合计11快5慢。
`experiments/report_v008.py`核对两阶段审计、冻结时间和哈希后生成总报告；默认输出已存在时拒绝覆盖。

## 第九版：固定运行两候选，再按原始评估结果选择

`src/portfolio_scheduler.py` 保留冻结的 v001、v008，依次生成并评估两个方案，
选择 Makespan 更小的成功方案，完全持平选 v001。每候选生成30秒、评估180秒，
无重试、不并发；所有候选都计入求解成本。一个候选失败标为degraded，两个失败
不输出最终方案。420秒为分阶段子进程预算之和，验证/归档开销另计。

新入口 `experiments/run_portfolio.py` 读取冻结文件中的候选、参数、用例和核数，
运行前核对源码和输入哈希。运行使用归档的规划器快照，原始评估器及配置不变。
每个候选保存在 `candidates/case_NNN_nK/v001或v008/`，包含方案、结果、时间线、
命令、生成与评估日志、状态；最终方案在 `plans/`，两候选成本在
`metrics/candidates.csv`，组合成本和选择在 `metrics/summary.csv`。

下面是本轮命令；复跑必须换新实验编号，汇总必须换新的输出目录：

```powershell
python -B A题/solution/experiments/run_portfolio.py --experiment exp028_20260924_portfolio_development --freeze A题/solution/experiments/v009_selection.json --split development
python -B A题/solution/experiments/run_portfolio.py --experiment exp029_20260924_portfolio_holdout --freeze A题/solution/experiments/v009_selection.json --split holdout
python -B A题/solution/experiments/summarize_portfolio.py --runs A题/solution/outputs/07_portfolio/raw/problem_1/v009/exp028_20260924_portfolio_development A题/solution/outputs/07_portfolio/raw/problem_1/v009/exp029_20260924_portfolio_holdout --freeze A题/solution/experiments/v009_selection.json --output A题/solution/outputs/08_full/raw/problem_1/v009/summary_20260924
```

开发流程2项、新图8项共20次候选评估全部成功；34项测试通过。新图case_064/063
在2～5核中4项选v001、4项选v008，新图配置总耗时51.811秒。新图相对v001为
4快4平，这包含额外一次评估的搜索成本，不是同预算单算法比较。
见[总报告](outputs/07_portfolio/raw/problem_1/v009/summary_20260924/REPORT.md)、
[冻结决策](experiments/v009_selection.json)和[策略说明](experiments/v009_DESIGN.md)。
该小范围阶段当时尚未完成全量；当前全量结果见下一节。

## v009 全量分批评估（已完成）

**第一问全量评估已完成并核对（2026-09-25）**：100张图、400个多核配置、100个单核参考、800个候选结果均成功。本轮无算法失败或超时；另有1次用户主动暂停导致的评估中断，已保留并恢复。v009在2/3/4/5核的平均加速比分别为1.7684/2.4128/2.9518/3.4136，均为100个逐图比值的算术平均。相对v001多核基线360快、40平、0慢；这是双候选择优，需披露额外评估成本，不是等预算比较。相对单核仍有4/6/2/1项更慢。

[全量报告](outputs/08_full/raw/problem_1/v009/full_summary_20260924/REPORT.md)保存了逐图表和SVG/PDF/PNG曲线；[完成核对记录](outputs/08_full/raw/problem_1/v009/completion_audit_20260925.json)记录文件哈希、均值复算和图形检查。原始输入、冻结算法及旧实验保持不变。已记录多核求解6666.312秒为下界（一次人工中断的旧耗时未落盘）；单核评估累计3620.125秒。

**下一步**：整理第一问数学模型、算法伪代码和结果分析，解释少数多核比单核慢的配置；第二、三问尚未开展。当前无评估任务运行，无需再次启动旧驱动命令。

### 首次启动与暂停历史

2026-09-24 21:58北京时间暂停，所有评估进程已停止。已完成383/400个多核配置，
100个单核参考尚未开始；剩余17个多核配置及续跑要求见
[暂停记录](outputs/08_full/raw/problem_1/v009/PAUSE_20260924.md)。下面保留首次启动命令用于追溯；
当前不要直接执行第一条，它会拒绝部分完成的exp039。续跑需独立恢复实验，保留旧结果。

冻结文件 `experiments/v009_full_selection.json` 列出100张图及其哈希，按非COPY操作数
从小到大分为10批。exp030–039每批10图×4核数×2候选；exp040–049每批10个
单核参考。候选预算与v009不变，单核参考统一1800秒，无重试，批次顺序执行。
旧单核程序原始哈希存在换行符差异，因此100个单核参考全部重新计算。

```powershell
python -B A题/solution/experiments/run_full_suite.py --freeze A题/solution/experiments/v009_full_selection.json
python -B A题/solution/experiments/summarize_full_suite.py --freeze A题/solution/experiments/v009_full_selection.json --output A题/solution/outputs/08_full/raw/problem_1/v009/full_summary_20260924
```

第二条须在全部批次结束后运行；输出目录不得已存在。脚本核对100个单核、400个
多核配置、800个候选和源快照/原始成绩/最终方案哈希；缺少任一单核分母时不报告
完整100图平均值。可用均值为各图加速比的算术平均，输出逐图表和SVG/PDF/PNG曲线。

总进度在 `outputs/08_full/raw/problem_1/v009/full_progress_20260924.json`，当前批进度在各批
`progress.json`。同一冻结记录再次运行只跳过已登记完成的批次；存在中断/未登记
目录时明确停止，不覆盖或悄悄补跑。需要恢复中断配置时另建冻结记录与实验编号。

### 本次恢复命令记录（已结束）

用户再次要求继续后，新增exp050_20260924_resume接续17项，随后运行原定exp040–049。
原full_progress与PAUSE文件保留为暂停历史；新的总进度是resume_progress_20260924.json。

```powershell
python -B A题/solution/experiments/run_resume_suite.py --recovery-freeze A题/solution/experiments/v009_resume_selection.json
python -B A题/solution/experiments/summarize_full_suite.py --freeze A题/solution/experiments/v009_full_selection.json --recovery-freeze A题/solution/experiments/v009_resume_selection.json --output A题/solution/outputs/08_full/raw/problem_1/v009/full_summary_20260924
```

以上命令已经运行完毕，结果已保存，不要重复启动。恢复入口拒绝已有进度文件；重新核对时可执行第二条并指定一个尚不存在的新输出目录，保留原报告。
case_087_n5的成功v001按字节复用，v008复用原方案，仅重复被人工中断的评估；
其余383个完整配置不重跑。原中断耗时无法精确恢复，完整耗时字段保留null，
已记录成本以recorded_*字段给出，汇总只作下界；暂停时间不计入算法成本。

## 第三问启动（2026-09-26）

规则核验、成对入口及复现命令见 [第三问启动报告](outputs/10_problem3/README.md)。已完成七个诊断图、十项测试及 case_001 二核配对链路检查；正式基线尚未启动。

第三问已完成6图×1～5核共30对开发基线，报告见 [开发基线](outputs/10_problem3/v001_development_20260926/REPORT.md)。批量复现与预算见报告；当前尚无第三问优化或全量结论。

第三问v002固定分核排序开发对照已完成，见 [v002报告](outputs/10_problem3/v002_development_20260926/REPORT.md)。主组30配置4快26平，收益有限且不属于Cache专属收益；预留检验尚未开始。

第三问v002预留检验完成：[报告](outputs/10_problem3/v002_reserve_20260926/REPORT.md)。未复现主方法改善，后续全量保留v001固定方案基线。当前尚未完成第三问100图全量。
# 第三问 v003：排查后限制交错（2026-09-26）

新入口：`experiments/run_problem3_bounded.py`；算法：`src/scene_b_bounded_order.py`；冻结配置：`experiments/problem3_v003_selection.json`。

固定分核与子图内容，主组比较原方案和逐个完成独立组件的候选；等候选数对照比较原方案和每次交错两个组件的候选。实际Cache Makespan择优，平局保留原方案。跨核连通组件不变。每个方案均评估无L2/Cache，调度收益和Cache收益分列。

从仓库根目录执行（重复运行须使用未占用的新实验编号）：

```powershell
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_bounded.py' --role development --experiment exp116_20260926_bounded_development
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_bounded.py' --role validation --experiment exp117_20260926_bounded_validation
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/report_problem3_bounded.py' 'A题/solution/outputs/10_problem3/raw/problem_3/v003/exp117_20260926_bounded_validation'
```

开发实验首次调用曾误用已有exp115编号，完成后改为exp116归档；manifest保留实际命令及更名说明。源码/配置/输入变动会触发冻结检查，须另建版本或明确新实验设计，不覆盖本轮记录。

诊断与Windows超时测试限制见`outputs/10_problem3/raw/scratch/timeline_diagnosis_20260926/REPORT.md`。本轮开发+新检验共12图，不代表100图全量完成。

