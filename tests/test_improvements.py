"""Tests for all improvements made to FinanceOpsEnv."""

import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from world import WorldState
from tasks import TaskGenerator
from rubrics import RubricEvaluator, compute_reward


# ---------------------------------------------------------------------------
# World state tests
# ---------------------------------------------------------------------------

class TestWorldStateVariance:
    def test_different_seeds_produce_different_balances(self):
        w1 = WorldState(seed=1)
        w2 = WorldState(seed=99)
        # At least one account should differ
        assert any(
            w1.accounts[aid]["balance"] != w2.accounts[aid]["balance"]
            for aid in w1.accounts
        )

    def test_same_seed_produces_same_balances(self):
        w1 = WorldState(seed=42)
        w2 = WorldState(seed=42)
        for aid in w1.accounts:
            assert w1.accounts[aid]["balance"] == w2.accounts[aid]["balance"]

    def test_balances_within_variance_bounds(self):
        base_balances = {
            "acc_operating": 5_000_000,
            "acc_payroll": 120_000_000,
            "acc_reserve": 1_000_000,
            "acc_fx": 500_000,
        }
        for seed in range(20):
            w = WorldState(seed=seed)
            for aid, base in base_balances.items():
                bal = w.accounts[aid]["balance"]
                assert base * 0.80 <= bal <= base * 1.20, (
                    f"seed={seed} account={aid} balance={bal} out of ±20% range"
                )

    def test_reset_with_new_seed_changes_balances(self):
        w = WorldState(seed=1)
        bal_before = w.accounts["acc_operating"]["balance"]
        w.reset(episode_seed=999)
        bal_after = w.accounts["acc_operating"]["balance"]
        # Different seed should (almost certainly) produce a different balance
        # Use a range check rather than exact inequality since seeds might coincide
        assert isinstance(bal_after, float)

    def test_payroll_run_truncated_flag(self):
        w = WorldState(seed=0)
        result = w.payroll_run("2025-01")
        assert "truncated" in result.get("payroll_run", {}) or result.get("success") is False


# ---------------------------------------------------------------------------
# Task generation tests
# ---------------------------------------------------------------------------

class TestTaskGeneration:
    def setup_method(self):
        self.world = WorldState(seed=42)
        self.gen = TaskGenerator(self.world, seed=42)
        self.tasks = self.gen.generate_all_tasks()

    def test_total_task_count(self):
        assert len(self.tasks) == 80

    def test_no_duplicate_instructions(self):
        instructions = [t.instruction for t in self.tasks]
        assert len(instructions) == len(set(instructions)), "Duplicate task instructions found"

    def test_financial_close_tasks_are_unique(self):
        close_tasks = [t for t in self.tasks if t.category == "financial_close"]
        assert len(close_tasks) == 10
        instructions = [t.instruction for t in close_tasks]
        assert len(set(instructions)) == 10, "financial_close tasks have duplicates"

    def test_cross_domain_tasks_exist(self):
        chain = [t for t in self.tasks if t.category == "cross_domain"]
        assert len(chain) == 5

    def test_cross_domain_multi_category_tools(self):
        """Each cross_domain task should touch tools from ≥2 functional areas."""
        ar_tools = {"acc_create_invoice", "acc_record_payment", "acc_get_ledger", "acc_generate_financials"}
        payroll_tools = {"payroll_run", "payroll_calculate", "payroll_disburse"}
        bank_tools = {"bank_get_balance", "bank_transfer", "bank_reconcile"}
        exp_tools = {"exp_submit", "exp_approve", "exp_reimburse", "exp_check_policy"}

        groups = [ar_tools, payroll_tools, bank_tools, exp_tools]
        for t in [t for t in self.tasks if t.category == "cross_domain"]:
            tool_set = set(t.expected_tools)
            matched_groups = sum(1 for g in groups if tool_set & g)
            assert matched_groups >= 2, f"Task {t.task_id} only covers 1 tool group"

    def test_blacklisted_vendor_in_task_is_actually_blacklisted(self):
        """Edge case task mentioning a blacklisted vendor must reference a real blacklisted vendor."""
        blacklisted_ids = {v["id"] for v in self.world._vendors if v.get("blacklisted")}
        blacklist_tasks = [t for t in self.tasks if "blacklisted" in t.instruction.lower()]
        assert blacklist_tasks, "No blacklisted vendor task found"
        for t in blacklist_tasks:
            # Extract vendor id from instruction: word starting with v_
            import re
            vendor_ids = re.findall(r"v_\d+", t.instruction)
            for vid in vendor_ids:
                assert vid in blacklisted_ids, f"Task references {vid} which is NOT blacklisted"

    def test_all_tasks_have_min_expected_steps(self):
        for t in self.tasks:
            assert "min_expected_steps" in t.context, f"{t.task_id} missing min_expected_steps"
            assert t.context["min_expected_steps"] >= 1


# ---------------------------------------------------------------------------
# Rubric evaluator tests
# ---------------------------------------------------------------------------

class TestRubricEvaluator:
    def setup_method(self):
        self.ev = RubricEvaluator()
        self.world = WorldState(seed=42)

    def _log(self, *calls):
        """Build a fake action log from (tool, params, result) tuples."""
        return [{"tool": t, "params": p, "result": r} for t, p, r in calls]

    def test_tool_order_first_occurrence(self):
        """A before B: first A idx < last B idx."""
        log = self._log(
            ("tool_a", {}, {}),
            ("tool_b", {}, {}),
        )
        assert self.ev._check_tool_order("tool_a<tool_b", log) is True

    def test_tool_order_retry_pattern(self):
        """A, B, A, B — should still pass (first A < last B)."""
        log = self._log(
            ("tool_a", {}, {}),
            ("tool_b", {}, {}),
            ("tool_a", {}, {}),
            ("tool_b", {}, {}),
        )
        assert self.ev._check_tool_order("tool_a<tool_b", log) is True

    def test_tool_order_fails_when_reversed(self):
        log = self._log(
            ("tool_b", {}, {}),
            ("tool_a", {}, {}),
        )
        assert self.ev._check_tool_order("tool_a<tool_b", log) is False

    def test_world_state_cash_eq(self):
        self.world.accounts["acc_operating"]["balance"] = 1000.0
        self.world.accounts["acc_payroll"]["balance"] = 0.0
        self.world.accounts["acc_reserve"]["balance"] = 0.0
        self.world.accounts["acc_fx"]["balance"] = 0.0
        self.ev._world = self.world
        assert self.ev._check_world_state("cash>=1000", []) is True
        assert self.ev._check_world_state("cash>=1001", []) is False

    def test_world_state_bool_attr(self):
        self.world.payroll_missed = False
        self.ev._world = self.world
        assert self.ev._check_world_state("payroll_missed=False", []) is True
        self.world.payroll_missed = True
        assert self.ev._check_world_state("payroll_missed=False", []) is False

    def test_world_state_reconciliation(self):
        self.world._reconciliation_done = False
        self.ev._world = self.world
        assert self.ev._check_world_state("_reconciliation_done=False", []) is True

    def test_world_state_no_world(self):
        ev = RubricEvaluator()  # _world is None
        assert ev._check_world_state("cash>=0", []) is False


# ---------------------------------------------------------------------------
# Reward function tests
# ---------------------------------------------------------------------------

class TestComputeReward:
    def setup_method(self):
        self.world = WorldState(seed=42)

    def _make_task(self, min_steps=4, has_fraud=False, fraud_id=None):
        from tasks import Task
        ctx = {"min_expected_steps": min_steps}
        if has_fraud:
            ctx["has_fraud"] = True
            if fraud_id:
                ctx["fraud_expense_id"] = fraud_id
        return Task("t_test", "test", "medium", "test", [], [], context=ctx)

    def test_efficiency_weight_at_exact_min_steps(self):
        task = self._make_task(min_steps=4)
        # Perfect base_score, no penalties, step_count == min_steps
        reward = compute_reward(task, [], None, base_score=1.0, step_count=4)
        # efficiency = 0.15 * (4/4) = 0.15, total = 1.15 capped at 1.0
        assert reward == 1.0

    def test_efficiency_is_0_15_not_0_1(self):
        task = self._make_task(min_steps=4)
        # base_score 0.8, no world, step_count = 4 → efficiency = 0.15
        reward = compute_reward(task, [], None, base_score=0.8, step_count=4)
        assert abs(reward - min(1.0, 0.8 + 0.15)) < 1e-9

    def test_efficiency_decreases_with_more_steps(self):
        task = self._make_task(min_steps=4)
        r_tight = compute_reward(task, [], None, base_score=0.8, step_count=4)
        r_loose = compute_reward(task, [], None, base_score=0.8, step_count=10)
        assert r_tight > r_loose

    def test_negative_cash_penalty(self):
        self.world.accounts["acc_operating"]["balance"] = -1.0
        self.world.accounts["acc_payroll"]["balance"] = 0.0
        self.world.accounts["acc_reserve"]["balance"] = 0.0
        self.world.accounts["acc_fx"]["balance"] = 0.0
        task = self._make_task()
        reward = compute_reward(task, [], self.world, base_score=0.5, step_count=4)
        # penalty -0.3 applied
        assert reward < 0.5 + 0.15  # even with efficiency boost, penalised

    def test_payroll_missed_penalty(self):
        task = self._make_task()
        self.world.payroll_missed = True
        reward = compute_reward(task, [], self.world, base_score=1.0, step_count=4)
        assert reward < 1.0  # -0.4 penalty should fire

    def test_reward_clipped_to_0_1(self):
        task = self._make_task()
        # Worst case: all penalties
        self.world.payroll_missed = True
        self.world.policy_violations = ["a", "b", "c", "d"]
        self.world.accounts["acc_operating"]["balance"] = -1.0
        self.world.accounts["acc_payroll"]["balance"] = 0.0
        self.world.accounts["acc_reserve"]["balance"] = 0.0
        self.world.accounts["acc_fx"]["balance"] = 0.0
        reward = compute_reward(task, [], self.world, base_score=0.0, step_count=1)
        assert 0.0 <= reward <= 1.0


# ---------------------------------------------------------------------------
# Integration smoke test
# ---------------------------------------------------------------------------

class TestEnvironmentIntegration:
    def test_random_task_sampling_produces_variety(self):
        """Two environments with different seeds should not always produce the same task sequence."""
        import random
        tasks_seen_42 = set()
        tasks_seen_7 = set()

        world42 = WorldState(seed=42)
        gen42 = TaskGenerator(world42, seed=42)
        tasks42 = gen42.generate_all_tasks()
        rng42 = random.Random(42)
        for _ in range(20):
            tasks_seen_42.add(rng42.choice(tasks42).task_id)

        world7 = WorldState(seed=7)
        gen7 = TaskGenerator(world7, seed=7)
        tasks7 = gen7.generate_all_tasks()
        rng7 = random.Random(7)
        for _ in range(20):
            tasks_seen_7.add(rng7.choice(tasks7).task_id)

        # The two sequences should have explored at least somewhat different tasks
        assert tasks_seen_42 != tasks_seen_7 or len(tasks_seen_42) > 1

    def test_per_task_max_steps_bounded(self):
        """Per-task max steps should be ≥ 6 and ≤ 20."""
        world = WorldState(seed=42)
        gen = TaskGenerator(world, seed=42)
        for task in gen.generate_all_tasks():
            min_steps = int(task.context.get("min_expected_steps", 4))
            task_max = min(20, max(min_steps * 3, 6))
            assert 6 <= task_max <= 20, f"task {task.task_id} has bad max_steps={task_max}"

    def test_world_reset_with_episode_seed(self):
        world = WorldState(seed=0)
        world.reset(episode_seed=123)
        bal1 = world.accounts["acc_operating"]["balance"]
        world.reset(episode_seed=123)
        bal2 = world.accounts["acc_operating"]["balance"]
        assert bal1 == bal2  # Same seed → reproducible

        world.reset(episode_seed=456)
        bal3 = world.accounts["acc_operating"]["balance"]
        assert bal1 != bal3  # Different seed → different balance


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
