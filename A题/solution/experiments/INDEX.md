# 实验目录

## 全量完成（2026-09-25）

exp030–038完整360项 + exp039暂停前23项 + exp050恢复17项，共400项多核配置；exp040–049共100项单核参考；800个候选结果均成功。全量均值（2/3/4/5核）：1.7684/2.4128/2.9518/3.4136。较v001为360快40平0慢，双候选成本单独报告。

[正式全量报告](../outputs/08_full/raw/problem_1/v009/full_summary_20260924/REPORT.md) · [完成核对记录](../outputs/08_full/raw/problem_1/v009/completion_audit_20260925.json)。全量数据与图表已核对；第一问数学模型及论文叙述待整理。以下保留历史阶段状态。

## 全量恢复启动记录（2026-09-24晚，当时进行中）

用户要求继续，exp050_20260924_resume恢复剩余17项；保留exp030–039及暂停记录。
case_087_n5复用原v001和v008方案，仅重启中断的v008评估；原未落盘耗时保留未知，
增加的评估尝试单独披露。随后运行预留exp040–049的100个单核参考。
冻结记录：v009_resume_selection.json。最终400项汇总尚未生成。

## 全量暂停记录（2026-09-24 21:58北京时间）

用户要求保存进度并暂停，已停止驱动及当前评估子进程。exp030–038全部完成并审计；
exp039完成23/40项，标记paused_by_user。累计383/400配置成功，767个候选成功；
case_087_n5/v008人工中断，不计作算法超时。exp040–049为已预留但尚未运行的单核批次。
剩余17个多核配置的恢复实验应从exp050起另立编号，避免覆盖原批次。
见[暂停与续跑说明](../outputs/08_full/raw/problem_1/v009/PAUSE_20260924.md)。

## v009 阶段结论（2026-09-24）

exp028：case_069 × 2/4核开发流程；exp029：case_064/063 × 2～5核新检验。
共10个配置、20次候选评估全部成功，无重试。新检验4项选v001、4项选v008，
相对v001为4快4平，合计51.811秒（两候选均计费）。34项测试通过。
输入、冻结源码、候选文件及最终选择均经[汇总审计](../outputs/07_portfolio/raw/problem_1/v009/summary_20260924/REPORT.md)。
固定双候选不是等预算单算法改进证据；全量尚未开始。本轮工作保存在当前worktree。

- 2026-09-24 | v008 | [短分叉与汇合合并：开发及新检验](../outputs/06_regions/raw/problem_1/v008/summary_20260924/REPORT.md) | exp022–027共48次原始评估全部成功；开发及新检验各8项均快于v004，较v001分别6快2慢/5快3慢。16项边界字节精确核对，26项测试通过；保留候选，非全量完成。

- 2026-09-24 | v005/v006/v007 | [成本感知合并开发对照](../outputs/05_cost/raw/problem_1/v005/summary_20260924/REPORT.md) | exp016/017/020有效评估各8项；exp018 selection格式失败，exp021方案生成中断；v007仅计划检查。v005/v006不作为替代，case_048 Task数反增。

- 2026-09-24 | v004 | [保留分叉对照及结构诊断](../outputs/04_forks/raw/problem_1/v004/summary_20260924/REPORT.md) | exp012/013/014/015；26次新增评估，首次2项超时后原方案重试成功。开发8快，新检验4快4慢；不作为统一替代。

- 2026-09-24 | v003 | [原型对照汇总](../outputs/03_branches/raw/problem_1/v003/summary_20260924/REPORT.md) | exp009/010/011共24次新增原始评估成功；开发4快4慢，新检验8快。保留失败方向，不作为统一替代。
- 2026-09-24 | v003 | [100图×4核数方案合法性](../outputs/03_branches/raw/scratch/v003_all_graph_plan_validation_20260924/results.json) | 400项通过；仅方案验证，无性能模拟。

- 2026-09-24 | 事后诊断 | [退步案例最终报告](../outputs/02_components/raw/scratch/partition_regression_20260924_final/REPORT.md) | 汇总 exp002/006/007/008 的32格对照；补跑16项成功；不是新独立检验。初次读取失败草稿及中间草稿保留在 scratch/partition_regression_20260924 与同名 _r2 目录。

以下流水记录包含原型、失败及中断；当前全量状态以顶部2026-09-25完成记录为准。

- 2026-09-24T04:41:02.715448+00:00 | `v001` | [exp001_20260924_profile](../outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/manifest.json) | profile | running
- 2026-09-24T04:41:12.453702+00:00 | `v001` | [exp001_20260924_profile](../outputs/01_baseline/raw/problem_1/v001/exp001_20260924_profile/manifest.json) | profile | completed
- 2026-09-24T04:42:28.505117+00:00 | `v001` | [exp002_20260924_baseline](../outputs/01_baseline/raw/problem_1/v001/exp002_20260924_baseline/manifest.json) | benchmark | running
- 2026-09-24T04:45:34.413676+00:00 | `v001` | [exp002_20260924_baseline](../outputs/01_baseline/raw/problem_1/v001/exp002_20260924_baseline/manifest.json) | benchmark | completed_with_failures
- 2026-09-24T04:46:41.343341+00:00 | `v001` | [exp003_20260924_single_retry](../outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/manifest.json) | benchmark | running
- 2026-09-24T04:52:20.394320+00:00 | `v001` | [exp003_20260924_single_retry](../outputs/01_baseline/raw/problem_1/v001/exp003_20260924_single_retry/manifest.json) | benchmark | completed_with_failures
- 2026-09-24T09:00:16.748698+00:00 | `v002` | [exp004_20260924_components_tune](../outputs/02_components/raw/problem_1/v002/exp004_20260924_components_tune/manifest.json) | benchmark | running
- 2026-09-24T09:02:28.322939+00:00 | `v002` | [exp004_20260924_components_tune](../outputs/02_components/raw/problem_1/v002/exp004_20260924_components_tune/manifest.json) | benchmark | completed_with_failures
- 2026-09-24T09:02:56.753086+00:00 | `v002` | [exp005_20260924_components_tune16](../outputs/02_components/raw/problem_1/v002/exp005_20260924_components_tune16/manifest.json) | benchmark | running
- 2026-09-24T09:04:20.293848+00:00 | `v002` | [exp005_20260924_components_tune16](../outputs/02_components/raw/problem_1/v002/exp005_20260924_components_tune16/manifest.json) | benchmark | completed
- 2026-09-24T09:06:19.321729+00:00 | `v002` | [exp006_20260924_components_holdout](../outputs/02_components/raw/problem_1/v002/exp006_20260924_components_holdout/manifest.json) | benchmark | running
- 2026-09-24T09:06:45.060075+00:00 | `v002` | [exp006_20260924_components_holdout](../outputs/02_components/raw/problem_1/v002/exp006_20260924_components_holdout/manifest.json) | benchmark | completed
- 2026-09-24T10:37:42.436574+00:00 | `v002` | [exp007_20260924_components_diagnosis4](../outputs/02_components/raw/problem_1/v002/exp007_20260924_components_diagnosis4/manifest.json) | benchmark | running
- 2026-09-24T10:37:55.081555+00:00 | `v002` | [exp007_20260924_components_diagnosis4](../outputs/02_components/raw/problem_1/v002/exp007_20260924_components_diagnosis4/manifest.json) | benchmark | completed
- 2026-09-24T10:38:05.353906+00:00 | `v001` | [exp008_20260924_baseline_diagnosis16](../outputs/02_components/raw/problem_1/v001/exp008_20260924_baseline_diagnosis16/manifest.json) | benchmark | running
- 2026-09-24T10:38:15.504379+00:00 | `v001` | [exp008_20260924_baseline_diagnosis16](../outputs/02_components/raw/problem_1/v001/exp008_20260924_baseline_diagnosis16/manifest.json) | benchmark | completed
- 2026-09-24T10:51:05.739054+00:00 | `v003` | [exp009_20260924_branches_development](../outputs/03_branches/raw/problem_1/v003/exp009_20260924_branches_development/manifest.json) | benchmark | running
- 2026-09-24T10:51:18.830016+00:00 | `v003` | [exp009_20260924_branches_development](../outputs/03_branches/raw/problem_1/v003/exp009_20260924_branches_development/manifest.json) | benchmark | completed
- 2026-09-24T10:51:58.695956+00:00 | `v003` | [exp010_20260924_branches_holdout](../outputs/03_branches/raw/problem_1/v003/exp010_20260924_branches_holdout/manifest.json) | benchmark | running
- 2026-09-24T10:51:58.706335+00:00 | `v001` | [exp011_20260924_baseline_holdout](../outputs/03_branches/raw/problem_1/v001/exp011_20260924_baseline_holdout/manifest.json) | benchmark | running
- 2026-09-24T10:52:01.844677+00:00 | `v003` | [exp010_20260924_branches_holdout](../outputs/03_branches/raw/problem_1/v003/exp010_20260924_branches_holdout/manifest.json) | benchmark | completed
- 2026-09-24T10:52:01.851036+00:00 | `v001` | [exp011_20260924_baseline_holdout](../outputs/03_branches/raw/problem_1/v001/exp011_20260924_baseline_holdout/manifest.json) | benchmark | completed
- 2026-09-24T11:01:02.019764+00:00 | `v004` | [exp012_20260924_forks_development](../outputs/04_forks/raw/problem_1/v004/exp012_20260924_forks_development/manifest.json) | benchmark | running
- 2026-09-24T11:02:38.403828+00:00 | `v004` | [exp013_20260924_forks_holdout](../outputs/04_forks/raw/problem_1/v004/exp013_20260924_forks_holdout/manifest.json) | benchmark | running
- 2026-09-24T11:02:38.406827+00:00 | `v001` | [exp014_20260924_baseline_holdout](../outputs/04_forks/raw/problem_1/v001/exp014_20260924_baseline_holdout/manifest.json) | benchmark | running
- 2026-09-24T11:02:44.577149+00:00 | `v001` | [exp014_20260924_baseline_holdout](../outputs/04_forks/raw/problem_1/v001/exp014_20260924_baseline_holdout/manifest.json) | benchmark | completed
- 2026-09-24T11:02:56.919809+00:00 | `v004` | [exp012_20260924_forks_development](../outputs/04_forks/raw/problem_1/v004/exp012_20260924_forks_development/manifest.json) | benchmark | completed_with_failures
- 2026-09-24T11:03:06.783728+00:00 | `v004` | [exp013_20260924_forks_holdout](../outputs/04_forks/raw/problem_1/v004/exp013_20260924_forks_holdout/manifest.json) | benchmark | completed
- 2026-09-24T11:03:21.300343+00:00 | `v004` | [exp015_20260924_forks_retry](../outputs/04_forks/raw/problem_1/v004/exp015_20260924_forks_retry/manifest.json) | benchmark | running
- 2026-09-24T11:04:54.739703+00:00 | `v004` | [exp015_20260924_forks_retry](../outputs/04_forks/raw/problem_1/v004/exp015_20260924_forks_retry/manifest.json) | benchmark | completed
- 2026-09-24T11:14:20.636749+00:00 | `v005` | [exp016_20260924_cost_aware_development](../outputs/05_cost/raw/problem_1/v005/exp016_20260924_cost_aware_development/manifest.json) | benchmark | running
- 2026-09-24T11:14:28.277624+00:00 | `v005` | [exp016_20260924_cost_aware_development](../outputs/05_cost/raw/problem_1/v005/exp016_20260924_cost_aware_development/manifest.json) | benchmark | completed
- 2026-09-24T11:14:34.604876+00:00 | `v001` | [exp017_20260924_baseline_development](../outputs/05_cost/raw/problem_1/v001/exp017_20260924_baseline_development/manifest.json) | benchmark | running
- 2026-09-24T11:14:37.347579+00:00 | `v001` | [exp017_20260924_baseline_development](../outputs/05_cost/raw/problem_1/v001/exp017_20260924_baseline_development/manifest.json) | benchmark | completed
- 2026-09-24T11:15:37.859942+00:00 | `v006` | [exp018_20260924_cost_balanced_development](../outputs/05_cost/raw/problem_1/v006/exp018_20260924_cost_balanced_development/manifest.json) | benchmark | running
- 2026-09-24T11:15:38.083909+00:00 | `v006` | [exp018_20260924_cost_balanced_development](../outputs/05_cost/raw/problem_1/v006/exp018_20260924_cost_balanced_development/manifest.json) | benchmark | failed
- 2026-09-24T11:15:47.611691+00:00 | `v006` | [exp020_20260924_cost_balanced_development](../outputs/05_cost/raw/problem_1/v006/exp020_20260924_cost_balanced_development/manifest.json) | benchmark | running
- 2026-09-24T11:15:55.307667+00:00 | `v006` | [exp020_20260924_cost_balanced_development](../outputs/05_cost/raw/problem_1/v006/exp020_20260924_cost_balanced_development/manifest.json) | benchmark | completed
- 2026-09-24T11:16:18.899551+00:00 | `v006` | [exp021_20260924_cost_balanced_case016](../outputs/05_cost/raw/problem_1/v006/exp021_20260924_cost_balanced_case016/manifest.json) | benchmark | running
- 2026-09-24T11:16:18Z | `v006` | [exp021_20260924_cost_balanced_case016](../outputs/05_cost/raw/problem_1/v006/exp021_20260924_cost_balanced_case016/manifest.json) | benchmark | interrupted during plan generation; no evaluator rows.
- 2026-09-24T11:43:19.710075+00:00 | `v008` | [exp022_20260924_regions_development](../outputs/06_regions/raw/problem_1/v008/exp022_20260924_regions_development/manifest.json) | benchmark | running
- 2026-09-24T11:45:16.073527+00:00 | `v008` | [exp022_20260924_regions_development](../outputs/06_regions/raw/problem_1/v008/exp022_20260924_regions_development/manifest.json) | benchmark | completed
- 2026-09-24T11:45:36.566693+00:00 | `v004` | [exp023_20260924_forks_matched_development](../outputs/06_regions/raw/problem_1/v004/exp023_20260924_forks_matched_development/manifest.json) | benchmark | running
- 2026-09-24T11:48:48.276150+00:00 | `v004` | [exp023_20260924_forks_matched_development](../outputs/06_regions/raw/problem_1/v004/exp023_20260924_forks_matched_development/manifest.json) | benchmark | completed
- 2026-09-24T11:48:48.799748+00:00 | `v001` | [exp024_20260924_baseline_matched_development](../outputs/06_regions/raw/problem_1/v001/exp024_20260924_baseline_matched_development/manifest.json) | benchmark | running
- 2026-09-24T11:49:22.814381+00:00 | `v001` | [exp024_20260924_baseline_matched_development](../outputs/06_regions/raw/problem_1/v001/exp024_20260924_baseline_matched_development/manifest.json) | benchmark | completed
- 2026-09-24T11:50:26.492086+00:00 | `v008` | [exp025_20260924_regions_holdout](../outputs/06_regions/raw/problem_1/v008/exp025_20260924_regions_holdout/manifest.json) | benchmark | running
- 2026-09-24T11:51:45.236495+00:00 | `v008` | [exp025_20260924_regions_holdout](../outputs/06_regions/raw/problem_1/v008/exp025_20260924_regions_holdout/manifest.json) | benchmark | completed
- 2026-09-24T11:51:46.431958+00:00 | `v004` | [exp026_20260924_forks_matched_holdout](../outputs/06_regions/raw/problem_1/v004/exp026_20260924_forks_matched_holdout/manifest.json) | benchmark | running
- 2026-09-24T11:54:27.176362+00:00 | `v004` | [exp026_20260924_forks_matched_holdout](../outputs/06_regions/raw/problem_1/v004/exp026_20260924_forks_matched_holdout/manifest.json) | benchmark | completed
- 2026-09-24T11:54:28.432152+00:00 | `v001` | [exp027_20260924_baseline_matched_holdout](../outputs/06_regions/raw/problem_1/v001/exp027_20260924_baseline_matched_holdout/manifest.json) | benchmark | running
- 2026-09-24T11:54:40.660384+00:00 | `v001` | [exp027_20260924_baseline_matched_holdout](../outputs/06_regions/raw/problem_1/v001/exp027_20260924_baseline_matched_holdout/manifest.json) | benchmark | completed
- 2026-09-24T12:16:07.958084+00:00 | `v009` | [exp028_20260924_portfolio_development](../outputs/07_portfolio/raw/problem_1/v009/exp028_20260924_portfolio_development/manifest.json) | fixed_portfolio | running
- 2026-09-24T12:16:11.968103+00:00 | `v009` | [exp028_20260924_portfolio_development](../outputs/07_portfolio/raw/problem_1/v009/exp028_20260924_portfolio_development/manifest.json) | fixed_portfolio | completed
- 2026-09-24T12:16:22.898301+00:00 | `v009` | [exp029_20260924_portfolio_holdout](../outputs/07_portfolio/raw/problem_1/v009/exp029_20260924_portfolio_holdout/manifest.json) | fixed_portfolio | running
- 2026-09-24T12:17:15.403281+00:00 | `v009` | [exp029_20260924_portfolio_holdout](../outputs/07_portfolio/raw/problem_1/v009/exp029_20260924_portfolio_holdout/manifest.json) | fixed_portfolio | completed
- 2026-09-24T12:41:55.106457+00:00 | `v009` | [exp030_20260924_full_multicore_01](../outputs/08_full/raw/problem_1/v009/exp030_20260924_full_multicore_01/manifest.json) | full_portfolio | running
- 2026-09-24T12:42:53.097584+00:00 | `v009` | [exp030_20260924_full_multicore_01](../outputs/08_full/raw/problem_1/v009/exp030_20260924_full_multicore_01/manifest.json) | full_portfolio | completed
- 2026-09-24T12:42:53.710367+00:00 | `v009` | [exp031_20260924_full_multicore_02](../outputs/08_full/raw/problem_1/v009/exp031_20260924_full_multicore_02/manifest.json) | full_portfolio | running
- 2026-09-24T12:43:59.702589+00:00 | `v009` | [exp031_20260924_full_multicore_02](../outputs/08_full/raw/problem_1/v009/exp031_20260924_full_multicore_02/manifest.json) | full_portfolio | completed
- 2026-09-24T12:44:00.305529+00:00 | `v009` | [exp032_20260924_full_multicore_03](../outputs/08_full/raw/problem_1/v009/exp032_20260924_full_multicore_03/manifest.json) | full_portfolio | running
- 2026-09-24T12:45:10.074733+00:00 | `v009` | [exp032_20260924_full_multicore_03](../outputs/08_full/raw/problem_1/v009/exp032_20260924_full_multicore_03/manifest.json) | full_portfolio | completed
- 2026-09-24T12:45:10.755220+00:00 | `v009` | [exp033_20260924_full_multicore_04](../outputs/08_full/raw/problem_1/v009/exp033_20260924_full_multicore_04/manifest.json) | full_portfolio | running
- 2026-09-24T12:46:45.236090+00:00 | `v009` | [exp033_20260924_full_multicore_04](../outputs/08_full/raw/problem_1/v009/exp033_20260924_full_multicore_04/manifest.json) | full_portfolio | completed
- 2026-09-24T12:46:45.875534+00:00 | `v009` | [exp034_20260924_full_multicore_05](../outputs/08_full/raw/problem_1/v009/exp034_20260924_full_multicore_05/manifest.json) | full_portfolio | running
- 2026-09-24T12:50:29.161131+00:00 | `v009` | [exp034_20260924_full_multicore_05](../outputs/08_full/raw/problem_1/v009/exp034_20260924_full_multicore_05/manifest.json) | full_portfolio | completed
- 2026-09-24T12:50:29.709215+00:00 | `v009` | [exp035_20260924_full_multicore_06](../outputs/08_full/raw/problem_1/v009/exp035_20260924_full_multicore_06/manifest.json) | full_portfolio | running
- 2026-09-24T12:53:33.178535+00:00 | `v009` | [exp035_20260924_full_multicore_06](../outputs/08_full/raw/problem_1/v009/exp035_20260924_full_multicore_06/manifest.json) | full_portfolio | completed
- 2026-09-24T12:53:33.642366+00:00 | `v009` | [exp036_20260924_full_multicore_07](../outputs/08_full/raw/problem_1/v009/exp036_20260924_full_multicore_07/manifest.json) | full_portfolio | running
- 2026-09-24T12:58:14.820309+00:00 | `v009` | [exp036_20260924_full_multicore_07](../outputs/08_full/raw/problem_1/v009/exp036_20260924_full_multicore_07/manifest.json) | full_portfolio | completed
- 2026-09-24T12:58:15.457787+00:00 | `v009` | [exp037_20260924_full_multicore_08](../outputs/08_full/raw/problem_1/v009/exp037_20260924_full_multicore_08/manifest.json) | full_portfolio | running
- 2026-09-24T13:06:22.126503+00:00 | `v009` | [exp037_20260924_full_multicore_08](../outputs/08_full/raw/problem_1/v009/exp037_20260924_full_multicore_08/manifest.json) | full_portfolio | completed
- 2026-09-24T13:06:22.860581+00:00 | `v009` | [exp038_20260924_full_multicore_09](../outputs/08_full/raw/problem_1/v009/exp038_20260924_full_multicore_09/manifest.json) | full_portfolio | running
- 2026-09-24T13:34:34.514481+00:00 | `v009` | [exp038_20260924_full_multicore_09](../outputs/08_full/raw/problem_1/v009/exp038_20260924_full_multicore_09/manifest.json) | full_portfolio | completed
- 2026-09-24T13:34:34.926572+00:00 | `v009` | [exp039_20260924_full_multicore_10](../outputs/08_full/raw/problem_1/v009/exp039_20260924_full_multicore_10/manifest.json) | full_portfolio | running
- 2026-09-24T14:56:07.871050+00:00 | `v009` | [exp050_20260924_resume](../outputs/08_full/raw/problem_1/v009/exp050_20260924_resume/manifest.json) | operational_recovery | running
- 2026-09-24T15:32:09.214528+00:00 | `v009` | [exp050_20260924_resume](../outputs/08_full/raw/problem_1/v009/exp050_20260924_resume/manifest.json) | operational_recovery | completed
- 2026-09-24T15:32:09.669854+00:00 | `v001` | [exp040_20260924_full_single_01](../outputs/08_full/raw/problem_1/v001/exp040_20260924_full_single_01/manifest.json) | full_single_reference | running
- 2026-09-24T15:32:12.342320+00:00 | `v001` | [exp040_20260924_full_single_01](../outputs/08_full/raw/problem_1/v001/exp040_20260924_full_single_01/manifest.json) | full_single_reference | completed
- 2026-09-24T15:32:12.791454+00:00 | `v001` | [exp041_20260924_full_single_02](../outputs/08_full/raw/problem_1/v001/exp041_20260924_full_single_02/manifest.json) | full_single_reference | running
- 2026-09-24T15:32:16.105632+00:00 | `v001` | [exp041_20260924_full_single_02](../outputs/08_full/raw/problem_1/v001/exp041_20260924_full_single_02/manifest.json) | full_single_reference | completed
- 2026-09-24T15:32:16.570995+00:00 | `v001` | [exp042_20260924_full_single_03](../outputs/08_full/raw/problem_1/v001/exp042_20260924_full_single_03/manifest.json) | full_single_reference | running
- 2026-09-24T15:32:20.381048+00:00 | `v001` | [exp042_20260924_full_single_03](../outputs/08_full/raw/problem_1/v001/exp042_20260924_full_single_03/manifest.json) | full_single_reference | completed
- 2026-09-24T15:32:20.863941+00:00 | `v001` | [exp043_20260924_full_single_04](../outputs/08_full/raw/problem_1/v001/exp043_20260924_full_single_04/manifest.json) | full_single_reference | running
- 2026-09-24T15:32:26.295521+00:00 | `v001` | [exp043_20260924_full_single_04](../outputs/08_full/raw/problem_1/v001/exp043_20260924_full_single_04/manifest.json) | full_single_reference | completed
- 2026-09-24T15:32:26.800597+00:00 | `v001` | [exp044_20260924_full_single_05](../outputs/08_full/raw/problem_1/v001/exp044_20260924_full_single_05/manifest.json) | full_single_reference | running
- 2026-09-24T15:32:48.874371+00:00 | `v001` | [exp044_20260924_full_single_05](../outputs/08_full/raw/problem_1/v001/exp044_20260924_full_single_05/manifest.json) | full_single_reference | completed
- 2026-09-24T15:32:49.299626+00:00 | `v001` | [exp045_20260924_full_single_06](../outputs/08_full/raw/problem_1/v001/exp045_20260924_full_single_06/manifest.json) | full_single_reference | running
- 2026-09-24T15:33:17.165669+00:00 | `v001` | [exp045_20260924_full_single_06](../outputs/08_full/raw/problem_1/v001/exp045_20260924_full_single_06/manifest.json) | full_single_reference | completed
- 2026-09-24T15:33:17.601862+00:00 | `v001` | [exp046_20260924_full_single_07](../outputs/08_full/raw/problem_1/v001/exp046_20260924_full_single_07/manifest.json) | full_single_reference | running
- 2026-09-24T15:34:16.056870+00:00 | `v001` | [exp046_20260924_full_single_07](../outputs/08_full/raw/problem_1/v001/exp046_20260924_full_single_07/manifest.json) | full_single_reference | completed
- 2026-09-24T15:34:16.472385+00:00 | `v001` | [exp047_20260924_full_single_08](../outputs/08_full/raw/problem_1/v001/exp047_20260924_full_single_08/manifest.json) | full_single_reference | running
- 2026-09-24T15:36:24.313582+00:00 | `v001` | [exp047_20260924_full_single_08](../outputs/08_full/raw/problem_1/v001/exp047_20260924_full_single_08/manifest.json) | full_single_reference | completed
- 2026-09-24T15:36:24.748721+00:00 | `v001` | [exp048_20260924_full_single_09](../outputs/08_full/raw/problem_1/v001/exp048_20260924_full_single_09/manifest.json) | full_single_reference | running
- 2026-09-24T15:44:07.205852+00:00 | `v001` | [exp048_20260924_full_single_09](../outputs/08_full/raw/problem_1/v001/exp048_20260924_full_single_09/manifest.json) | full_single_reference | completed
- 2026-09-24T15:44:07.520084+00:00 | `v001` | [exp049_20260924_full_single_10](../outputs/08_full/raw/problem_1/v001/exp049_20260924_full_single_10/manifest.json) | full_single_reference | running
- 2026-09-24T16:32:43.028748+00:00 | `v001` | [exp049_20260924_full_single_10](../outputs/08_full/raw/problem_1/v001/exp049_20260924_full_single_10/manifest.json) | full_single_reference | completed
