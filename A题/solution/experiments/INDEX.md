# 实验目录

- 问题3 v004 | exp129_20260926_v004_full | completed and audited | 100图×1～5核500配置、4候选无L2/Cache配对4000逻辑槽位全部成功；审计passed、失败0；择优205改善295持平。2861次新增评估、1139次外部复用。[正式报告](../outputs/10_problem3/v004_full_20260926/REPORT.md) · [冻结方案](../outputs/10_problem3/v004_run_protocol_20260926/PROTOCOL.md)

- 问题3 v004 | exp125_20260926_v004_preflight | 初步暂停，后续快照更改后保留原目录 | 不续跑、不算完成。
- 问题3 v004 | exp126_20260926_v004_frozen_preflight | 初版恢复通过，成本统计修正前快照 | 中断复用多计1次，最终验收见exp127。
- 问题3 v004 | exp127_20260926_v004_final_preflight | completed and audited | 4配置恢复序列2/4/42/0新增操作，16新增评估+16成功复用；非全量。
- 问题3 v004 | exp128_20260926_v004_fresh_check | completed and audited | 禁用复用1配置8次评估，全部完整JSON与exp127一致；非全量。
- [v004入口与恢复演练总报告](../outputs/10_problem3/raw/scratch/v004_full_preflight_20260926/REPORT.md)：10项保护测试通过；这是全量启动前的演练记录。

- 问题3 v004 | exp124_20260926_window_transfer | completed and audited | 8额外图×2～5核32配置；择优20改善12持平，96直接候选41快12平43慢；116新增评估无失败/超时。预设全量门槛通过；非独立未见数据。[报告](../outputs/10_problem3/raw/problem_3/v004/exp124_20260926_window_transfer/REPORT.md)

- 问题3 v003对外部固定方案 | exp122_20260926_external_replay | 完成 | 6图五核24次配对评估，12个Cache耗时全部精确复现；固定外部提交及MIT许可已存档。
- 问题3 v004 | exp123_20260926_window_pilot | 开发试验完成并核验 | 18新候选5快3平10慢；择优2改善4持平；20新增评估，无失败。非全量、非独立检验。[报告](../outputs/10_problem3/raw/problem_3/v004/exp123_20260926_window_pilot/REPORT.md)

- 2026-09-25 | 问题 3 流程制定 | 尚无正式实验编号 | 阶段 0～6、同方案无 L2/有 Cache 对照及交付门槛已写明；当前待规则核验，未启动基线或全量 | [工作流程](problem3_PLAN.md)

- 2026-09-25 | 问题 2 全量完成 | exp066–095 | v007 400 + v002 400 + 单核 100，900/900 成功，均值与哈希核对通过；相对 v002 251 快 85 平 64 慢 | [正式结果](../outputs/09_problem2/full_summary_20260925/REPORT.md)

- 2026-09-25 | 问题 2 优化与新图检验 | exp061–065 | 80 次评估均成功；v005/v006 无收益，v007 开发和检验各 8 快 8 平 0 慢 | [报告](../outputs/09_problem2/优化与新图检验.md)

- 2026-09-25 | 问题 2 设计 v1 | exp057_20260925_static_selection | 完成 100 图静态特征与 4 开发/4 新检验划分；不读取性能成绩 | [选择记录](../outputs/09_problem2/raw/problem_2/design_v001/exp057_20260925_static_selection/selection.json)
- 2026-09-25 | 问题 2 开发基线汇总 | exp058–060 | 32 多核 + 4 单核全部成功，哈希核对通过；区域方法 16 快 0 平 0 慢 | [报告](../outputs/09_problem2/开发集基线.md)

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
# 第二问原型

- 2026-09-25 | 问题 2 `v001` | `exp051_20260925_scene_b_baseline` | 2 张图 × 2～5 核，8/8 成功 | [记录](../outputs/09_problem2/raw/problem_2/v001/exp051_20260925_scene_b_baseline/manifest.json)
- 2026-09-25 | 问题 2 `v002` | `exp052_20260925_scene_b_regions` | 同配置对照，8/8 成功 | [记录](../outputs/09_problem2/raw/problem_2/v002/exp052_20260925_scene_b_regions/manifest.json)


- 问题 2 `v003` | `exp053_20260925_runner_smoke` | running | [记录](../outputs/09_problem2/raw/problem_2/v003/exp053_20260925_runner_smoke/manifest.json)

- 问题 2 `v003` | `exp053_20260925_runner_smoke` | completed | [记录](../outputs/09_problem2/raw/problem_2/v003/exp053_20260925_runner_smoke/manifest.json)

- 问题 2 `single_v001` | `exp054_20260925_single_smoke` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp054_20260925_single_smoke/manifest.json)

- 问题 2 `single_v001` | `exp054_20260925_single_smoke` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp054_20260925_single_smoke/manifest.json)

- 问题 2 `v004` | `exp055_20260925_regions_a_control` | running | [记录](../outputs/09_problem2/raw/problem_2/v004/exp055_20260925_regions_a_control/manifest.json)

- 问题 2 `v004` | `exp055_20260925_regions_a_control` | completed | [记录](../outputs/09_problem2/raw/problem_2/v004/exp055_20260925_regions_a_control/manifest.json)

- 问题 2 `v002` | `exp056_20260925_regions_b_archive` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp056_20260925_regions_b_archive/manifest.json)

- 问题 2 `v002` | `exp056_20260925_regions_b_archive` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp056_20260925_regions_b_archive/manifest.json)

- 问题 2 `v003` | `exp058_20260925_development_baseline` | running | [记录](../outputs/09_problem2/raw/problem_2/v003/exp058_20260925_development_baseline/manifest.json)

- 问题 2 `v003` | `exp058_20260925_development_baseline` | completed | [记录](../outputs/09_problem2/raw/problem_2/v003/exp058_20260925_development_baseline/manifest.json)

- 问题 2 `v002` | `exp059_20260925_development_regions` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp059_20260925_development_regions/manifest.json)

- 问题 2 `v002` | `exp059_20260925_development_regions` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp059_20260925_development_regions/manifest.json)

- 问题 2 `single_v001` | `exp060_20260925_development_single` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp060_20260925_development_single/manifest.json)

- 问题 2 `single_v001` | `exp060_20260925_development_single` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp060_20260925_development_single/manifest.json)

- 问题 2 `v005` | `exp061_20260925_component_order_development` | running | [记录](../outputs/09_problem2/raw/problem_2/v005/exp061_20260925_component_order_development/manifest.json)

- 问题 2 `v005` | `exp061_20260925_component_order_development` | completed | [记录](../outputs/09_problem2/raw/problem_2/v005/exp061_20260925_component_order_development/manifest.json)

- 问题 2 `v006` | `exp062_20260925_operation_order_development` | running | [记录](../outputs/09_problem2/raw/problem_2/v006/exp062_20260925_operation_order_development/manifest.json)

- 问题 2 `v006` | `exp062_20260925_operation_order_development` | completed | [记录](../outputs/09_problem2/raw/problem_2/v006/exp062_20260925_operation_order_development/manifest.json)

- 问题 2 `v007` | `exp063_20260925_paired_order_development` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp063_20260925_paired_order_development/manifest.json)

- 问题 2 `v007` | `exp063_20260925_paired_order_development` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp063_20260925_paired_order_development/manifest.json)

- 问题 2 `v002` | `exp064_20260925_check_regions` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp064_20260925_check_regions/manifest.json)

- 问题 2 `v002` | `exp064_20260925_check_regions` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp064_20260925_check_regions/manifest.json)

- 问题 2 `v007` | `exp065_20260925_check_paired` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp065_20260925_check_paired/manifest.json)

- 问题 2 `v007` | `exp065_20260925_check_paired` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp065_20260925_check_paired/manifest.json)

- 问题 2 `v007` | `exp066_20260925_full_paired_order_01` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp066_20260925_full_paired_order_01/manifest.json)

- 问题 2 `v007` | `exp066_20260925_full_paired_order_01` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp066_20260925_full_paired_order_01/manifest.json)

- 问题 2 `v007` | `exp067_20260925_full_paired_order_02` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp067_20260925_full_paired_order_02/manifest.json)

- 问题 2 `v007` | `exp067_20260925_full_paired_order_02` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp067_20260925_full_paired_order_02/manifest.json)

- 问题 2 `v007` | `exp068_20260925_full_paired_order_03` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp068_20260925_full_paired_order_03/manifest.json)

- 问题 2 `v007` | `exp068_20260925_full_paired_order_03` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp068_20260925_full_paired_order_03/manifest.json)

- 问题 2 `v007` | `exp069_20260925_full_paired_order_04` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp069_20260925_full_paired_order_04/manifest.json)

- 问题 2 `v007` | `exp069_20260925_full_paired_order_04` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp069_20260925_full_paired_order_04/manifest.json)

- 问题 2 `v007` | `exp070_20260925_full_paired_order_05` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp070_20260925_full_paired_order_05/manifest.json)

- 问题 2 `v007` | `exp070_20260925_full_paired_order_05` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp070_20260925_full_paired_order_05/manifest.json)

- 问题 2 `v007` | `exp071_20260925_full_paired_order_06` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp071_20260925_full_paired_order_06/manifest.json)

- 问题 2 `v007` | `exp071_20260925_full_paired_order_06` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp071_20260925_full_paired_order_06/manifest.json)

- 问题 2 `v007` | `exp072_20260925_full_paired_order_07` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp072_20260925_full_paired_order_07/manifest.json)

- 问题 2 `v007` | `exp072_20260925_full_paired_order_07` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp072_20260925_full_paired_order_07/manifest.json)

- 问题 2 `v007` | `exp073_20260925_full_paired_order_08` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp073_20260925_full_paired_order_08/manifest.json)

- 问题 2 `v007` | `exp073_20260925_full_paired_order_08` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp073_20260925_full_paired_order_08/manifest.json)

- 问题 2 `v007` | `exp074_20260925_full_paired_order_09` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp074_20260925_full_paired_order_09/manifest.json)

- 问题 2 `v007` | `exp074_20260925_full_paired_order_09` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp074_20260925_full_paired_order_09/manifest.json)

- 问题 2 `v007` | `exp075_20260925_full_paired_order_10` | running | [记录](../outputs/09_problem2/raw/problem_2/v007/exp075_20260925_full_paired_order_10/manifest.json)

- 问题 2 `v007` | `exp075_20260925_full_paired_order_10` | completed | [记录](../outputs/09_problem2/raw/problem_2/v007/exp075_20260925_full_paired_order_10/manifest.json)

- 问题 2 `v002` | `exp076_20260925_full_regions_b_01` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp076_20260925_full_regions_b_01/manifest.json)

- 问题 2 `v002` | `exp076_20260925_full_regions_b_01` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp076_20260925_full_regions_b_01/manifest.json)

- 问题 2 `v002` | `exp077_20260925_full_regions_b_02` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp077_20260925_full_regions_b_02/manifest.json)

- 问题 2 `v002` | `exp077_20260925_full_regions_b_02` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp077_20260925_full_regions_b_02/manifest.json)

- 问题 2 `v002` | `exp078_20260925_full_regions_b_03` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp078_20260925_full_regions_b_03/manifest.json)

- 问题 2 `v002` | `exp078_20260925_full_regions_b_03` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp078_20260925_full_regions_b_03/manifest.json)

- 问题 2 `v002` | `exp079_20260925_full_regions_b_04` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp079_20260925_full_regions_b_04/manifest.json)

- 问题 2 `v002` | `exp079_20260925_full_regions_b_04` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp079_20260925_full_regions_b_04/manifest.json)

- 问题 2 `v002` | `exp080_20260925_full_regions_b_05` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp080_20260925_full_regions_b_05/manifest.json)

- 问题 2 `v002` | `exp080_20260925_full_regions_b_05` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp080_20260925_full_regions_b_05/manifest.json)

- 问题 2 `v002` | `exp081_20260925_full_regions_b_06` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp081_20260925_full_regions_b_06/manifest.json)

- 问题 2 `v002` | `exp081_20260925_full_regions_b_06` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp081_20260925_full_regions_b_06/manifest.json)

- 问题 2 `v002` | `exp082_20260925_full_regions_b_07` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp082_20260925_full_regions_b_07/manifest.json)

- 问题 2 `v002` | `exp082_20260925_full_regions_b_07` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp082_20260925_full_regions_b_07/manifest.json)

- 问题 2 `v002` | `exp083_20260925_full_regions_b_08` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp083_20260925_full_regions_b_08/manifest.json)

- 问题 2 `v002` | `exp083_20260925_full_regions_b_08` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp083_20260925_full_regions_b_08/manifest.json)

- 问题 2 `v002` | `exp084_20260925_full_regions_b_09` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp084_20260925_full_regions_b_09/manifest.json)

- 问题 2 `v002` | `exp084_20260925_full_regions_b_09` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp084_20260925_full_regions_b_09/manifest.json)

- 问题 2 `v002` | `exp085_20260925_full_regions_b_10` | running | [记录](../outputs/09_problem2/raw/problem_2/v002/exp085_20260925_full_regions_b_10/manifest.json)

- 问题 2 `v002` | `exp085_20260925_full_regions_b_10` | completed | [记录](../outputs/09_problem2/raw/problem_2/v002/exp085_20260925_full_regions_b_10/manifest.json)

- 问题 2 `single_v001` | `exp086_20260925_full_single_01` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp086_20260925_full_single_01/manifest.json)

- 问题 2 `single_v001` | `exp086_20260925_full_single_01` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp086_20260925_full_single_01/manifest.json)

- 问题 2 `single_v001` | `exp087_20260925_full_single_02` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp087_20260925_full_single_02/manifest.json)

- 问题 2 `single_v001` | `exp087_20260925_full_single_02` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp087_20260925_full_single_02/manifest.json)

- 问题 2 `single_v001` | `exp088_20260925_full_single_03` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp088_20260925_full_single_03/manifest.json)

- 问题 2 `single_v001` | `exp088_20260925_full_single_03` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp088_20260925_full_single_03/manifest.json)

- 问题 2 `single_v001` | `exp089_20260925_full_single_04` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp089_20260925_full_single_04/manifest.json)

- 问题 2 `single_v001` | `exp089_20260925_full_single_04` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp089_20260925_full_single_04/manifest.json)

- 问题 2 `single_v001` | `exp090_20260925_full_single_05` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp090_20260925_full_single_05/manifest.json)

- 问题 2 `single_v001` | `exp090_20260925_full_single_05` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp090_20260925_full_single_05/manifest.json)

- 问题 2 `single_v001` | `exp091_20260925_full_single_06` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp091_20260925_full_single_06/manifest.json)

- 问题 2 `single_v001` | `exp091_20260925_full_single_06` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp091_20260925_full_single_06/manifest.json)

- 问题 2 `single_v001` | `exp092_20260925_full_single_07` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp092_20260925_full_single_07/manifest.json)

- 问题 2 `single_v001` | `exp092_20260925_full_single_07` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp092_20260925_full_single_07/manifest.json)

- 问题 2 `single_v001` | `exp093_20260925_full_single_08` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp093_20260925_full_single_08/manifest.json)

- 问题 2 `single_v001` | `exp093_20260925_full_single_08` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp093_20260925_full_single_08/manifest.json)

- 问题 2 `single_v001` | `exp094_20260925_full_single_09` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp094_20260925_full_single_09/manifest.json)

- 问题 2 `single_v001` | `exp094_20260925_full_single_09` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp094_20260925_full_single_09/manifest.json)

- 问题 2 `single_v001` | `exp095_20260925_full_single_10` | running | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp095_20260925_full_single_10/manifest.json)

- 问题 2 `single_v001` | `exp095_20260925_full_single_10` | completed | [记录](../outputs/09_problem2/raw/problem_2/single_v001/exp095_20260925_full_single_10/manifest.json)

- 问题 2 `v008` | `exp096_20260925_split_development` | running | [记录](../outputs/09_problem2/raw/problem_2/v008/exp096_20260925_split_development/manifest.json)

- 问题 2 `v008` | `exp096_20260925_split_development` | interrupted | [记录](../outputs/09_problem2/raw/problem_2/v008/exp096_20260925_split_development/manifest.json)

- 问题 2 `v008` | `exp097_20260925_split_controls` | running | [记录](../outputs/09_problem2/raw/problem_2/v008/exp097_20260925_split_controls/manifest.json)

- 问题 2 `v008` | `exp097_20260925_split_controls` | completed | [记录](../outputs/09_problem2/raw/problem_2/v008/exp097_20260925_split_controls/manifest.json)

- 问题 2 `v008` | `exp098_20260925_split_check` | running | [记录](../outputs/09_problem2/raw/problem_2/v008/exp098_20260925_split_check/manifest.json)

- 问题 2 `v008` | `exp098_20260925_split_check` | completed | [记录](../outputs/09_problem2/raw/problem_2/v008/exp098_20260925_split_check/manifest.json)

- 问题 2 `v008` | `exp099_20260925_split_full5` | running | [记录](../outputs/09_problem2/raw/problem_2/v008/exp099_20260925_split_full5/manifest.json)

- 问题 2 `v008` | `exp099_20260925_split_full5` | completed | [记录](../outputs/09_problem2/raw/problem_2/v008/exp099_20260925_split_full5/manifest.json)

- 问题 2 v008 本轮汇总：exp096/097 开发 6 项、exp098 检查 20 项、exp099 五核全量 100 项成功；exp096 清单写入中断记录保留。五核均值 3.9145607827；[报告](../outputs/09_problem2/v008_summary_20260925/REPORT.md)。

- 问题 2 `v009` | `exp100_20260925_adaptive_dev` | running | [记录](../outputs/09_problem2/raw/problem_2/v009/exp100_20260925_adaptive_dev/manifest.json)

- 问题 2 `v009` | `exp100_20260925_adaptive_dev` | completed | [记录](../outputs/09_problem2/raw/problem_2/v009/exp100_20260925_adaptive_dev/manifest.json)

- 问题 2 `v009` | `exp101_20260925_adaptive_check` | running | [记录](../outputs/09_problem2/raw/problem_2/v009/exp101_20260925_adaptive_check/manifest.json)

- 问题 2 `v009` | `exp101_20260925_adaptive_check` | completed | [记录](../outputs/09_problem2/raw/problem_2/v009/exp101_20260925_adaptive_check/manifest.json)

- 问题 2 `v009` | `exp102_20260925_adaptive_full_a` | running | [记录](../outputs/09_problem2/raw/problem_2/v009/exp102_20260925_adaptive_full_a/manifest.json)

- 问题 2 `v009` | `exp103_20260925_adaptive_full_b` | running | [记录](../outputs/09_problem2/raw/problem_2/v009/exp103_20260925_adaptive_full_b/manifest.json)

- 问题 2 v009 | exp102/103 | paused_by_user 2026-09-25 | 成功 100/400，3 项生成超时、2 项评估人工中断、295 项未开始；[续跑说明](../outputs/09_problem2/raw/problem_2/v009/PAUSE_20260925.md)。

- 问题 2 v009 | exp104_20260925_adaptive_resume | running | [清单](../outputs/09_problem2/raw/problem_2/v009/exp104_20260925_adaptive_resume/manifest.json)

- 问题 2 v009 | exp104_20260925_adaptive_resume | partial | [清单](../outputs/09_problem2/raw/problem_2/v009/exp104_20260925_adaptive_resume/manifest.json)

- 问题 2 v009 | exp105_20260925_adaptive_timeouts | running | [清单](../outputs/09_problem2/raw/problem_2/v009/exp105_20260925_adaptive_timeouts/manifest.json)

- 问题 2 v009 | exp105_20260925_adaptive_timeouts | completed | [清单](../outputs/09_problem2/raw/problem_2/v009/exp105_20260925_adaptive_timeouts/manifest.json)

- 问题 2 v009 全量完成 | exp102/103 保留 100 项、exp104/105 接续完成 | 400 唯一配置成功，5 次生成超时和 2 次人工暂停保留；五核均值 3.9774019373；[最终报告](../outputs/09_problem2/v009_summary_20260925/REPORT.md)。

- 问题 2 v010 | exp106_20260925_portfolio_dev | running | [清单](../outputs/09_problem2/raw/problem_2/v010/exp106_20260925_portfolio_dev/manifest.json)

- 问题 2 v010 | exp106_20260925_portfolio_dev | completed | [清单](../outputs/09_problem2/raw/problem_2/v010/exp106_20260925_portfolio_dev/manifest.json)

- 问题 2 v010 | exp107_20260925_portfolio_full | running | [清单](../outputs/09_problem2/raw/problem_2/v010/exp107_20260925_portfolio_full/manifest.json)

- 问题 2 v010 | exp107_20260925_portfolio_full | completed | [清单](../outputs/09_problem2/raw/problem_2/v010/exp107_20260925_portfolio_full/manifest.json)

- 问题 2 探索性机制检验 | idle_cores_probe_20260925 | completed | 三图、五核配置保留三个空闲核；不计为新算法全量成绩。

- 问题 2 v010 | exp107_20260925_portfolio_full | 完整核对通过：400/400，五核均值 4.006185，613 次完整评估、187 次去重 | [报告](../outputs/09_problem2/v010_summary_20260925/REPORT.md)

- 问题 2 v011 | exp108_20260926_active_dev | running | outputs\09_problem2\raw\problem_2\v011\exp108_20260926_active_dev

- 问题 2 v011 | exp108_20260926_active_dev | completed | outputs\09_problem2\raw\problem_2\v011\exp108_20260926_active_dev

- 问题 2 v011 | exp109_20260926_active_full | running | outputs\09_problem2\raw\problem_2\v011\exp109_20260926_active_full

- 问题 2 v011 | exp109_20260926_active_full | completed | outputs\09_problem2\raw\problem_2\v011\exp109_20260926_active_full

- 问题 2 v011 | exp109_20260926_active_full | 完整核对通过：400/400，五核均值4.040692；新增1327次评估，复用成本单列 | [报告](../outputs/09_problem2/v011_summary_20260926/REPORT.md)

- 问题 3 机制诊断 | rules_v002_20260926 | 七例已归档，重新插入正式配置影响待验证 | [报告](../outputs/10_problem3/README.md)
- 问题 3 v001 | exp110_20260926_pair_smoke | completed：case_001 二核同方案成对链路检查；非正式开发基线；恢复未增加评估 | [清单](../outputs/10_problem3/raw/problem_3/v001/exp110_20260926_pair_smoke/manifest.json)

- 问题 3 v001 | exp111_20260926_development | running | 6 开发图 × 1～5 核 A/B 固定基线

- 问题 3 v001 | exp111_20260926_development | completed | 30/30 pairs | outputs/10_problem3/raw/problem_3/v001/exp111_20260926_development

- 问题 3 v001 | exp111_20260926_development | completed | 30/30 pairs | outputs/10_problem3/raw/problem_3/v001/exp111_20260926_development

- 问题 3 v001 | exp111_20260926_development | 审计通过：30/30配对、60次评估；恢复未增评估；固定配置4次命中完成后插入 | [报告](../outputs/10_problem3/v001_development_20260926/REPORT.md)

- 问题3 v002 | exp112_20260926_order_development | running | fixed placement ordering

- 问题3 v002 | exp112_20260926_order_development | completed | 30 configurations

- 问题3 v002 | exp112_20260926_order_development | 审计通过：30配置、50次新增评估；直接新排序4快14平12慢，主组4快26平 | [报告](../outputs/10_problem3/v002_development_20260926/REPORT.md)

- 问题 3 v001 | exp113_20260926_reserve_baseline | running | 6 预留图 × 1～5 核 A/B 固定基线

- 问题 3 v001 | exp113_20260926_reserve_baseline | completed | 30/30 pairs | outputs/10_problem3/raw/problem_3/v001/exp113_20260926_reserve_baseline

- 问题3 v002 | exp114_20260926_order_reserve | running | fixed placement ordering

- 问题3 v002 | exp114_20260926_order_reserve | completed | 30 configurations

- 问题3 v001 | exp113_20260926_reserve_baseline | 审计通过：30/30配对、60次评估 | [报告](../outputs/10_problem3/v002_reserve_20260926/baseline_REPORT.md)
- 问题3 v002 | exp114_20260926_order_reserve | 审计通过：30配置、80次新增评估；主组全选基线，直接候选0快7平23慢 | [报告](../outputs/10_problem3/v002_reserve_20260926/REPORT.md)

- 问题 3 v001 | exp115_20260926_full | running | 100 全量图 × 1～5 核 A/B 固定基线

- 问题3 v003 | exp116_20260926_bounded_development | 30配置运行完成、独立审计中 | 限制独立组件交错；运行时名称曾误用exp115，完成后更正归档编号，原始命令保留于manifest。
- 问题3 v003 | exp117_20260926_bounded_validation | 待运行 | 预先冻结的新6图×1～5核。

- 问题3 v003 | exp116_20260926_bounded_development | 完成并审计通过 | 30配置、88次评估，主候选8快18平4慢，择优8快22平。
- 问题3 v003 | exp117_20260926_bounded_validation | 完成并审计通过 | 30配置、86次评估，主候选9快18平3慢，择优9快21平。
- [第三问v003排查—优化—检验总报告](../outputs/10_problem3/v003_diagnosis_optimization_20260926/REPORT.md)；全100图仍待完成。

- 问题3 v003 | exp118_20260926_full_preflight | 4配置预检查通过；原快照保留 | 恢复、复用及重复启动。
- 问题3 v003 | exp119_20260926_fresh_preflight | 1配置全新计算通过 | 四份JSON与旧归档一致。
- 问题3 v003 | exp120_20260926_frozen_preflight | 最终入口4配置审计通过 | 中途保存后恢复、再次启动0新增操作。
- 问题3 v003 | exp121_20260926_v003_full | running | 100图×1～5核，冻结算法，配对与复用核验。

- 问题3 v003 | exp121_20260926_v003_full | completed and audited | 500/500配置；914新增评估，624外部复用，462内部去重；择优69改善431持平，直接候选166退化均披露。
- [v003正式全量报告](../outputs/10_problem3/v003_full_20260926/REPORT.md)；500份方案包与PNG/SVG/PDF图表已核验。
