# Harness Tax Mini

**IdeaSniper demo**: same 5 toy tasks × two harnesses (thin vs fat) on one model backend — measure the **harness tax** (extra tokens / steps / tool fails / latency from prompt+tool ritual), not model IQ.

Inspired by (not a copy of) [HarnessTax](https://harnesstax.github.io/).

## Credits / 致谢

- HarnessTax site: https://harnesstax.github.io/
- Hacker News thread: https://news.ycombinator.com/item?id=49733726

## What “harness tax” means here / 这里的 harness tax 指什么

| | **thin** | **fat** |
|---|---|---|
| System prompt | ~短：concise ReAct | ~长：enterprise FRCP 仪式文 |
| Tools | `calculate`, `run_python`, `finish` | + `plan`, `cite`, `verify`（强制仪式） |
| Behavior | 尽快 `finish` | 先 plan→cite→(tools)→verify→finish；易自我折腾 |

**Tax** = fat − thin（或 fat/thin）在 `tokens_*`、`steps`、`tool_fails`、`latency_ms` 上的差额。  
反直觉点：**更胖的 harness 不一定更准**——仪式本身会引入 verify 失败、错误 finish、banned `import` 等，把简单题搞砸。

## One-command run / 一键跑

```bash
cd /workspace/harness-tax-mini
python3 run.py
# 等价: python3 -m harness_tax_mini
```

- **无需 API key**。优先探测本机 Ollama `http://127.0.0.1:11434`；不可达或无 model 时自动用 **deterministic mock**（仍走真实 harness 循环：tool call / step / token 估算）。
- 输出：
  - `results/run.csv` — 10 行（5 tasks × 2 harnesses）
  - `results/dashboard.html` — 静态页（CSV 已 embed，双击/浏览器打开即可，无需起服务）

Token 计数：优先 `tiktoken`（若已安装）；否则 **`chars/4`**（本次运行用的是 chars/4）。

`requirements.txt`：纯 stdlib，无强制依赖。可选 `pip install tiktoken` 换更准的 token 估算。

## Tasks (pass/fail)

1. `extract_email` — 抽出邮箱  
2. `fix_one_line_bug` — `return a - b` → `return a + b`  
3. `count_words` — 数词  
4. `rewrite_json_key` — `name` → `full_name`  
5. `sort_csv_lines` — 按首列排序 CSV 行  

## How to read the CSV / 怎么读结果

Columns: `task, harness, tokens_in, tokens_out, steps, success, tool_fails, latency_ms`

- 先比 **同 task** 的 thin vs fat：steps / tokens 通常 fat >> thin  
- 再看 **aggregate success**：fat 可能更低（本 demo 的 mock 故意让 fat 在 `sort_csv_lines` 上仪式疲劳后交错答案）  
- `tool_fails`：parse 失败、`ERROR`、`VERIFY_FAIL` 都计入  

打开 `results/dashboard.html` 看 KPI 卡片与条形对比。

## Example run (mock backend, 实测)

```
backend: mock / mock-deterministic-v1
tokens:  chars/4

thin: success=5/5  tokens≈1026  steps=7   tool_fails=0  latency_ms≈84
fat:  success=4/5  tokens≈15468 steps=28  tool_fails=3  latency_ms≈793
tax ratio tokens ≈ 15×   steps ≈ 4×
```

Fat 在 `sort_csv_lines` 上 FAIL：先 `run_python` 触发 banned `import`，仪式走完后疲劳交了**未排序**结果。

## 踩坑 (filled after actually building/running)

1. **`python` 不在 PATH，只有 `python3`**  
   环境里 `python run.py` → `command not found`。文档和入口统一写成 `python3`。这是最基础却最容易写进 README 又跑挂的坑。

2. **Ollama 探测返回 000 / unreachable**  
   `curl` 到 `127.0.0.1:11434` 失败时必须静默 fallback mock，且 mock 仍要走完整 ReAct 环，否则 CSV 全 0、dashboard 没对比意义。不要在“没 key”时直接 exit。

3. **Fat 的 verify 会惩罚 markdown fences**  
   企业风 system prompt 鼓励“用 fence 展示候选答案”，但 `verify` 工具故意 `VERIFY_FAIL` fences。这是刻意的 harness 自相矛盾：仪式 prompt 与 gate 工具打架 → 多步 + tool_fails。真实系统里类似“style guide vs linter”也很常见。

4. **`run_python` 禁 `import`，但 mock 起初写了 `import json`**  
   thin 的 `rewrite_json_key` 第一版因此 `tool_fails=1`，幸好后面仍 `finish` 正确答案。修复：sandbox 已注入 `json`，action input 里直接 `json.dumps` 即可。教训：**工具沙箱规则必须和 demo agent 的 action 对齐**，否则你在测 harness 还是在测自己写的 prompt 笔误说不清。

5. **Mock latency 原本全是 0ms**  
   纯 CPU mock 太快，`latency_ms` 列无区分度。给 thin/fat 加了极短 `sleep`（每步 ~12ms / ~28ms），CSV 才能看出 fat 因 steps 多而 latency 堆高——否则“税”只剩 token/steps，读者会以为 latency 列坏了。

6. **Token 是累计按“每轮全量 messages”估算**  
   `tokens_in` 把每一 turn 的 prompt 再算一遍并累加，会放大多步 harness 的税（符合“上下文越滚越大”的直觉）。若改成只计增量，fat/thin 倍率会下降——读数前先看清定义。

7. **Dashboard 选择 embed CSV 而不是 fetch**  
   `file://` 打开时 `fetch(run.csv)` 常被浏览器 CORS/本地限制干掉。生成时把 rows JSON 写进 HTML，双击就能看。

## Layout

```
harness-tax-mini/
  run.py
  README.md
  requirements.txt
  harness_tax_mini/
    __init__.py
    __main__.py
    tasks.py          # 5 tasks + checkers
    tools.py          # calculate / run_python / plan / cite / verify
    model.py          # Ollama detect + mock ReAct brain
    harness.py        # thin/fat loops
    tokens.py         # tiktoken or chars/4
    runner.py         # 5×2 → CSV
    dashboard.py      # CSV → static HTML
  results/
    run.csv
    dashboard.html
```

## License note

Demo code for education. HarnessTax name/site credited above; this repo is a tiny independent MVP.
