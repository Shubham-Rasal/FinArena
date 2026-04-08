"""FastAPI application for FinanceOps Environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError("openenv is required. Install with: uv sync") from e

from models import FinanceAction, FinanceObservation
from .finance_environment import FinanceOpsEnvironment
from .tools import TOOL_DEFINITIONS
from .rubrics import RubricEvaluator, score_to_open_unit_interval

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")

app = create_app(
    FinanceOpsEnvironment,
    FinanceAction,
    FinanceObservation,
    env_name="finance_ops_env",
    max_concurrent_envs=4,
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_playground_env = FinanceOpsEnvironment(seed=42, max_steps=20)


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/playground")


@app.get("/playground", include_in_schema=False)
def playground():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/tasks")
def get_tasks():
    env = _playground_env
    orig_idx = env._task_idx
    out = []
    for i in range(len(env._tasks)):
        task = env._tasks[i]
        out.append(
            {
                "index": i,
                "task_id": task.task_id,
                "instruction": task.instruction,
                "difficulty": task.difficulty,
                "category": task.category,
                "expected_tools": task.expected_tools,
                "rubric_criteria": task.rubric_criteria,
                "num_criteria": len(task.rubric_criteria),
            }
        )
    env._task_idx = orig_idx
    return out


@app.get("/api/tool_definitions")
def get_tool_definitions():
    return TOOL_DEFINITIONS


@app.post("/api/reset")
async def playground_reset(request: Request):
    body = await request.json()
    task_idx = body.get("task_idx", 0)
    env = _playground_env
    env._task_idx = task_idx
    obs = env.reset()
    return {
        "task_id": obs.task_id,
        "instruction": obs.instruction,
        "step": obs.step,
        "max_steps": obs.max_steps,
        "available_tools": obs.available_tools,
        "done": obs.done,
        "reward": obs.reward,
        "metadata": obs.metadata,
    }


@app.post("/api/step")
async def playground_step(request: Request):
    body = await request.json()
    tool_name = body.get("tool_name", "")
    arguments = body.get("arguments", {})
    env = _playground_env
    action = FinanceAction(tool_name=tool_name, arguments=arguments)
    obs = env.step(action)
    return {
        "task_id": obs.task_id,
        "instruction": obs.instruction,
        "tool_name": obs.tool_name,
        "tool_result": obs.tool_result,
        "step": obs.step,
        "max_steps": obs.max_steps,
        "done": obs.done,
        "reward": obs.reward,
        "metadata": obs.metadata,
    }


@app.post("/api/evaluate")
async def playground_evaluate():
    env = _playground_env
    evaluator = RubricEvaluator()
    if env._current_task:
        return evaluator.evaluate(
            env._current_task,
            env.world.action_log,
            world=env.world,
            step_count=env._state.step_count,
        )
    return {
        "score": score_to_open_unit_interval(0.0),
        "passed": False,
        "criteria_results": [],
        "passed_count": 0,
        "total_criteria": 0,
    }


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
