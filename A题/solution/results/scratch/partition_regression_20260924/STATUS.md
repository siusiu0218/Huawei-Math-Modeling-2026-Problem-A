# 未完成的诊断草稿

首次脚本在读取 exp002 时断言失败：该历史实验状态为 completed_with_failures（含无关单核超时），而脚本只接受 completed。尚未写出结果，也没有修改输入实验。

后续版本接受已完成且含失败项的历史实验，但逐项要求实际使用的配置状态为 ok。最终记录见 ../partition_regression_20260924_final/REPORT.md。
