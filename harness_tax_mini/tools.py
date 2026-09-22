"""Shared tool implementations for thin and fat harnesses."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def tool_calculate(expr: str) -> str:
    """Safe-ish arithmetic / simple expression eval via AST."""
    expr = (expr or "").strip()
    if not expr:
        return "ERROR: empty expression"
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Call, ast.Attribute, ast.Name)):
                if isinstance(node, ast.Name) and node.id in {"True", "False", "None"}:
                    continue
                if isinstance(node, ast.Name):
                    return f"ERROR: name not allowed: {node.id}"
                if isinstance(node, (ast.Call, ast.Attribute)):
                    return "ERROR: calls/attributes not allowed"
        return str(eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {}))
    except Exception as e:
        return f"ERROR: {e}"


def tool_run_python(code: str) -> str:
    """Very restricted exec: only allow simple assignments + print/result."""
    code = (code or "").strip()
    if not code:
        return "ERROR: empty code"
    banned = ("import", "open", "exec", "eval", "__", "os.", "sys.", "subprocess")
    lower = code.lower()
    for b in banned:
        if b in lower:
            return f"ERROR: banned token: {b}"
    ns: dict[str, Any] = {}
    try:
        exec(code, {"__builtins__": {"len": len, "str": str, "int": int, "sorted": sorted, "print": print, "list": list, "dict": dict, "json": json, "re": re}}, ns)
        if "result" in ns:
            return str(ns["result"])
        return "OK (no result variable; set result = ...)"
    except Exception as e:
        return f"ERROR: {e}"


def tool_plan(goal: str) -> str:
    """Fat-harness ritual: force a plan step."""
    goal = (goal or "").strip()
    return (
        "PLAN_ACK:\n"
        "1. Restate the goal\n"
        "2. Choose tools\n"
        "3. Execute\n"
        "4. Cite sources\n"
        "5. Verify before finish\n"
        f"Goal received ({len(goal)} chars). Continue with cite then tools."
    )


def tool_cite(claim: str) -> str:
    """Fat-harness ritual: fake citation step (adds latency/tokens)."""
    claim = (claim or "").strip()
    if len(claim) < 8:
        return "ERROR: cite requires a non-trivial claim string"
    return f"CITE_OK: [{claim[:40]}...] — synthetic_ref_v1"


def tool_verify(answer: str) -> str:
    """Fat-harness ritual: verify before finish. Sometimes nitpicks."""
    answer = (answer or "").strip()
    if not answer:
        return "VERIFY_FAIL: empty answer"
    if len(answer) > 500:
        return "VERIFY_FAIL: answer too long"
    # Intentionally picky: answers with trailing spaces or markdown fences fail
    if answer.startswith("```") or answer.endswith("```"):
        return "VERIFY_FAIL: remove markdown fences"
    return f"VERIFY_OK: length={len(answer)}"


THIN_TOOLS = {
    "calculate": {"fn": tool_calculate, "schema": "calculate(expr: str) -> str"},
    "run_python": {"fn": tool_run_python, "schema": "run_python(code: str) -> str  # set result=..."},
    "finish": {"fn": None, "schema": "finish(answer: str)  # end with final answer"},
}

FAT_TOOLS = {
    "plan": {"fn": tool_plan, "schema": "plan(goal: str) -> str  # MUST call first"},
    "cite": {"fn": tool_cite, "schema": "cite(claim: str) -> str  # MUST call before finish"},
    "verify": {"fn": tool_verify, "schema": "verify(answer: str) -> str  # MUST pass before finish"},
    "calculate": {"fn": tool_calculate, "schema": "calculate(expr: str) -> str"},
    "run_python": {"fn": tool_run_python, "schema": "run_python(code: str) -> str"},
    "finish": {"fn": None, "schema": "finish(answer: str)"},
}
