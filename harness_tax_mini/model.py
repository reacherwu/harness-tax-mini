"""Model backend: local Ollama if available, else deterministic mock."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OLLAMA_BASE = "http://127.0.0.1:11434"


@dataclass
class ModelInfo:
    backend: str  # "ollama" | "mock"
    model_name: str


def detect_backend() -> ModelInfo:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        if not models:
            return ModelInfo("mock", "mock-deterministic-v1")
        name = models[0].get("name") or models[0].get("model") or "unknown"
        return ModelInfo("ollama", name)
    except Exception:
        return ModelInfo("mock", "mock-deterministic-v1")


def _ollama_chat(model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("message") or {}).get("content") or ""


# --- Mock "LLM" that speaks the harness ReAct protocol ---
# Thin path: short, often correct finish quickly.
# Fat path: obeys rituals, sometimes loops / fails verify / wastes steps.


def _extract_task_id(messages: list[dict[str, str]]) -> str:
    blob = "\n".join(m.get("content", "") for m in messages)
    for tid in (
        "extract_email",
        "fix_one_line_bug",
        "count_words",
        "rewrite_json_key",
        "sort_csv_lines",
    ):
        if tid in blob or f"Task id: {tid}" in blob:
            return tid
    # infer from task text
    if "alice@example.com" in blob.lower() or "Extract the email" in blob:
        return "extract_email"
    if "return a - b" in blob or "Fix the bug" in blob:
        return "fix_one_line_bug"
    if "Count the words" in blob or "quick brown fox" in blob:
        return "count_words"
    if "full_name" in blob or '"name": "Ada' in blob:
        return "rewrite_json_key"
    if "banana,3" in blob or "Sort these CSV" in blob:
        return "sort_csv_lines"
    return "unknown"


def _answers(task_id: str) -> str:
    return {
        "extract_email": "alice@example.com",
        "fix_one_line_bug": "return a + b",
        "count_words": "7",
        "rewrite_json_key": '{"full_name": "Ada Lovelace", "year": 1815}',
        "sort_csv_lines": "apple,1\nbanana,3\ncherry,2",
    }.get(task_id, "UNKNOWN")


def _count_tool_obs(messages: list[dict[str, str]], name: str) -> int:
    n = 0
    for m in messages:
        c = m.get("content", "")
        if f"Tool result ({name}):" in c or f"Observation ({name}):" in c:
            n += 1
    return n


def _last_observations(messages: list[dict[str, str]]) -> list[str]:
    obs = []
    for m in messages:
        c = m.get("content", "")
        if c.startswith("Observation") or c.startswith("Tool result"):
            obs.append(c)
    return obs


def _mock_thin(messages: list[dict[str, str]]) -> str:
    """Minimal ReAct: usually finish in 1 step; use tools only when helpful."""
    task_id = _extract_task_id(messages)
    ans = _answers(task_id)
    steps_so_far = sum(1 for m in messages if m.get("role") == "assistant")

    # count_words: optionally use calculate once then finish
    if task_id == "count_words" and steps_so_far == 0:
        return 'Thought: count words with calculate.\nAction: calculate\nAction Input: 1+1+1+1+1+1+1'
    if task_id == "count_words" and _count_tool_obs(messages, "calculate") >= 1:
        return f"Thought: got 7.\nAction: finish\nAction Input: {ans}"

    # rewrite_json: use run_python once
    if task_id == "rewrite_json_key" and steps_so_far == 0:
        return (
            "Thought: rewrite key in python.\n"
            "Action: run_python\n"
            'Action Input: obj={"name":"Ada Lovelace","year":1815}\n'
            'obj["full_name"]=obj.pop("name")\nresult=json.dumps(obj)'
        )
    if task_id == "rewrite_json_key" and _count_tool_obs(messages, "run_python") >= 1:
        # Prefer finishing with known good answer (tool may have quirks)
        return f"Thought: done.\nAction: finish\nAction Input: {ans}"

    # default: finish immediately with correct answer
    return f"Thought: straightforward.\nAction: finish\nAction Input: {ans}"


def _mock_fat(messages: list[dict[str, str]]) -> str:
    """
    Fat harness mock: forced plan → cite → (tools) → verify → finish.
    Intentionally wastes steps; sometimes fails verify or finishes wrong after ritual fatigue.
    """
    task_id = _extract_task_id(messages)
    ans = _answers(task_id)
    steps = sum(1 for m in messages if m.get("role") == "assistant")
    planned = _count_tool_obs(messages, "plan")
    cited = _count_tool_obs(messages, "cite")
    verified = _count_tool_obs(messages, "verify")
    obs = _last_observations(messages)

    # Must plan first
    if planned == 0:
        return (
            f"Thought: harness requires plan before any work.\n"
            f"Action: plan\n"
            f"Action Input: Solve task {task_id} with full ritual compliance"
        )

    # Sometimes call plan AGAIN (tax!) if early
    if planned == 1 and steps <= 2 and task_id in ("extract_email", "count_words"):
        return (
            "Thought: refine the plan for quality (ritual).\n"
            "Action: plan\n"
            "Action Input: Additional planning pass for robustness"
        )

    # Cite before real work
    if cited == 0:
        return (
            "Thought: must cite a claim before proceeding.\n"
            "Action: cite\n"
            f"Action Input: Working on {task_id} per enterprise agent policy"
        )

    # Extra cite on fat path for some tasks
    if cited == 1 and task_id in ("fix_one_line_bug", "sort_csv_lines") and verified == 0 and steps < 5:
        return (
            "Thought: second citation for audit trail.\n"
            "Action: cite\n"
            "Action Input: Secondary claim documenting tool selection rationale"
        )

    # Maybe use a tool unhelpfully
    if task_id == "count_words" and _count_tool_obs(messages, "calculate") == 0 and verified == 0:
        return "Thought: calculate something vaguely related.\nAction: calculate\nAction Input: 2+2"

    if task_id == "sort_csv_lines" and _count_tool_obs(messages, "run_python") == 0 and verified == 0:
        return (
            "Thought: try python sort (may ban import).\n"
            "Action: run_python\n"
            "Action Input: import csv\nresult='fail'"
        )

    # Verify — sometimes with WRONG / fenced answer to trigger VERIFY_FAIL
    if verified == 0:
        # Counterintuitive: fat harness wraps simple answers in fences → verify fails
        if task_id in ("extract_email", "fix_one_line_bug"):
            bad = f"```\n{ans}\n```"
            return f"Thought: verify candidate.\nAction: verify\nAction Input: {bad}"
        return f"Thought: verify candidate.\nAction: verify\nAction Input: {ans}"

    # After verify fail, recover or stumble
    last = obs[-1] if obs else ""
    if "VERIFY_FAIL" in last:
        # One recovery attempt: verify clean answer
        if verified == 1:
            return f"Thought: remove fences and re-verify.\nAction: verify\nAction Input: {ans}"
        # After second verify still confused — finish with polluted answer (fail)
        if task_id == "extract_email":
            return "Thought: ritual complete, ship it.\nAction: finish\nAction Input: Contact Alice (alice@example.com)"
        if task_id == "fix_one_line_bug":
            return "Thought: done enough.\nAction: finish\nAction Input: return a - b  # original?"

    if "VERIFY_OK" in last or verified >= 1:
        # sort_csv: after python ERROR, finish wrong once
        if task_id == "sort_csv_lines" and any("ERROR" in o for o in obs):
            if steps < 8:
                return (
                    "Thought: ignore tool error, finish unsorted (fatigue).\n"
                    "Action: finish\n"
                    "Action Input: banana,3\ncherry,2\napple,1"
                )
        return f"Thought: verified; finish.\nAction: finish\nAction Input: {ans}"

    # Fallback
    return f"Thought: fallback finish.\nAction: finish\nAction Input: {ans}"


def mock_complete(messages: list[dict[str, str]], harness: str) -> str:
    # Synthetic think-time so latency_ms reflects ritual cost even without a real LLM.
    time.sleep(0.012 if harness == "thin" else 0.028)
    if harness == "fat":
        return _mock_fat(messages)
    return _mock_thin(messages)


class ChatModel:
    def __init__(self, info: ModelInfo | None = None):
        self.info = info or detect_backend()

    def complete(self, messages: list[dict[str, str]], harness: str = "thin") -> str:
        if self.info.backend == "ollama":
            try:
                return _ollama_chat(self.info.model_name, messages)
            except Exception as e:
                # fall back mid-run
                return mock_complete(messages, harness) + f"\n# ollama_error_fallback: {e}"
        return mock_complete(messages, harness)
