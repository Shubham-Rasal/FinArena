"""Rubric evaluation and weighted reward for FinanceOpsEnv."""

from __future__ import annotations

import re
from typing import Any

try:
    from .tasks import Task
except ImportError:
    from tasks import Task


def _values_match(actual: Any, expected_str: str) -> bool:
    if str(actual) == expected_str:
        return True
    try:
        return float(actual) == float(expected_str)
    except (TypeError, ValueError):
        return False


class RubricEvaluator:
    """Evaluates action logs against task rubric criteria."""

    def __init__(self) -> None:
        self._world: Any = None
        self._checkers = {
            "tool_used": self._check_tool_used,
            "tool_not_used": self._check_tool_not_used,
            "tool_used_any": self._check_tool_used_any,
            "param_value": self._check_param_value,
            "param_contains": self._check_param_contains,
            "tool_order": self._check_tool_order,
            "tool_count": self._check_tool_count,
            "result_contains": self._check_result_contains,
            "cash_sufficient": self._check_cash_sufficient,
            "no_duplicate": self._check_no_duplicate,
            "result_field": self._check_result_field,
            "world_state": self._check_world_state,
        }

    def evaluate(
        self,
        task: Task,
        action_log: list[dict],
        world: Any = None,
        step_count: int = 0,
    ) -> dict:
        self._world = world
        criteria_results = []
        for criterion in task.rubric_criteria:
            check_str = criterion["check"]
            passed = self._evaluate_criterion(check_str, action_log)
            criteria_results.append(
                {
                    "name": criterion["name"],
                    "description": criterion["description"],
                    "passed": passed,
                }
            )

        total = len(criteria_results)
        passed_count = sum(1 for c in criteria_results if c["passed"])
        base_score = passed_count / total if total > 0 else 0.0

        reward = compute_reward(
            task=task,
            action_log=action_log,
            world=world,
            base_score=base_score,
            step_count=step_count,
        )

        return {
            "task_id": task.task_id,
            "criteria_results": criteria_results,
            "score": reward,
            "passed": all(c["passed"] for c in criteria_results),
            "passed_count": passed_count,
            "total_criteria": total,
        }

    def _evaluate_criterion(self, check_str: str, action_log: list[dict]) -> bool:
        parts = check_str.split(":", 1)
        if len(parts) != 2:
            return False
        check_type, check_args = parts[0], parts[1]
        checker = self._checkers.get(check_type)
        if not checker:
            return False
        return checker(check_args, action_log)

    def _check_tool_used(self, tool_name: str, action_log: list[dict]) -> bool:
        return any(a["tool"] == tool_name for a in action_log)

    def _check_tool_not_used(self, tool_name: str, action_log: list[dict]) -> bool:
        return not any(a["tool"] == tool_name for a in action_log)

    def _check_tool_used_any(self, tools_csv: str, action_log: list[dict]) -> bool:
        tool_names = [t.strip() for t in tools_csv.split(",")]
        return any(a["tool"] in tool_names for a in action_log)

    def _check_param_value(self, spec: str, action_log: list[dict]) -> bool:
        match = re.match(r"(\w+)\.(\w+)=(.+)", spec)
        if not match:
            return False
        tool_name, param_name, expected_value = match.groups()

        for action in action_log:
            if action["tool"] == tool_name:
                actual = action["params"].get(param_name)
                if actual is not None and _values_match(actual, expected_value):
                    return True
                updates = action["params"].get("updates", {})
                if param_name in updates and _values_match(updates[param_name], expected_value):
                    return True
        return False

    def _check_param_contains(self, spec: str, action_log: list[dict]) -> bool:
        match = re.match(r"(\w+)\.(\w+)=(.+)", spec)
        if not match:
            return False
        tool_name, param_name, substring = match.groups()
        for action in action_log:
            if action["tool"] == tool_name:
                actual = action["params"].get(param_name, "")
                if substring.lower() in str(actual).lower():
                    return True
        return False

    def _check_tool_order(self, spec: str, action_log: list[dict]) -> bool:
        parts = spec.split("<")
        if len(parts) != 2:
            return False
        tool_a, tool_b = parts[0].strip(), parts[1].strip()
        # Find last occurrence of A before first occurrence of B after it
        # This handles retry patterns: any A before any B is sufficient
        indices_a = [i for i, a in enumerate(action_log) if a["tool"] == tool_a]
        indices_b = [i for i, a in enumerate(action_log) if a["tool"] == tool_b]
        if not indices_a or not indices_b:
            return False
        return min(indices_a) < max(indices_b)

    def _check_tool_count(self, spec: str, action_log: list[dict]) -> bool:
        match = re.match(r"(\w+)>=(\d+)", spec)
        if not match:
            return False
        tool_name, min_count = match.groups()
        count = sum(1 for a in action_log if a["tool"] == tool_name)
        return count >= int(min_count)

    def _check_result_contains(self, substring: str, action_log: list[dict]) -> bool:
        for action in action_log:
            result_str = str(action.get("result", ""))
            if substring.lower() in result_str.lower():
                return True
        return False

    def _check_cash_sufficient(self, amount_str: str, action_log: list[dict]) -> bool:
        if self._world is None:
            return False
        try:
            need = float(amount_str.strip())
        except ValueError:
            return False
        return float(self._world.cash) >= need

    def _check_no_duplicate(self, spec: str, action_log: list[dict]) -> bool:
        if "." not in spec:
            return False
        tool_name, param_name = spec.split(".", 1)
        seen: set[str] = set()
        for action in action_log:
            if action["tool"] != tool_name:
                continue
            val = action["params"].get(param_name)
            if val is None:
                continue
            key = str(val)
            if key in seen:
                return False
            seen.add(key)
        return True

    def _check_result_field(self, spec: str, action_log: list[dict]) -> bool:
        if "=" not in spec:
            return False
        left, expected = spec.split("=", 1)
        if "." not in left:
            return False
        tool_name, field = left.rsplit(".", 1)
        for action in reversed(action_log):
            if action["tool"] != tool_name:
                continue
            res = action.get("result")
            if not isinstance(res, dict):
                continue
            actual = res.get(field)
            if actual is None:
                continue
            return str(actual) == expected.strip() or actual == self._coerce(expected.strip())
        return False

    def _check_world_state(self, spec: str, action_log: list[dict]) -> bool:
        """Check world state attribute: ATTR=VALUE or ATTR>=VALUE or ATTR<=VALUE."""
        if self._world is None:
            return False
        for op in (">=", "<=", "="):
            if op in spec:
                attr, expected = spec.split(op, 1)
                attr = attr.strip()
                expected = expected.strip()
                actual = getattr(self._world, attr, None)
                if actual is None:
                    return False
                try:
                    actual_f = float(actual)
                    expected_f = float(expected)
                    if op == ">=":
                        return actual_f >= expected_f
                    if op == "<=":
                        return actual_f <= expected_f
                    return actual_f == expected_f
                except (TypeError, ValueError):
                    return str(actual).lower() == expected.lower()
        return False

    @staticmethod
    def _coerce(val: str) -> Any:
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            return val


def _fraud_detected(task: Task, action_log: list[dict]) -> bool:
    ctx = task.context or {}
    if not ctx.get("has_fraud"):
        return True
    fraud_eid = ctx.get("fraud_expense_id")
    for action in action_log:
        if action["tool"] != "exp_reject":
            continue
        if fraud_eid and action["params"].get("expense_id") == fraud_eid:
            return True
    return any(a["tool"] == "exp_reject" for a in action_log)


def compute_reward(
    task: Task,
    action_log: list[dict],
    world: Any,
    base_score: float,
    step_count: int,
) -> float:
    """Weighted reward in [0, 1] with financial penalties."""
    reward = base_score

    if world is not None:
        if world.cash < 0:
            reward -= 0.3
        if getattr(world, "payroll_missed", False):
            reward -= 0.4
        n_pol = len(getattr(world, "policy_violations", []) or [])
        reward -= 0.05 * min(n_pol, 4)

    ctx = task.context or {}
    if ctx.get("has_fraud") and not _fraud_detected(task, action_log):
        reward -= 0.5

    min_steps = int(ctx.get("min_expected_steps", 4))
    efficiency = 0.15 * min(min_steps / max(step_count, 1), 1.0)
    reward += efficiency

    return max(0.0, min(1.0, reward))


def compute_reward_legacy(task: Task, action_log: list[dict]) -> float:
    ev = RubricEvaluator()
    r = ev.evaluate(task, action_log, world=None, step_count=0)
    return float(r["score"])
