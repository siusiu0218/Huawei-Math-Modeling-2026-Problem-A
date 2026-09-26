# 第三问 v004 全量运行冻结方案

冻结日期：2026-09-26。状态：**流程已冻结，尚未启动全量**。

## 1. 固定范围与算法

- 问题3，算法v004；计划实验编号`exp129_20260926_v004_full`，仅预留，不创建运行目录。
- case_001～case_100，每图1、2、3、4、5核，共500个配置。每核数均报告100图，不排除失败或慢例。
- 每配置四候选：exp121已审计的v003入选方案作为baseline，及窗口w4/w10/w16，sticky=0.5。单核执行相同候选规则。
- Cache Makespan最小者入选；同值依次优先baseline、w4、w10、w16。没有随机搜索或新增调参。
- 每个候选均评估同方案无L2和Cache：共4000个逻辑评估槽位，不等于4000次新增计算。新增窗口方案最多1500次生成，baseline为复制。
- 开源bandcomp借鉴来源及MIT许可保持在源文件和快照中，不声称原创。

## 2. 固定评估配置

原始评估器保持不变。L1=524288 bytes，UB=131072 bytes，DDR=60 bytes/cycle，Cache=1048576 bytes、250 bytes/cycle，跨核COPY等待500 cycles。继续按用户批准的原评估器口径计算，并披露命中读取完成后可能重新插入FIFO的行为。

生成30秒、评估180秒超时；单运行进程按配置顺序执行，不另加并行搜索或自动重试。所有候选、失败和超时均保留。

## 3. 冻结与结果复用

`freeze.json`固定算法、入口、工作进程、审计脚本、相关依赖、原始代码/配置、100图、500份baseline、复用来源和演练证据的SHA-256。源代码及配置快照位于本目录`snapshot/`。

启动或恢复前运行只读冻结检查。哈希不匹配即停止核查，不静默更新清单。算法改变需新版本；流程修订也须记录原因、重新演练和新实验编号，不覆盖旧结果。

外部复用仅限已接入的exp121/123/124。exp127/128只作入口演练证据，不新增到运行复用来源。图、方案、配置、评估器、结果及来源manifest均须匹配；来源不匹配时当前入口报错停止，不跳过核验。没有匹配方案时正常计算。

内部仅对与baseline完全相同的方案按现有入口规则去重；不临时增加其他去重策略。成功复用、实际执行、内部复制及中断尝试分别保留记录。历史搜索成本非零。

## 4. 运行与恢复

代码位置：`D:/workspace/HuaWei`；使用`A题/.venv/Scripts/python.exe`，保持现有环境。单目录并发锁、原子manifest保存；操作前登记running，重启后未完成尝试标为interrupted，使用新attempt路径。成功产物哈希改变则拒绝恢复。

失败/超时不自动重试，也不通过删记录或放宽时间上限掩盖。出现问题先记录并报告；旧运行保留。全部操作结束的`evaluated`不代表验收通过。

以下为**后续获准启动时**的固定命令，本轮不执行运行命令。

```powershell
# 1. 只读检查；必须退出码0
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/check_problem3_v004_freeze.py'
# 2. 新运行，不传cases/cores/max-actions/no-reuse或故障注入参数
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_v004_full.py' --experiment exp129_20260926_v004_full
# 3. 中断时，先重复步骤1，再用同名实验恢复
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_v004_full.py' --experiment exp129_20260926_v004_full --resume
# 4. 运行结束后独立审计
& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/report_problem3_v004_full.py' 'A题/solution/outputs/10_problem3/raw/problem_3/v004/exp129_20260926_v004_full'
```

核验与执行分步进行：步骤1失败不能执行后续步骤。这是固定操作规程；未修改已演练入口来自动调用新冻结检查。

## 5. 验收及交付

- 恰好500唯一配置，每配置四候选均有合法方案和有效配对结果。任何候选失败均使整体审计不完整，不能只靠baseline成功宣布完成。
- 检查固定配置、任务依赖、核数、来源哈希、Cache容量和命中率、跨核等待、无L2/Cache搬运口径一致。
- 独立重算择优，保留直接候选快/平/慢、最终选择和所有反例；500份入选方案与逐配置附表可追溯。
- A=baseline无L2，B=baseline Cache，C=入选Cache，D=入选无L2。A/B、B/C、D/C分别报告；按每核数先逐图算比值再取100图算术平均。耗时下降比例另算，不与平均比值混用。
- 主要判断依据是Makespan；报告搬运量、命中率、候选数、生成时间、实际评估时间、复用数量及运行墙钟时间。不能以提高Cache比为目的牺牲最终耗时。
- 结果包括manifest、代码/输入快照、全部方案/指标/日志、comparison.csv、summary.json、REPORT.md、audit_provenance.json及selected_plans。
- 100图均曾用于v003，不称全新独立测试集。小样本收益不外推；全量无收益、失败或Cache变慢均如实报告，不现场调参后仍称冻结验证。

## 6. 已完成的启动准备

exp127最终4配置恢复演练通过；重复运行0新增操作；exp128禁用复用的8份完整JSON与对应复用结果一致；10项保护测试通过。证据摘要与日志纳入冻结清单。这里只冻结流程，不改变当前正式成绩：v003仍是已完成全量的版本，v004尚待正式全量验收。
