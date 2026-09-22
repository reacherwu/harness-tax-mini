"""Thin and fat ReAct harnesses sharing the same ChatModel backend."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .model import ChatModel
from .tasks import Task
from .tokens import count_tokens
from .tools import FAT_TOOLS, THIN_TOOLS


ACTION_RE = re.compile(
    r"Action:\s*(?P<action>\w+)\s*\nAction Input:\s*(?P<input>.*?)(?=\nThought:|\nAction:|\Z)",
    re.DOTALL | re.IGNORECASE,
)


THIN_SYSTEM = """You are a concise coding agent.
Use tools sparingly. Format every step as:
Thought: ...
Action: <tool_name>
Action Input: <args>
Available tools:
- calculate(expr)
- run_python(code)  # assign result=...
- finish(answer)    # final answer only
When done, Action: finish with the exact answer. No markdown fences."""


FAT_SYSTEM = """You are an ENTERPRISE-GRADE Multi-Agent Orchestration Harness (v3.7.2-LTS).

## Mission Charter
You MUST follow the Full Ritual Compliance Protocol (FRCP) before delivering any answer.
Skipping ritual steps is a POLICY VIOLATION and will be logged for audit.

## Mandatory Lifecycle (non-negotiable)
1. ALWAYS call `plan` FIRST with a detailed goal restatement (min 1 call; prefer 2 for quality).
2. ALWAYS call `cite` with a substantive claim BEFORE any domain tool or finish.
3. Prefer an ADDITIONAL `cite` for audit trail on non-trivial tasks.
4. Use domain tools (`calculate`, `run_python`) only after plan+cite.
5. ALWAYS call `verify` on your candidate answer; if VERIFY_FAIL, fix and verify again.
6. ONLY THEN call `finish` with the final answer.

## Style Guide (verbose on purpose)
- Narrate compliance explicitly in Thought lines.
- Prefer thoroughness over speed; latency is acceptable for correctness theater.
- Wrap intermediate candidates in markdown fences when "presenting for review"
  (the verify tool will tell you if that is wrong — follow its guidance).

## Output Format
Thought: ...
Action: <tool_name>
Action Input: <args>

## Tool Catalog
- plan(goal)
- cite(claim)
- verify(answer)
- calculate(expr)
- run_python(code)
- finish(answer)

Remember: a thin answer without ritual is WORSE than a slow compliant answer.
Quality gates > user impatience. This is the harness way.
"""


@dataclass
class TrialResult:
    task: str
    harness: str
    tokens_in: int = 0
    tokens_out: int = 0
    steps: int = 0
    success: bool = False
    tool_fails: int = 0
    latency_ms: int = 0
    answer: str = ""
    log: list[str] = field(default_factory=list)


def _parse_action(text: str) -> tuple[str | None, str]:
    m = ACTION_RE.search(text or "")
    if not m:
        # fallback: look for finish inline
        m2 = re.search(r"Action:\s*(\w+)", text or "", re.I)
        if m2:
            action = m2.group(1).lower()
            # everything after Action Input:
            m3 = re.search(r"Action Input:\s*(.*)", text or "", re.I | re.DOTALL)
            return action, (m3.group(1).strip() if m3 else "")
        return None, ""
    return m.group("action").lower().strip(), m.group("input").strip()


def run_harness(
    task: Task,
    harness: str,
    model: ChatModel,
    max_steps: int = 12,
) -> TrialResult:
    assert harness in ("thin", "fat")
    tools = THIN_TOOLS if harness == "thin" else FAT_TOOLS
    system = THIN_SYSTEM if harness == "thin" else FAT_SYSTEM

    user = f"Task id: {task.id}\n\n{task.description}"
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    result = TrialResult(task=task.id, harness=harness)
    t0 = time.perf_counter()
    final_answer = ""

    for step in range(max_steps):
        result.steps += 1
        # prompt tokens for this call (cumulative estimate: sum of message sizes each turn)
        prompt_text = "\n".join(m["content"] for m in messages)
        result.tokens_in += count_tokens(prompt_text)

        reply = model.complete(messages, harness=harness)
        result.tokens_out += count_tokens(reply)
        result.log.append(reply)
        messages.append({"role": "assistant", "content": reply})

        action, action_input = _parse_action(reply)
        if action is None:
            result.tool_fails += 1
            obs = "Observation: ERROR parse — emit Thought/Action/Action Input"
            messages.append({"role": "user", "content": obs})
            continue

        if action == "finish":
            final_answer = action_input
            break

        if action not in tools or tools[action]["fn"] is None:
            result.tool_fails += 1
            obs = f"Observation ({action}): ERROR unknown tool"
            messages.append({"role": "user", "content": obs})
            continue

        # Fat ritual soft-enforcement: if finish attempted without verify, we already handled finish.
        # Extra: plan/cite/verify failures count as tool_fails when ERROR/FAIL in output
        out = tools[action]["fn"](action_input)
        if out.startswith("ERROR") or "VERIFY_FAIL" in out or "FAIL" in out.split(":")[0]:
            result.tool_fails += 1
        obs = f"Observation ({action}): {out}"
        messages.append({"role": "user", "content": obs})
    else:
        # exhausted steps without finish
        final_answer = final_answer or ""

    result.answer = final_answer
    result.success = task.check(final_answer)
    result.latency_ms = int((time.perf_counter() - t0) * 1000)
    return result
