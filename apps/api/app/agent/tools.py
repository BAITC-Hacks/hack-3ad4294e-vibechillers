"""Tool registry for the agent loop.

Other slices register `Tool`s into a shared `ToolRegistry`; the loop exposes
them to the LLM via `to_function_schema` and executes them via `call_tool`,
which never raises — every failure mode comes back as ``{"ok": False, ...}``.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

import anyio.to_thread
from pydantic import BaseModel, ValidationError


@dataclass
class Tool:
    name: str
    description: str
    params: type[BaseModel]
    fn: Callable[..., Any]  # sync or async, returns JSON-serialisable


class ToolRegistry:
    """Name -> Tool lookup with duplicate detection."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(
                f"tool {tool.name!r} is already registered; "
                "unregister it first or choose a different name"
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            known = ", ".join(sorted(self._tools)) or "<none>"
            raise KeyError(
                f"unknown tool {name!r}; registered tools: [{known}]"
            ) from None

    def list(self) -> list[Tool]:
        return list(self._tools.values())


def to_function_schema(tool: Tool) -> dict[str, Any]:
    """Render a Tool as an OpenAI function-calling schema."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.params.model_json_schema(),
        },
    }


async def call_tool(
    registry: ToolRegistry, name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Validate `args` against the tool's model and run it.

    Never raises: unknown tools, validation errors, and exceptions inside the
    tool function all return ``{"ok": False, "error": <readable>}``.
    Coroutine functions are awaited; sync functions run in a worker thread.
    """
    try:
        tool = registry.get(name)
    except KeyError as exc:
        message = exc.args[0] if exc.args else f"unknown tool {name!r}"
        return {"ok": False, "error": str(message)}

    try:
        validated = tool.params(**(args or {}))
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        return {"ok": False, "error": f"invalid arguments for tool {name!r}: {problems}"}
    except TypeError as exc:
        return {
            "ok": False,
            "error": f"invalid arguments for tool {name!r}: {exc}",
        }

    kwargs: dict[str, Any] = validated.model_dump()

    try:
        if inspect.iscoroutinefunction(tool.fn):
            result = await tool.fn(**kwargs)
        else:
            # anyio.to_thread.run_sync takes a callable (+ partial for kwargs);
            # awaiting an awaitable returned from a worker thread would be
            # wrong, so hand coroutines back to the event loop here.
            result = await anyio.to_thread.run_sync(partial(tool.fn, **kwargs))
            if inspect.isawaitable(result):
                result = await result
    except Exception as exc:  # noqa: BLE001 - tool failures are data, not crashes
        return {
            "ok": False,
            "error": f"tool {name!r} raised {type(exc).__name__}: {exc}",
        }

    return {"ok": True, "result": result}
