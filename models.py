"""
Data models for FinanceOps Environment.

Action: tool call. Observation: tool result + task context.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, model_validator

from openenv.core.env_server.types import Action, Observation


def _parse_arguments_value(v: Any) -> dict[str, Any]:
    """Turn arguments into a dict (OpenEnv/Gradio often sends JSON as a string)."""
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            if not s.startswith("{"):
                s = "{" + s + "}"
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError as e:
                raise ValueError(
                    'arguments must be JSON object, e.g. {"account_id": "acc_operating"}'
                ) from e
        if not isinstance(parsed, dict):
            raise ValueError("arguments JSON must be an object {...}, not a list or string")
        return parsed
    raise TypeError("arguments must be a dict or JSON string")


class FinanceAction(Action):
    """A single tool invocation."""

    tool_name: str = Field(..., description="Name of the finance tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

    @model_validator(mode="before")
    @classmethod
    def _coerce_arguments_before_model(cls, data: Any) -> Any:
        """Run before field validators so string `arguments` is never rejected as dict_type."""
        if isinstance(data, dict) and "arguments" in data:
            data = {**data, "arguments": _parse_arguments_value(data["arguments"])}
        return data

    @field_validator("arguments", mode="before")
    @classmethod
    def coerce_arguments_field(cls, v: Any) -> dict[str, Any]:
        """Backup: coerce if only field-level validation runs."""
        return _parse_arguments_value(v)


class FinanceObservation(Observation):
    """Observation after each environment step."""

    task_id: str = Field(default="", description="Current task identifier")
    instruction: str = Field(default="", description="Task instruction")
    tool_name: str = Field(default="", description="Tool that was executed")
    tool_result: Dict[str, Any] = Field(default_factory=dict, description="Tool return value")
    step: int = Field(default=0, description="Current step")
    max_steps: int = Field(default=20, description="Episode horizon")
    available_tools: List[str] = Field(default_factory=list, description="Tool names")
    done: bool = Field(default=False, description="Episode finished")
    reward: float = Field(default=0.0, description="Reward (typically on last step)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra metadata")
