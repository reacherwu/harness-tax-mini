# Harness Tax Mini

IdeaSniper demo: the same 5 toy tasks, two harnesses (thin vs fat), one model backend. Measures **harness tax** — extra tokens, steps, tool failures, and latency from prompt and tool ritual — not model IQ.

Inspired by (not a clone of) [HarnessTax](https://harnesstax.github.io/).

## Credits

- HarnessTax site: https://harnesstax.github.io/
- Hacker News thread: https://news.ycombinator.com/item?id=49733726

## What “harness tax” means here

| | **thin** | **fat** |
|---|---|---|
| System prompt | Short, concise ReAct | Long enterprise ritual copy |
| Tools | `calculate`, `run_python`, `finish` | Plus forced `plan`, `cite`, `verify` |
| Behavior | Finish as soon as possible | plan → cite → tools → verify → finish; easy to self-sabotage |

**Tax** is fat minus thin (or fat / thin) on `tokens_*`, `steps`, `tool_fails`, and `latency_ms`.

Counter-intuitive result: a fatter harness is not automatically more accurate. The ceremony itself can cause verify failures, bad finishes, and banned `import` errors that wreck easy tasks.

## One-command run

```bash
python3 run.py
# equivalent: python3 -m harness_tax_mini
```

- No API key required. The runner probes local Ollama at `http://127.0.0.1:11434`. If that is unreachable or has no model, it falls back to a **deterministic mock** that still walks the real harness loop (tool calls, steps, token estimates).
- Outputs:
  - `results/run.csv` — 10 rows (5 tasks × 2 harnesses)
  - `results/dashboard.html` — static page with the CSV embedded; open it in a browser, no server needed

Token counting prefers `tiktoken` if installed, otherwise **chars / 4** (this run used chars / 4).

`requirements.txt` is stdlib-only. Optional: `pip install tiktoken` for a tighter token estimate.

## Tasks (pass / fail)

1. `extract_email` — extract an email address
2. `fix_one_line_bug` — `return a - b` → `return a + b`
3. `count_words` — count words
4. `rewrite_json_key` — `name` → `full_name`
5. `sort_csv_lines` — sort CSV rows by the first column

## How to read the CSV

Columns: `task, harness, tokens_in, tokens_out, steps, success, tool_fails, latency_ms`

- Compare **the same task** thin vs fat: steps and tokens are usually fat >> thin
- Then look at **aggregate success**: fat can be lower (this mock deliberately lets fat fail `sort_csv_lines` after ritual fatigue)
- `tool_fails` counts parse failures, `ERROR`, and `VERIFY_FAIL`

Open `results/dashboard.html` for KPI cards and bar charts.

## Example run (mock backend)

```
backend: mock / mock-deterministic-v1
tokens:  chars/4

thin: success=5/5  tokens≈1026  steps=7   tool_fails=0  latency_ms≈84
fat:  success=4/5  tokens≈15468 steps=28  tool_fails=3  latency_ms≈790
tax ratio tokens ≈ 15×   steps ≈ 4×
```

Fat fails `sort_csv_lines`: `run_python` first hits the banned `import`, then after the ritual it finishes with an **unsorted** answer.

## Build notes (from actually running this)

1. **`python` is not on PATH; only `python3` is.** `python run.py` fails with command not found. Docs and entrypoints use `python3`.

2. **Ollama probe can return unreachable.** Fail soft into the mock, and keep the full ReAct loop. Otherwise the CSV is zeros and the dashboard is meaningless. Do not exit just because there is no API key.

3. **Fat `verify` punishes markdown fences.** The enterprise-style system prompt encourages fenced answers; `verify` then returns `VERIFY_FAIL` on fences. That is an intentional harness contradiction (ritual prompt vs gate tool) and a common real-world pattern, like a style guide fighting a linter.

4. **`run_python` bans `import`, but an early mock used `import json`.** Thin `rewrite_json_key` took a tool fail, then still finished correctly. The sandbox now injects `json`. Lesson: sandbox rules must match the demo agent's actions, or you cannot tell harness tax from your own prompt bug.

5. **Mock latency was 0ms.** Pure CPU mock is too fast for a useful `latency_ms` column. Tiny sleeps (~12ms / ~28ms per thin/fat step) make fat look slower because it takes more steps.

6. **`tokens_in` is recomputed on the full message list every turn and summed.** That magnifies tax for multi-step harnesses (context that keeps growing). Incremental counting would shrink the fat/thin ratio — read the definition first.

7. **The dashboard embeds CSV instead of fetching it.** `file://` plus `fetch(run.csv)` often dies on CORS / local file rules. Rows are written into the HTML so a double-click works.

## Layout

```
harness-tax-mini/
  run.py
  README.md
  requirements.txt
  harness_tax_mini/
    tasks.py
    tools.py
    model.py
    harness.py
    tokens.py
    runner.py
    dashboard.py
  results/
    run.csv
    dashboard.html
```

## License note

Demo code for education. HarnessTax name and site are credited above; this repo is a tiny independent MVP.
