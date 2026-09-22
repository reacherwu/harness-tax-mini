"""Five tiny coding/agent tasks with clear pass/fail checkers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Task:
    id: str
    description: str
    # What the agent should produce as final answer (string comparison after strip/normalize)
    expected: str
    # Optional custom checker; if None, exact match on expected (case-sensitive strip)
    checker: Callable[[str], bool] | None = None

    def check(self, answer: str) -> bool:
        got = (answer or "").strip()
        if self.checker is not None:
            return self.checker(got)
        return got == self.expected.strip()


def _check_email(ans: str) -> bool:
    return ans.strip().lower() == "alice@example.com"


def _check_bugfix(ans: str) -> bool:
    # Fixed line: return a + b  (was return a - b)
    cleaned = " ".join(ans.strip().split())
    return cleaned in ("return a + b", "return a+b") or "a + b" in cleaned.replace(" ", "")


def _check_wordcount(ans: str) -> bool:
    try:
        return int(ans.strip().split()[0]) == 7
    except (ValueError, IndexError):
        return False


def _check_json_key(ans: str) -> bool:
    import json

    try:
        obj = json.loads(ans)
        return obj.get("full_name") == "Ada Lovelace" and "name" not in obj
    except Exception:
        # also accept compact rewrite without strict JSON if key present
        s = ans.replace(" ", "")
        return '"full_name":"AdaLovelace"' in s or "'full_name':'Ada Lovelace'" in ans


def _check_csv_sort(ans: str) -> bool:
    lines = [ln.strip() for ln in ans.strip().splitlines() if ln.strip()]
    expected = ["apple,1", "banana,3", "cherry,2"]
    # allow header or not — just the three sorted by first column
    data = [ln for ln in lines if not ln.lower().startswith("fruit")]
    return data == expected


TASKS: list[Task] = [
    Task(
        id="extract_email",
        description=(
            "Extract the email address from this text and return ONLY the email:\n"
            "Contact Alice (alice@example.com) for details."
        ),
        expected="alice@example.com",
        checker=_check_email,
    ),
    Task(
        id="fix_one_line_bug",
        description=(
            "Fix the bug in this one-line function body. Return ONLY the corrected line:\n"
            "def add(a, b): return a - b\n"
            "It should add, not subtract."
        ),
        expected="return a + b",
        checker=_check_bugfix,
    ),
    Task(
        id="count_words",
        description=(
            "Count the words in this sentence and return ONLY the integer:\n"
            "The quick brown fox jumps over lazy"
        ),
        expected="7",
        checker=_check_wordcount,
    ),
    Task(
        id="rewrite_json_key",
        description=(
            'Rewrite this JSON so the key "name" becomes "full_name". '
            "Return ONLY the new JSON object:\n"
            '{"name": "Ada Lovelace", "year": 1815}'
        ),
        expected='{"full_name": "Ada Lovelace", "year": 1815}',
        checker=_check_json_key,
    ),
    Task(
        id="sort_csv_lines",
        description=(
            "Sort these CSV data lines alphabetically by the first column. "
            "Return ONLY the sorted lines (no header):\n"
            "banana,3\ncherry,2\napple,1"
        ),
        expected="apple,1\nbanana,3\ncherry,2",
        checker=_check_csv_sort,
    ),
]


def get_tasks() -> list[Task]:
    return list(TASKS)
