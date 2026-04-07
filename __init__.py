"""
Z.AI / Zhipu AI Statusline Plugin for Hermes Agent
===================================================

Displays real-time Z.AI Coding Plan usage information in a Claude Code-style
status bar after each LLM turn. Also registers a ``zai_usage`` tool for
on-demand queries.

Usage:
    Automatically displays status after each assistant response.
    Use the tool "zai_usage" to query on demand.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_git_branch() -> str:
    """Return current git branch name, or empty string."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _get_cwd_basename() -> str:
    """Return the basename of the current working directory."""
    try:
        return Path.cwd().name
    except Exception:
        return ""


def _format_usage_line(model_name: str, data: dict) -> str:
    """Build the compact status line string."""
    token_pct = data.get("token_percent", 0)
    wq_pct = data.get("token_percent_wq", 0)
    mcp_pct = data.get("mcp_percent", 0)
    reset_str = data.get("next_reset_time_str", "")
    wq_reset_str = data.get("next_reset_time_wq_str", "")

    # Usage: 5 Hours: 17% - 4h 32m  Weekly: 64% - 3d 4h  MCP: 75%
    parts = [f"[Status: {model_name} Usage:"]
    parts.append(f"5 Hours: {token_pct}%")
    if reset_str:
        parts.append(f"- {reset_str}")
    if wq_pct:
        wq_part = f"Weekly: {wq_pct}%"
        if wq_reset_str:
            wq_part += f" - {wq_reset_str}"
        parts.append(wq_part)
    parts.append(f"MCP: {mcp_pct}%]")
    return "  ".join(parts)


def _get_usage_context(**hook_kwargs: Any) -> str:
    """Fetch usage data and format as context string for injection.

    Returns a plain-text status line (no ANSI codes) that gets injected
    into the user message via the pre_llm_call hook, so the agent
    naturally surfaces usage info in its responses.
    """
    from .api_client import fetch_usage_data
    from .model_mapper import map_model_name

    try:
        data = fetch_usage_data()
        raw_model = hook_kwargs.get("model", "")
        model_name = map_model_name(raw_model) if raw_model else data.get("model_name", "Unknown")

        if data.get("error") == "setup_required":
            return ""

        # If API is unavailable, still show status bar with whatever we have
        if data.get("apiUnavailable"):
            status_line = f"[Status: {model_name} Usage: --  MCP: --]"
            return (
                f"[INSTRUCTION: You MUST display the following status bar at the "
                f"very beginning of your response, exactly as shown, before any "
                f"other content. Do NOT omit it, summarize it, or rephrase it. "
                f"This is a persistent UI element that must appear in every reply.]\n"
                f"{status_line}"
            )

        status_line = _format_usage_line(model_name, data)
        return (
            f"[INSTRUCTION: You MUST display the following status bar at the "
            f"very beginning of your response, exactly as shown, before any "
            f"other content. Do NOT omit it, summarize it, or rephrase it. "
            f"This is a persistent UI element that must appear in every reply.]\n"
            f"{status_line}"
        )
    except Exception as exc:
        logger.debug("usage context fetch failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _zai_usage_handler(**kwargs: Any) -> str:
    """Tool handler: return Z.AI usage status as formatted text."""
    from .api_client import fetch_usage_data
    from .formatting import render_status_line, Colors

    data = fetch_usage_data()
    status = render_status_line(
        data=data,
        cwd=_get_cwd_basename(),
        git_branch=_get_git_branch(),
    )
    return status


# ---------------------------------------------------------------------------
# Hook callbacks
# ---------------------------------------------------------------------------

def _on_pre_llm_call(**kwargs: Any) -> Dict[str, str]:
    """Inject usage context into the current turn via pre_llm_call hook.

    The context string is appended to the user message, so the agent
    naturally surfaces the usage info in its response — mimicking
    Claude Code's status bar behavior.
    """
    ctx = _get_usage_context(**kwargs)
    if ctx:
        return {"context": ctx}
    return {}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Plugin entry point called by Hermes PluginManager."""
    # Register the zai_usage tool
    ctx.register_tool(
        name="zai_usage",
        toolset="hermes-cli",
        schema={
            "type": "function",
            "function": {
                "name": "zai_usage",
                "description": (
                    "Show Z.AI / Zhipu AI Coding Plan usage status: "
                    "token quota, MCP usage, estimated cost, and current model. "
                    "Displays a Claude Code-style status bar."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        handler=_zai_usage_handler,
        is_async=False,
        description="Show Z.AI Coding Plan usage status bar",
        emoji="\u25b6",
    )

    # Register pre_llm_call hook to inject usage context each turn
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)

    logger.info("zai-statusline plugin registered: tool=zai_usage, hook=pre_llm_call")
