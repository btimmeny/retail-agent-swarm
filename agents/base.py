"""
Base agent class for the retail agent swarm.
Each domain agent wraps an OpenAI model with domain-specific tools and a system prompt.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from openai import OpenAI

# --- Structured Logging (structlog) ---
try:
    import structlog
    log = structlog.get_logger()
except ImportError:
    import logging
    log = logging.getLogger("agent")
# --- End Structured Logging ---

# --- OpenTelemetry Tracing ---
try:
    from opentelemetry import trace
    from opentelemetry.trace import Span
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    import threading as _otel_threading
    _otel_tracing_initialized = False
    _otel_tracing_lock = _otel_threading.Lock()
    def _init_tracing():
        global _otel_tracing_initialized
        with _otel_tracing_lock:
            if not _otel_tracing_initialized:
                if not trace.get_tracer_provider() or isinstance(trace.get_tracer_provider(), type(None)):
                    provider = TracerProvider()
                    processor = BatchSpanProcessor(ConsoleSpanExporter())
                    provider.add_span_processor(processor)
                    trace.set_tracer_provider(provider)
                _otel_tracing_initialized = True
    _init_tracing()
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None
# --- End OpenTelemetry Tracing ---

# --- Secrets Management ---
import threading
import logging

# Placeholder for a secure secrets loader. Replace with integration to AWS Secrets Manager,
# Azure Key Vault, or a local encrypted file as appropriate for your environment.
def load_secret(secret_name: str) -> str:
    """
    Securely load a secret by name. Replace this function's implementation with your
    organization's secrets management solution (e.g., AWS Secrets Manager, Azure Key Vault,
    HashiCorp Vault, or a local encrypted file).
    """
    # Example: Load from a local encrypted file (for demo only; replace in production)
    # with open('/path/to/encrypted_secrets.json', 'r') as f:
    #     secrets = decrypt_and_load(f.read())
    #     return secrets[secret_name]
    # For demonstration, raise if not set
    secret = os.environ.get(secret_name)
    if not secret:
        raise RuntimeError(f"Secret '{secret_name}' not found. Configure your secrets manager.")
    return secret

# Thread-safe singleton client and lock
default_secret_name = 'OPENAI_API_KEY'
_client: OpenAI | None = None
_client_lock = threading.Lock()
_current_api_key: str | None = None


def get_client() -> OpenAI:
    """
    Get the singleton OpenAI client, securely loading the API key if needed.
    """
    global _client, _current_api_key
    with _client_lock:
        api_key = load_secret(default_secret_name)
        if _client is None or _current_api_key != api_key:
            _client = OpenAI(api_key=api_key)
            _current_api_key = api_key
        return _client


def reload_openai_api_key():
    """
    Reload the OpenAI API key from the secrets manager and re-instantiate the client.
    Call this function after rotating the API key in your secrets manager.
    """
    global _client, _current_api_key
    with _client_lock:
        api_key = load_secret(default_secret_name)
        _client = OpenAI(api_key=api_key)
        _current_api_key = api_key
        log.info("api_key_reloaded", message="OpenAI API key reloaded and client re-instantiated.")

# --- End Secrets Management ---

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
        log.info(
            "agent_run_start",
            agent=self.name,
            user_message=user_message,
            context=context,
        )
        if tracer:
            span_ctx = tracer.start_as_current_span(f"Agent.run: {self.name}")
        else:
            span_ctx = None
        if span_ctx:
            with span_ctx as agent_span:
                try:
                    result = self._run_with_tracing(user_message, context, agent_span)
                    log.info(
                        "agent_run_success",
                        agent=self.name,
                        user_message=user_message,
                        result_summary=str(result.get("response", ""))[:200],
                    )
                    return result
                except Exception as e:
                    log.error(
                        "agent_run_error",
                        agent=self.name,
                        user_message=user_message,
                        error=str(e),
                    )
                    raise
        else:
            try:
                result = self._run_with_tracing(user_message, context, None)
                log.info(
                    "agent_run_success",
                    agent=self.name,
                    user_message=user_message,
                    result_summary=str(result.get("response", ""))[:200],
                )
                return result
            except Exception as e:
                log.error(
                    "agent_run_error",
                    agent=self.name,
                    user_message=user_message,
                    error=str(e),
                )
                raise

    def _run_with_tracing(self, user_message: str, context: dict | None, agent_span: 'Span | None') -> dict:
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
        for round_num in range(5):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            client = get_client()
            log.info(
                "agent_openai_chat_call",
                agent=self.name,
                round=round_num,
                model=self.model,
                messages=[m["role"] for m in messages],
                tools=[t.get("function", {}).get("name") for t in self.tools] if self.tools else [],
            )
            if tracer:
                with tracer.start_as_current_span("openai.chat.completions.create", parent=agent_span) as openai_span:
                    openai_span.set_attribute("agent.name", self.name)
                    openai_span.set_attribute("round", round_num)
                    try:
                        response = client.chat.completions.create(**kwargs)
                    except Exception as e:
                        log.error(
                            "openai_chat_error",
                            agent=self.name,
                            round=round_num,
                            error=str(e),
                        )
                        raise
            else:
                try:
                    response = client.chat.completions.create(**kwargs)
                except Exception as e:
                    log.error(
                        "openai_chat_error",
                        agent=self.name,
                        round=round_num,
                        error=str(e),
                    )
                    raise
            msg = response.choices[0].message

            if not msg.tool_calls:
                log.info(
                    "agent_no_tool_calls",
                    agent=self.name,
                    round=round_num,
                    response=msg.content or "",
                )
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
                try:
                    fn_args = json.loads(tc.function.arguments)
                except Exception as e:
                    log.error(
                        "tool_call_argument_parse_error",
                        agent=self.name,
                        tool=fn_name,
                        arguments=tc.function.arguments,
                        error=str(e),
                    )
                    fn_args = {}
                handler = self.tool_handlers.get(fn_name)
                log.info(
                    "tool_call_invoked",
                    agent=self.name,
                    tool=fn_name,
                    args=fn_args,
                )
                if tracer:
                    with tracer.start_as_current_span(f"tool_handler: {fn_name}", parent=agent_span) as tool_span:
                        tool_span.set_attribute("tool.name", fn_name)
                        tool_span.set_attribute("tool.args", str(fn_args))
                        if handler:
                            try:
                                result = handler(**fn_args)
                                tool_span.set_attribute("tool.success", True)
                                log.info(
                                    "tool_call_success",
                                    agent=self.name,
                                    tool=fn_name,
                                    args=fn_args,
                                    result=result,
                                )
                            except Exception as e:
                                result = {"error": str(e)}
                                tool_span.set_attribute("tool.success", False)
                                tool_span.set_attribute("tool.error", str(e))
                                log.error(
                                    "tool_call_error",
                                    agent=self.name,
                                    tool=fn_name,
                                    args=fn_args,
                                    error=str(e),
                                )
                        else:
                            result = {"error": f"Unknown tool: {fn_name}"}
                            tool_span.set_attribute("tool.success", False)
                            tool_span.set_attribute("tool.error", f"Unknown tool: {fn_name}")
                            log.error(
                                "tool_call_unknown_tool",
                                agent=self.name,
                                tool=fn_name,
                                args=fn_args,
                                error=f"Unknown tool: {fn_name}",
                            )
                else:
                    if handler:
                        try:
                            result = handler(**fn_args)
                            log.info(
                                "tool_call_success",
                                agent=self.name,
                                tool=fn_name,
                                args=fn_args,
                                result=result,
                            )
                        except Exception as e:
                            result = {"error": str(e)}
                            log.error(
                                "tool_call_error",
                                agent=self.name,
                                tool=fn_name,
                                args=fn_args,
                                error=str(e),
                            )
                    else:
                        result = {"error": f"Unknown tool: {fn_name}"}
                        log.error(
                            "tool_call_unknown_tool",
                            agent=self.name,
                            tool=fn_name,
                            args=fn_args,
                            error=f"Unknown tool: {fn_name}",
                        )

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
        log.warning(
            "agent_max_tool_call_rounds_exceeded",
            agent=self.name,
            response="Agent reached maximum tool-call rounds.",
            tool_calls_made=tool_calls_made,
        )
        return {
            "agent": self.name,
            "response": "Agent reached maximum tool-call rounds.",
            "tool_calls_made": tool_calls_made,
            "raw_data": raw_data,
        }

"""
API Key Rotation Process:
------------------------
1. Update your OpenAI API key in your secrets manager (e.g., AWS Secrets Manager, Azure Key Vault, or encrypted file).
2. Call the `reload_openai_api_key()` function at runtime to reload the key and re-instantiate the OpenAI client.
   This can be triggered via an admin endpoint, CLI, or management script.
3. All subsequent agent calls will use the new API key without requiring a service restart.

Note: Replace the `load_secret` implementation with your organization's secure secrets management solution.
"""
