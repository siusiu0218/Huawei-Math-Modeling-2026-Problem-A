"""Update live documentation references to the step-organized outputs tree."""

from pathlib import Path
import re

from result_paths import SOLUTION, result_path


DOCUMENTS = [
    SOLUTION / 'README.md',
    SOLUTION / 'CONTEXT.md',
    SOLUTION / 'AGENTS.md',
    SOLUTION / 'experiments/INDEX.md',
    SOLUTION / 'Output/第一问运行结果.md',
]


def replacement(match: re.Match) -> str:
    return result_path(match.group(0)).relative_to(SOLUTION).as_posix()


def main() -> None:
    for document in DOCUMENTS:
        if not document.exists():
            continue
        original = document.read_text(encoding='utf-8')
        revised = re.sub(r'results/(?:problem_1|scratch)/[A-Za-z0-9_./-]+', replacement, original)
        if revised != original:
            document.write_text(revised, encoding='utf-8')


if __name__ == '__main__':
    main()
