"""Generate a static HTML dashboard from run.csv."""

from __future__ import annotations

import csv
import json
from pathlib import Path


HTML_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Harness Tax Mini — Dashboard</title>
<style>
  :root {{
    --bg: #0f1419; --card: #1a2332; --text: #e7ecf3; --muted: #8b9bb4;
    --thin: #3dd68c; --fat: #f07178; --accent: #59c2ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: var(--bg); color: var(--text); padding: 24px;
  }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .sub {{ color: var(--muted); margin-bottom: 24px; font-size: 0.95rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: var(--card); border-radius: 12px; padding: 16px; border: 1px solid #243044; }}
  .card .label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: .04em; }}
  .card .value {{ font-size: 1.6rem; font-weight: 700; margin-top: 6px; }}
  .thin {{ color: var(--thin); }}
  .fat {{ color: var(--fat); }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 12px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #243044; font-size: 0.9rem; }}
  th {{ color: var(--muted); font-weight: 600; background: #152033; }}
  tr:last-child td {{ border-bottom: none; }}
  .ok {{ color: var(--thin); }}
  .bad {{ color: var(--fat); }}
  .bars {{ display: flex; flex-direction: column; gap: 14px; margin: 24px 0; }}
  .bar-row {{ display: grid; grid-template-columns: 140px 1fr 80px; align-items: center; gap: 10px; }}
  .bar-track {{ background: #243044; border-radius: 6px; height: 22px; overflow: hidden; display: flex; }}
  .bar-seg {{ height: 100%; }}
  .legend {{ display: flex; gap: 16px; margin-bottom: 8px; font-size: 0.85rem; color: var(--muted); }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 0.8rem; }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
  <h1>Harness Tax Mini</h1>
  <p class="sub">Thin vs Fat harness cost on the same 5 toy tasks — “harness tax” = extra tokens / steps / tool fails from ritual.</p>

  <div class="grid" id="kpis"></div>

  <div class="legend">
    <span><span class="dot" style="background:var(--thin)"></span>thin</span>
    <span><span class="dot" style="background:var(--fat)"></span>fat</span>
  </div>
  <div class="bars" id="bars"></div>

  <h2 style="font-size:1.1rem;margin:8px 0 12px;">Per-trial results</h2>
  <table>
    <thead>
      <tr>
        <th>task</th><th>harness</th><th>tokens_in</th><th>tokens_out</th>
        <th>steps</th><th>success</th><th>tool_fails</th><th>latency_ms</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <footer>
    Credits: <a href="https://harnesstax.github.io/">HarnessTax</a> ·
    <a href="https://news.ycombinator.com/item?id=49733726">HN discussion</a>
    · Embed data generated locally; no network required to view.
  </footer>

<script>
const ROWS = {rows_json};

function num(x) {{ return Number(x) || 0; }}
function agg(harness) {{
  const rs = ROWS.filter(r => r.harness === harness);
  const sum = (k) => rs.reduce((a,r) => a + num(r[k]), 0);
  const succ = rs.filter(r => String(r.success).toLowerCase() === 'true' || r.success === '1' || r.success === true).length;
  return {{
    n: rs.length,
    tokens_in: sum('tokens_in'),
    tokens_out: sum('tokens_out'),
    steps: sum('steps'),
    tool_fails: sum('tool_fails'),
    latency_ms: sum('latency_ms'),
    success: succ,
  }};
}}

const thin = agg('thin');
const fat = agg('fat');

const kpis = [
  ['Thin success', thin.success + '/' + thin.n, 'thin'],
  ['Fat success', fat.success + '/' + fat.n, 'fat'],
  ['Thin tokens (in+out)', thin.tokens_in + thin.tokens_out, 'thin'],
  ['Fat tokens (in+out)', fat.tokens_in + fat.tokens_out, 'fat'],
  ['Thin steps', thin.steps, 'thin'],
  ['Fat steps', fat.steps, 'fat'],
  ['Thin tool_fails', thin.tool_fails, 'thin'],
  ['Fat tool_fails', fat.tool_fails, 'fat'],
];
document.getElementById('kpis').innerHTML = kpis.map(([label, val, cls]) =>
  `<div class="card"><div class="label">${{label}}</div><div class="value ${{cls}}">${{val}}</div></div>`
).join('');

const metrics = [
  ['tokens_in', thin.tokens_in, fat.tokens_in],
  ['tokens_out', thin.tokens_out, fat.tokens_out],
  ['steps', thin.steps, fat.steps],
  ['tool_fails', thin.tool_fails, fat.tool_fails],
  ['latency_ms', thin.latency_ms, fat.latency_ms],
];
const maxV = Math.max(...metrics.flatMap(m => [m[1], m[2]]), 1);
document.getElementById('bars').innerHTML = metrics.map(([name, t, f]) => {{
  const tw = (t / maxV * 100).toFixed(1);
  const fw = (f / maxV * 100).toFixed(1);
  return `<div class="bar-row">
    <div>${{name}}</div>
    <div class="bar-track">
      <div class="bar-seg" style="width:${{tw}}%;background:var(--thin)" title="thin ${{t}}"></div>
      <div class="bar-seg" style="width:${{fw}}%;background:var(--fat)" title="fat ${{f}}"></div>
    </div>
    <div style="font-size:0.8rem;color:var(--muted)">${{t}} / ${{f}}</div>
  </div>`;
}}).join('');

document.getElementById('tbody').innerHTML = ROWS.map(r => {{
  const ok = String(r.success).toLowerCase() === 'true' || r.success === '1' || r.success === true;
  return `<tr>
    <td>${{r.task}}</td><td class="${{r.harness}}">${{r.harness}}</td>
    <td>${{r.tokens_in}}</td><td>${{r.tokens_out}}</td><td>${{r.steps}}</td>
    <td class="${{ok?'ok':'bad'}}">${{ok}}</td>
    <td>${{r.tool_fails}}</td><td>${{r.latency_ms}}</td>
  </tr>`;
}}).join('');
</script>
</body>
</html>
"""


def write_dashboard(csv_path: Path, html_path: Path) -> None:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    html = HTML_TMPL.format(rows_json=json.dumps(rows, ensure_ascii=False))
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
