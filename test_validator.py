# test_validator.py — sanity-check rewards are strictly in (0, 1) for every benchmark task.
import math
import os
import sys

import requests

BASE = os.environ.get(
    "FINANCE_OPS_URL", "https://shubhamrasal-finance-ops-env.hf.space"
).rstrip("/")
# TaskGenerator produces 80 tasks (task_001 … task_075).
NUM_TASKS = 75
REQUEST_TIMEOUT_S = 120

# OpenEnv standard endpoints (what the remote validator uses)
RESET_URL = f"{BASE}/reset"
STEP_URL = f"{BASE}/step"


def _reward_invalid(reward) -> bool:
    """
    True if reward is not strictly in the open interval (0, 1).

    Catches endpoints (0, 1), values outside [0, 1], NaN/inf, None, and non-numeric.
    """
    if reward is None:
        return True
    try:
        x = float(reward)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(x):
        return True
    return not (0.0 < x < 1.0)


def _check_task(task_idx: int) -> tuple[bool, str]:
    """
    Reset with explicit task index, run a few noop steps, ensure every reward
    satisfies 0 < reward < 1 (open interval).
    Returns (ok, detail_message).
    """
    try:
        r = requests.post(
            RESET_URL,
            json={"task_idx": task_idx, "seed": 42},
            timeout=REQUEST_TIMEOUT_S,
        )
        r.raise_for_status()
        reset_data = r.json()
    except requests.RequestException as e:
        return False, f"reset HTTP error: {e}"

    reward = reset_data.get("reward")
    obs = reset_data.get("observation") or {}
    task_id = obs.get("task_id", f"task_{task_idx:03d}")

    if _reward_invalid(reward):
        return False, f"{task_id} reset reward={reward!r}"

    for step in range(5):
        try:
            r = requests.post(
                STEP_URL,
                json={
                    "action": {
                        "tool_name": "bank_get_balance",
                        "arguments": {"account_id": "acc_operating"},
                    }
                },
                timeout=REQUEST_TIMEOUT_S,
            )
            r.raise_for_status()
            step_data = r.json()
        except requests.RequestException as e:
            return False, f"{task_id} step {step + 1} HTTP error: {e}"

        reward = step_data.get("reward")
        if _reward_invalid(reward):
            return False, f"{task_id} step {step + 1} reward={reward!r}"

        if step_data.get("done"):
            break

    return True, task_id


def main() -> None:
    print(f"Checking rewards on {NUM_TASKS} tasks at {BASE!r} …", flush=True)
    failures: list[str] = []
    for task_idx in range(NUM_TASKS):
        ok, detail = _check_task(task_idx)
        if ok:
            print(f"  [{task_idx:02d}] {detail} ✓", flush=True)
        else:
            print(f"  [{task_idx:02d}] ❌ {detail}", flush=True)
            failures.append(detail)

    print(flush=True)
    if failures:
        print(f"FAILED: {len(failures)} / {NUM_TASKS} tasks", file=sys.stderr, flush=True)
        sys.exit(1)
    print(
        f"OK: all {NUM_TASKS} tasks — every checked reward satisfied 0 < reward < 1",
        flush=True,
    )


if __name__ == "__main__":
    main()
