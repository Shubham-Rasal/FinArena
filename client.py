"""FinanceOps Environment HTTP client."""

from typing import Dict

from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from openenv.core import EnvClient

from .models import FinanceAction, FinanceObservation


class FinanceOpsEnv(EnvClient[FinanceAction, FinanceObservation]):
    """Client for FinanceOpsEnvironment (remote HTTP/WebSocket server)."""

    def _step_payload(self, action: FinanceAction) -> Dict:
        return {"tool_name": action.tool_name, "arguments": action.arguments}

    def _parse_result(self, payload: Dict) -> StepResult[FinanceObservation]:
        obs_data = payload.get("observation", {})
        observation = FinanceObservation(
            task_id=obs_data.get("task_id", ""),
            instruction=obs_data.get("instruction", ""),
            tool_name=obs_data.get("tool_name", ""),
            tool_result=obs_data.get("tool_result", {}),
            step=obs_data.get("step", 0),
            max_steps=obs_data.get("max_steps", 20),
            available_tools=obs_data.get("available_tools", []),
            done=payload.get("done", False),
            reward=obs_data.get("reward", payload.get("reward")),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
