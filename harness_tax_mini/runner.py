"""Run all tasks × harnesses and write CSV + dashboard."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from .dashboard import write_dashboard
from .harness import run_harness
from .model import ChatModel, detect_backend
from .tasks import get_tasks
from .tokens import token_method


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
CSV_PATH = RESULTS / "run.csv"
HTML_PATH = RESULTS / "dashboard.html"

CSV_COLS = [
    "task",
    "harness",
    "tokens_in",
    "tokens_out",
    "steps",
    "success",
    "tool_fails",
    "latency_ms",
]


def run_all(verbose: bool = True) -> list[dict]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    info = detect_backend()
    model = ChatModel(info)
    if verbose:
        print(f"[backend] {info.backend} / {info.model_name}")
        print(f"[tokens]  method={token_method()}")

    rows: list[dict] = []
    for task in get_tasks():
        for harness in ("thin", "fat"):
            if verbose:
                print(f"  → {task.id} @ {harness} ...", end=" ", flush=True)
            tr = run_harness(task, harness, model)
            row = {
                "task": tr.task,
                "harness": tr.harness,
                "tokens_in": tr.tokens_in,
                "tokens_out": tr.tokens_out,
                "steps": tr.steps,
                "success": str(tr.success).lower(),
                "tool_fails": tr.tool_fails,
                "latency_ms": tr.latency_ms,
            }
            rows.append(row)
            if verbose:
                flag = "OK" if tr.success else "FAIL"
                print(
                    f"{flag} steps={tr.steps} tok_in={tr.tokens_in} "
                    f"tok_out={tr.tokens_out} fails={tr.tool_fails} ms={tr.latency_ms}"
                )

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(rows)

    write_dashboard(CSV_PATH, HTML_PATH)
    if verbose:
        print(f"\nWrote {CSV_PATH}")
        print(f"Wrote {HTML_PATH}")
        _print_agg(rows)
    return rows


def _print_agg(rows: list[dict]) -> None:
    def agg(h: str):
        rs = [r for r in rows if r["harness"] == h]
        return {
            "success": sum(1 for r in rs if r["success"] == "true"),
            "n": len(rs),
            "tokens": sum(int(r["tokens_in"]) + int(r["tokens_out"]) for r in rs),
            "steps": sum(int(r["steps"]) for r in rs),
            "fails": sum(int(r["tool_fails"]) for r in rs),
            "ms": sum(int(r["latency_ms"]) for r in rs),
        }

    t, f = agg("thin"), agg("fat")
    print("\n=== Aggregate (harness tax) ===")
    print(f"thin: success={t['success']}/{t['n']} tokens={t['tokens']} steps={t['steps']} tool_fails={t['fails']} latency_ms={t['ms']}")
    print(f"fat:  success={f['success']}/{f['n']} tokens={f['tokens']} steps={f['steps']} tool_fails={f['fails']} latency_ms={f['ms']}")
    if t["tokens"] > 0:
        print(f"tax ratio (fat/thin tokens): {f['tokens']/t['tokens']:.2f}x")
    if t["steps"] > 0:
        print(f"tax ratio (fat/thin steps):  {f['steps']/t['steps']:.2f}x")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    run_all(verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
