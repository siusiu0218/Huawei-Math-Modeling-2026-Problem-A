"""Locate first-question run records in the shallow step-based outputs tree."""

from pathlib import Path


SOLUTION = Path(__file__).resolve().parents[1]
OUTPUTS = SOLUTION / "outputs"

_EXPERIMENT_STAGE = {
    **{i: "01_baseline" for i in (1, 2, 3)},
    **{i: "02_components" for i in (4, 5, 6, 7, 8)},
    **{i: "03_branches" for i in (9, 10, 11)},
    **{i: "04_forks" for i in (12, 13, 14, 15)},
    **{i: "05_cost" for i in (16, 17, 18, 20, 21)},
    **{i: "06_regions" for i in range(22, 28)},
    **{i: "07_portfolio" for i in (28, 29)},
    **{i: "08_full" for i in range(30, 51)},
}
_SUMMARY_STAGE = {
    "v003": "03_branches",
    "v004": "04_forks",
    "v005": "05_cost",
    "v008": "06_regions",
    "v009": "07_portfolio",
}


def result_path(relative: str | Path) -> Path:
    """Translate an old results-relative path without changing frozen JSON files."""
    parts = Path(relative).parts
    if parts and parts[0] == "results":
        parts = parts[1:]
    if not parts:
        raise ValueError("empty result path")
    if parts[0] == "scratch" and len(parts) >= 2:
        name = parts[1]
        if name.startswith("partition_regression"):
            stage = "02_components"
        elif name.startswith("v003_"):
            stage = "03_branches"
        elif name.startswith("case014_"):
            stage = "01_baseline"
        else:
            stage = "09_future"
    elif parts[0] == "problem_3" and len(parts) >= 3:
        stage = "10_problem3"
    elif parts[0] == "problem_2" and len(parts) >= 3:
        stage = "09_problem2"
    elif parts[0] == "problem_1" and len(parts) >= 3:
        version, group = parts[1:3]
        if group.startswith("exp") and group[3:6].isdigit():
            stage = _EXPERIMENT_STAGE.get(int(group[3:6]), "09_future")
        elif version == "v009" and len(parts) == 3:
            stage = "08_full"
        elif group.startswith("full_summary"):
            stage = "08_full"
        elif group.startswith(("summary", "development_summary", "holdout_summary")):
            stage = _SUMMARY_STAGE[version]
        else:
            raise ValueError(f"unclassified result path: {relative}")
    else:
        raise ValueError(f"unclassified result path: {relative}")
    return OUTPUTS / stage / "raw" / Path(*parts)


def experiment_path(version: str, experiment: str) -> Path:
    return result_path(Path("problem_1") / version / experiment)
