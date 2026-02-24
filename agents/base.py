"""
Base agent class for the retail agent swarm.
Each domain agent wraps an OpenAI model with domain-specific tools and a system prompt.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class Agent:
    """A single domain agent backed by an OpenAI chat model with function calling."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[dict],
        tool_handlers: dict[str, Callable[..., Any]],
        model: str = "gpt-4.1",
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.model = model

    def run(self, user_message: str, context: dict | None = None) -> dict:
        """
        Execute the agent with a user message and optional context.
        Returns {"response": str, "tool_calls_made": list[dict], "raw_data": dict}.
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Context from other agents:\n{json.dumps(context, indent=2, default=str)}",
            })

        messages.append({"role": "user", "content": user_message})

        tool_calls_made = []
        raw_data = {}

        # Allow up to 5 rounds of tool calling
        for _ in range(5):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            client = get_client()
            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            if not msg.tool_calls:
                return {
                    "agent": self.name,
                    "response": msg.content or "",
                    "tool_calls_made": tool_calls_made,
                    "raw_data": raw_data,
                }

            # Process tool calls
            messages.append(msg)
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                handler = self.tool_handlers.get(fn_name)
                if handler:
                    result = handler(**fn_args)
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                tool_calls_made.append({
                    "tool": fn_name,
                    "args": fn_args,
                    "result": result,
                })
                raw_data[fn_name] = result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

        # If we exhausted rounds, return last state
        return {
            "agent": self.name,
            "response": "Agent reached maximum tool-call rounds.",
            "tool_calls_made": tool_calls_made,
            "raw_data": raw_data,
        }
