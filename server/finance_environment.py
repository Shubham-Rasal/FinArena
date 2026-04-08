"""FinanceOps OpenEnv environment implementation."""

from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from models import FinanceAction, FinanceObservation

try:
    from .world import WorldState
    from .tools import ToolRegistry, TOOL_DEFINITIONS
    from .tasks import TaskGenerator
    from .rubrics import RubricEvaluator, score_to_open_unit_interval
except ImportError:
    from world import WorldState
    from tools import ToolRegistry, TOOL_DEFINITIONS
    from tasks import TaskGenerator
    from rubrics import RubricEvaluator, score_to_open_unit_interval


class FinanceOpsEnvironment(Environment):
    """Enterprise finance workflows with rubric-based terminal reward."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self, seed: int = 42, max_steps: int = 20):
        self._seed = seed
        self._max_steps = max_steps
        self._rng = random.Random(seed)

        self.world = WorldState(seed=seed)
        self.tool_registry = ToolRegistry(self.world)
        self.evaluator = RubricEvaluator()

        self._task_gen = TaskGenerator(self.world, seed=seed)
        self._tasks = self._task_gen.generate_all_tasks()
        self._task_idx = -1  # -1 = use random sampling; ≥0 = explicit index
        self._current_task = None

        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._done = False
        self._tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        self._prev_criteria_score: float = 0.0
        self._episode_max_steps: int = max_steps

    def reset(self, seed: int | None = None, episode_id: str | None = None,
              task_idx: int | None = None, **kwargs: Any) -> FinanceObservation:
        ep_seed = seed if seed is not None else self._rng.randint(0, 2**31)
        self.world.reset(episode_seed=ep_seed)
        self._done = False
        self._prev_criteria_score = 0.0

        # Explicit task_idx (e.g. from playground API) overrides random sampling
        if task_idx is not None:
            self._current_task = self._tasks[task_idx % len(self._tasks)]
        elif self._task_idx >= 0:
            # _task_idx set externally (playground compat): use it once then go random
            self._current_task = self._tasks[self._task_idx % len(self._tasks)]
            self._task_idx = -1  # sentinel: revert to random after explicit pick
        else:
            # Random sampling for RL training — prevents episode-order memorisation
            self._current_task = self._rng.choice(self._tasks)

        if self._current_task.setup_fn:
            self._current_task.setup_fn(self.world)

        ep_id = episode_id or str(uuid4())
        self._state = State(episode_id=ep_id, step_count=0)

        # Per-task horizon: 3× the minimum expected steps, capped at env max_steps
        min_steps = int(self._current_task.context.get("min_expected_steps", 4))
        task_max_steps = min(self._max_steps, max(min_steps * 3, 6))
        self._episode_max_steps = task_max_steps

        return FinanceObservation(
            task_id=self._current_task.task_id,
            instruction=self._current_task.instruction,
            tool_name="",
            tool_result={},
            step=0,
            max_steps=task_max_steps,
            available_tools=self._tool_names,
            done=False,
            reward=score_to_open_unit_interval(0.0),
            metadata={
                "difficulty": self._current_task.difficulty,
                "category": self._current_task.category,
                "context": self._current_task.context,
                "task_max_steps": task_max_steps,
            },
        )

    def step(self, action: FinanceAction, timeout_s: float | None = None, **kwargs: Any) -> FinanceObservation:  # type: ignore[override]
        if self._done:
            return FinanceObservation(
                task_id=self._current_task.task_id if self._current_task else "",
                instruction="",
                tool_name=action.tool_name,
                tool_result={"error": "Episode already finished"},
                step=self._state.step_count,
                max_steps=self._episode_max_steps,
                available_tools=self._tool_names,
                done=True,
                reward=score_to_open_unit_interval(0.0),
                metadata={},
            )

        self._state.step_count += 1
        result = self.tool_registry.execute(action.tool_name, action.arguments)

        done = self._state.step_count >= self._episode_max_steps
        self._done = done

        reward = 0.0
        eval_info: dict[str, Any] = {}
        if self._current_task:
            eval_result = self.evaluator.evaluate(
                self._current_task,
                self.world.action_log,
                world=self.world,
                step_count=self._state.step_count,
            )
            eval_info = eval_result
            total = eval_result["total_criteria"]
            current_criteria_score = eval_result["passed_count"] / total if total > 0 else 0.0

            if done:
                # Full weighted reward at episode end (includes penalties + efficiency)
                raw = float(eval_result["score"])
            else:
                # Incremental reward: fraction of newly satisfied criteria this step
                delta = max(0.0, current_criteria_score - self._prev_criteria_score)
                raw = round(delta * 0.5, 4)
            # Phase 2: every observation.reward must lie strictly in (0, 1), never 0.0 or 1.0
            reward = score_to_open_unit_interval(raw)

            self._prev_criteria_score = current_criteria_score

        return FinanceObservation(
            task_id=self._current_task.task_id if self._current_task else "",
            instruction=self._current_task.instruction if self._current_task else "",
            tool_name=action.tool_name,
            tool_result=result,
            step=self._state.step_count,
            max_steps=self._episode_max_steps,
            available_tools=self._tool_names,
            done=done,
            reward=reward,
            metadata={
                "step": self._state.step_count,
                **({"evaluation": eval_info} if eval_info else {}),
            },
        )

    @property
    def state(self) -> State:
        return self._state
