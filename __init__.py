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


def _print_status_bar(**hook_kwargs: Any) -> None:
    """Fetch usage data and print ANSI status bar to terminal (stdout).

    Called via post_llm_call hook — prints the status bar directly to
    the terminal after the assistant response, so it appears below the
    chat output without polluting the LLM context.
    """
    from .api_client import fetch_usage_data
    from .formatting import render_status_line

    try:
        data = fetch_usage_data()
        raw_model = hook_kwargs.get("model", "")
        from .model_mapper import map_model_name
        model_name = map_model_name(raw_model) if raw_model else data.get("model_name", "Unknown")

        status = render_status_line(
            data=data,
            model_name=model_name,
            cwd=_get_cwd_basename(),
            git_branch=_get_git_branch(),
        )
        # Print directly to terminal (stderr won't be captured, but
        # stdout works fine since post_llm_call runs after streaming)
        print(status, flush=True)
    except Exception as exc:
        logger.debug("status bar print failed: %s", exc)


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _zai_usage_handler(**kwargs: Any) -> str:
    """Tool handler: return Z.AI usage status as formatted text."""
    from .api_client import fetch_usage_data
    from .formatting import render_status_line

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

def _on_post_llm_call(**kwargs: Any) -> None:
    """Print status bar to terminal after each LLM turn completes.

    Uses post_llm_call hook so the status bar appears below the assistant
    response in the terminal, without injecting anything into the LLM context.
    """
    _print_status_bar(**kwargs)


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

    # Register post_llm_call hook to print status bar after each turn
    ctx.register_hook("post_llm_call", _on_post_llm_call)

    logger.info("zai-statusline plugin registered: tool=zai_usage, hook=post_llm_call")
