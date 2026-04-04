"""
Baseline Inference Script — FinanceOps Environment
===================================================
Runs an OpenAI-compatible LLM as a finance operations agent against three
representative tasks (easy / medium / hard) and emits structured logs.

Required environment variables
-------------------------------
API_BASE_URL      LLM endpoint  (default: https://api.openai.com/v1)
MODEL_NAME        Model id       (default: gpt-4o-mini)
OPENAI_API_KEY    API key        (also accepts HF_TOKEN for HuggingFace router)
ENV_BASE_URL      Finance server (default: http://localhost:7860)

STDOUT format
-------------
[START] task=<id> env=finance_ops_env model=<model>
[STEP]  step=<n> action=<json> reward=<0.00> done=<true|false> error=<msg|null>
[END]   success=<true|false> steps=<n> rewards=<r1,r2,...>
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY: str = os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN") or ""
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
ENV_BASE_URL: str = os.getenv("ENV_BASE_URL", "http://localhost:7860")

MAX_STEPS: int = 20
TEMPERATURE: float = 0.0
MAX_TOKENS: int = 256

# task indices: easy (simple_lookup=0), medium (expense_workflow=10), hard (payroll=44)
EVAL_TASK_INDICES: List[int] = [0, 10, 44]

BENCHMARK = "finance_ops_env"

# ---------------------------------------------------------------------------
# Logging helpers  (stdout format required by the spec)
# ---------------------------------------------------------------------------

def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)


def log_step(
    step: int,
    action: str,
    reward: float,
    done: bool,
    error: Optional[str],
) -> None:
    err_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f}"
        f" done={str(done).lower()} error={err_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Environment HTTP helpers
# ---------------------------------------------------------------------------

def env_reset(task_idx: int) -> Dict[str, Any]:
    resp = requests.post(
        f"{ENV_BASE_URL}/api/reset",
        json={"task_idx": task_idx},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_step(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(
        f"{ENV_BASE_URL}/api/step",
        json={"tool_name": tool_name, "arguments": arguments},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_tool_definitions() -> List[Dict[str, Any]]:
    resp = requests.get(f"{ENV_BASE_URL}/api/tool_definitions", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""
    You are a financial operations agent. Your job is to complete finance tasks
    by calling the available tools one at a time.

    Rules:
    - Respond with ONLY a single JSON object, no prose, no markdown fences.
    - Format: {"tool_name": "<name>", "arguments": {<key>: <value>, ...}}
    - Use the EXACT tool names and EXACT parameter names listed in the tool descriptions.
      Do NOT invent parameter names (e.g. use "category" not "expense_category").
    - If a tool call returns an error, read the error carefully and correct the parameter.
    - Valid bank account IDs are: acc_operating, acc_payroll, acc_reserve, acc_fx.
    - Read previous tool results carefully before deciding the next action.
    - When the task is complete, output: {"tool_name": "done", "arguments": {}}
""").strip()


def build_user_message(
    instruction: str,
    tool_defs: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    last_result: Optional[Dict[str, Any]],
) -> str:
    tool_summary = "\n".join(
        f"  - {t['name']}: {t.get('description', '')}" for t in tool_defs
    )
    history_lines = (
        "\n".join(
            f"  step {i+1}: {h['tool_name']}({json.dumps(h['arguments'])}) "
            f"→ {json.dumps(h['result'])}"
            for i, h in enumerate(history[-6:])
        )
        or "  (none yet)"
    )
    last_result_str = json.dumps(last_result) if last_result else "(none)"

    return textwrap.dedent(f"""
        Task: {instruction}

        Available tools:
        {tool_summary}

        Steps taken so far:
        {history_lines}

        Last tool result: {last_result_str}

        What is your next tool call? Reply with JSON only.
    """).strip()


def call_llm(
    client: OpenAI,
    instruction: str,
    tool_defs: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    last_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call the LLM and parse its tool-call JSON response."""
    user_msg = build_user_message(instruction, tool_defs, history, last_result)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        raw = (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", file=sys.stderr, flush=True)
        return {"tool_name": "done", "arguments": {}}

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or "tool_name" not in parsed:
            raise ValueError("missing tool_name")
        parsed.setdefault("arguments", {})
        return parsed
    except Exception as exc:
        print(f"[DEBUG] JSON parse failed ({exc}): {raw!r}", file=sys.stderr, flush=True)
        return {"tool_name": "done", "arguments": {}}


# ---------------------------------------------------------------------------
# Single-episode runner
# ---------------------------------------------------------------------------

def run_episode(
    client: OpenAI,
    task_idx: int,
    tool_defs: List[Dict[str, Any]],
) -> None:
    obs = env_reset(task_idx)
    task_id: str = obs.get("task_id", f"task_{task_idx:03d}")
    instruction: str = obs.get("instruction", "")

    log_start(task=task_id, model=MODEL_NAME)

    history: List[Dict[str, Any]] = []
    rewards: List[float] = []
    steps_taken = 0
    success = False
    last_result: Optional[Dict[str, Any]] = None
    done = obs.get("done", False)

    try:
        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            action = call_llm(client, instruction, tool_defs, history, last_result)
            tool_name: str = action["tool_name"]
            arguments: Dict[str, Any] = action["arguments"]

            if tool_name == "done":
                # Agent signalled completion — take a no-op step to close episode
                # by stepping with an invalid no-op and breaking
                log_step(step, json.dumps(action), 0.0, True, None)
                rewards.append(0.0)
                steps_taken = step
                break

            obs = env_step(tool_name, arguments)
            reward: float = float(obs.get("reward", 0.0))
            done = obs.get("done", False)
            last_result = obs.get("tool_result", {})
            error_msg: Optional[str] = last_result.get("error") if not last_result.get("success", True) else None

            history.append({"tool_name": tool_name, "arguments": arguments, "result": last_result})
            rewards.append(reward)
            steps_taken = step

            action_str = json.dumps({"tool_name": tool_name, "arguments": arguments})
            log_step(step=step, action=action_str, reward=reward, done=done, error=error_msg)

            if done:
                success = reward >= 0.5
                break
        else:
            success = False

    finally:
        log_end(success=success, steps=steps_taken, rewards=rewards)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not API_KEY:
        print(
            "[ERROR] No API key found. Set OPENAI_API_KEY or HF_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    try:
        tool_defs = env_tool_definitions()
    except Exception as exc:
        print(
            f"[ERROR] Could not reach environment at {ENV_BASE_URL}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    for task_idx in EVAL_TASK_INDICES:
        run_episode(client, task_idx, tool_defs)
        print(flush=True)  # blank line between episodes


if __name__ == "__main__":
    main()
