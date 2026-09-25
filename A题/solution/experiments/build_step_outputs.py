"""Build a shallow, browsable copy of the first-question results."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from zipfile import ZIP_STORED, ZipFile
import json


SOLUTION = Path(__file__).resolve().parents[1]
RESULTS = SOLUTION / "results"
OUTPUTS = SOLUTION / "outputs"

STEPS = {
    "01_baseline": ("基线与选图", "exp001–003：图特征、初始基线和单核重试。", ["baseline.py", "graph_analysis.py"]),
    "02_components": ("多连通分量与退步诊断", "exp004–008：分量方案、调参、检验与同参数事后诊断。", ["component_scheduler.py"]),
    "03_branches": ("v003 依赖收缩", "exp009–011：开发、新图检验及同条件基线；400项方案合法性仅验证方案。", ["branch_scheduler.py"]),
    "04_forks": ("v004 保留分叉", "exp012–015：开发、新图检验、基线和超时后的原方案重试。", ["fork_preserving_scheduler.py"]),
    "05_cost": ("v005–v007 成本感知探索", "exp016–018、020–021：开发对照、失败与中断；v007仅做计划检查。", ["cost_aware_scheduler.py", "cost_balanced_scheduler.py", "cost_boundary_scheduler.py"]),
    "06_regions": ("v008 短分叉与汇合", "exp022–027：开发与新图检验，每组都有v008、v004、v001同条件对照。", ["region_scheduler.py"]),
    "07_portfolio": ("v009 双候选设计", "exp028–029：v001与v008双候选开发和新图检验。", ["portfolio_scheduler.py"]),
    "08_full": ("第一问全量评估", "exp030–039多核分批、exp050暂停恢复、exp040–049单核参考；最终100图400配置。", ["portfolio_scheduler.py"]),
}

EXPERIMENT_STEPS = {
    **{f"{n:03d}": "01_baseline" for n in (1, 2, 3)},
    **{f"{n:03d}": "02_components" for n in (4, 5, 6, 7, 8)},
    **{f"{n:03d}": "03_branches" for n in (9, 10, 11)},
    **{f"{n:03d}": "04_forks" for n in (12, 13, 14, 15)},
    **{f"{n:03d}": "05_cost" for n in (16, 17, 18, 20, 21)},
    **{f"{n:03d}": "06_regions" for n in range(22, 28)},
    **{f"{n:03d}": "07_portfolio" for n in (28, 29)},
    **{f"{n:03d}": "08_full" for n in range(30, 51)},
}

REPORTS = {
    "01_baseline": "problem_1/v001/exp002_20260924_baseline/REPORT.md",
    "02_components": "scratch/partition_regression_20260924_final/REPORT.md",
    "03_branches": "problem_1/v003/summary_20260924/REPORT.md",
    "04_forks": "problem_1/v004/summary_20260924/REPORT.md",
    "05_cost": "problem_1/v005/summary_20260924/REPORT.md",
    "06_regions": "problem_1/v008/summary_20260924/REPORT.md",
    "07_portfolio": "problem_1/v009/summary_20260924/REPORT.md",
    "08_full": "problem_1/v009/full_summary_20260924/REPORT.md",
}

CONFIGS = {
    "03_branches": ["v003_selection.json", "v003_holdout_cases.json"],
    "04_forks": ["v004_selection.json", "v004_holdout_cases.json"],
    "05_cost": ["v005_selection.json", "v006_selection.json", "v007_selection.json"],
    "06_regions": ["v008_DESIGN.md", "v008_selection.json", "v008_holdout_selection.json"],
    "07_portfolio": ["v009_DESIGN.md", "v009_selection.json"],
    "08_full": ["v009_full_selection.json", "v009_resume_selection.json"],
}


def step_for(path: Path) -> str:
    parts = path.relative_to(RESULTS).parts
    if parts[0] == "scratch":
        if parts[1].startswith("partition_regression"):
            return "02_components"
        if parts[1].startswith("v003_"):
            return "03_branches"
        if parts[1].startswith("case014_"):
            return "01_baseline"
    if parts[0] != "problem_1" or len(parts) < 3:
        raise ValueError(f"Unclassified result: {path}")
    version, group = parts[1:3]
    if group.startswith("exp"):
        return EXPERIMENT_STEPS[group[3:6]]
    if version == "v009" and len(parts) == 3:
        return "08_full"
    if group.startswith("full_summary"):
        return "08_full"
    summaries = {"v003": "03_branches", "v004": "04_forks", "v005": "05_cost", "v008": "06_regions", "v009": "07_portfolio"}
    if group.startswith(("summary", "development_summary", "holdout_summary")):
        return summaries[version]
    raise ValueError(f"Unclassified result: {path}")


def main() -> None:
    if OUTPUTS.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUTS}")
    grouped: dict[str, list[Path]] = defaultdict(list)
    for base in (RESULTS / "problem_1", RESULTS / "scratch"):
        for path in base.rglob("*"):
            if path.is_file():
                grouped[step_for(path)].append(path)
    OUTPUTS.mkdir()
    lines = [
        "# 第一问：按解题步骤查看代码与结果",
        "",
        "打开下面任一步骤文件夹，首页只有 `README.md`、`主要报告.md`、主要算法代码、选图配置、汇总表（有则提供）和 `原始运行记录.zip`。",
        "ZIP 内保留原实验的相对路径、方案、指标、日志和冻结源码；日常看结果无需解压。实验原路径和哈希可从各 ZIP 及 `manifest.json` 追溯。",
        "",
        "| 顺序 | 内容 | 状态 |",
        "|---|---|---|",
    ]
    for step, (title, description, code_names) in STEPS.items():
        folder = OUTPUTS / step
        folder.mkdir()
        files = sorted(grouped[step])
        archive = folder / "原始运行记录.zip"
        with ZipFile(archive, "w", compression=ZIP_STORED, allowZip64=True) as zip_file:
            for path in files:
                zip_file.write(path, path.relative_to(RESULTS).as_posix())
        with ZipFile(archive) as zip_file:
            if len(zip_file.namelist()) != len(files) or zip_file.testzip() is not None:
                raise RuntimeError(f"Archive verification failed: {archive}")

        report = RESULTS / REPORTS[step]
        copy2(report, folder / "主要报告.md")
        for name in code_names:
            copy2(SOLUTION / "src" / name, folder / name)
        for name in CONFIGS.get(step, []):
            copy2(SOLUTION / "experiments" / name, folder / name)
        if step == "08_full":
            summary = RESULTS / "problem_1" / "v009" / "full_summary_20260924"
            for name in ("multicore_comparison.csv", "single_references.csv", "candidates.csv", "mean_speedup.csv", "mean_speedup.png", "mean_speedup.svg", "mean_speedup.pdf"):
                copy2(summary / name, folder / name)
            copy2(RESULTS / "problem_1" / "v009" / "completion_audit_20260925.json", folder / "完成核对.json")
        elif step in ("03_branches", "04_forks", "05_cost", "06_regions", "07_portfolio"):
            summary = report.parent
            for path in summary.glob("*.csv"):
                copy2(path, folder / path.name)
        digest = sha256()
        with archive.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        manifest = {
            "step": step,
            "title": title,
            "original_result_files": len(files),
            "raw_archive_sha256": digest.hexdigest(),
            "raw_archive_bytes": archive.stat().st_size,
            "source_results_root": str(RESULTS),
            "main_report_source": str(report.relative_to(RESULTS)),
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "README.md").write_text(
            f"# {title}\n\n{description}\n\n- `主要报告.md`：这一阶段可直接阅读的报告。\n- 同级 `.py` 和配置文件：这一阶段的主要代码与冻结选择条件；运行时的完整代码快照在 ZIP 内。\n- 同级 `.csv`、图表：方便直接查看的汇总产物（如有）。\n- `原始运行记录.zip`：本阶段 {len(files)} 个原始结果文件，含完整方案、逐项指标、日志、源码快照和失败/暂停记录；内部路径与旧结果目录一致。\n- `manifest.json`：本阶段 ZIP 的 SHA-256、原始文件数和报告来源。\n",
            encoding="utf-8",
        )
        lines.append(f"| [{step}：{title}]({step}/README.md) | {description} | {len(files)} 个原始文件已归档 |")
        print(f"{step}: {len(files)} files, {archive.stat().st_size} zip bytes", flush=True)
    lines.extend(["", "第二、三问尚无运行结果。迁移时产生的同名旧文件差异不是独立实验，另见旧目录的迁移说明。", ""])
    (OUTPUTS / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
