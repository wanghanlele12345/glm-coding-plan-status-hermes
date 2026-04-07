"""
ANSI color codes and status bar formatting.
Mimics Claude Code status line visual style.
"""

import time


class Colors:
    """256-color ANSI escape codes for status bar."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 256-color palette
    ORANGE = "\033[38;5;208m"
    BLUE = "\033[38;5;39m"
    GREEN = "\033[38;5;76m"
    YELLOW = "\033[38;5;226m"
    GRAY = "\033[38;5;245m"
    RED = "\033[38;5;196m"
    CYAN = "\033[38;5;51m"
    MAGENTA = "\033[38;5;177m"
    WHITE = "\033[38;5;255m"


def progress_bar(percent: int = 0, width: int = 10) -> str:
    """Render a colored progress bar with percentage.

    Style matches Claude Code status bar: filled blocks + empty blocks.
    """
    filled = round((min(percent, 100) / 100) * width)
    empty = width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    if percent >= 90:
        color = Colors.RED
    elif percent >= 70:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN

    return f"{color}{bar}{Colors.GRAY} {percent}%"


def format_reset_time(timestamp_ms: int) -> str:
    """Format next reset time as relative time string (e.g. '4h 30m', '3d 4h')."""
    diff = timestamp_ms - int(time.time() * 1000)
    if diff <= 0:
        return "0m"
    days = diff // (1000 * 60 * 60 * 24)
    remainder = diff % (1000 * 60 * 60 * 24)
    hours = remainder // (1000 * 60 * 60)
    minutes = (remainder % (1000 * 60 * 60)) // (1000 * 60)
    if days > 0 and hours > 0:
        return f"{days}d {hours}h"
    if days > 0:
        return f"{days}d"
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h"
    return f"{minutes}m"


def render_status_line(data: dict, model_name: str = "",
                       cwd: str = "", git_branch: str = "") -> str:
    """Render the full 2-line status bar in Claude Code style.

    Line 1:  model | Tokens: [====------] 42% (Resets in 3h) | MCP: 15%
    Line 2:  project-dir | git:main

    Args:
        data: Usage data dict with token_percent, mcp_percent, etc.
        model_name: Display name of the current model.
        cwd: Current working directory (basename only).
        git_branch: Git branch name (empty if not a repo).
    """
    C = Colors

    if data.get("error") == "setup_required":
        return f"{C.YELLOW}\u26a0 Setup required (env vars not configured){C.RESET}"

    if data.get("error") == "loading":
        return f"{C.YELLOW}\u26a0 Loading usage data...{C.RESET}"

    # Resolve model name
    if not model_name:
        model_name = data.get("model_name", "Unknown")

    token_pct = data.get("token_percent", 0)
    wq_pct = data.get("token_percent_wq", 0)
    mcp_pct = data.get("mcp_percent", 0)
    reset_str = data.get("next_reset_time_str", "")
    wq_reset_str = data.get("next_reset_time_wq_str", "")

    # ── Line 1 ──
    model_part = f"{C.ORANGE}\u25b6 {model_name}{C.RESET}"
    usage_parts = []
    
    # 5 Hours quota
    token_part = f"5 Hours: {progress_bar(token_pct)}"
    if reset_str:
        token_part += f" {C.DIM}({reset_str}){C.RESET}"
    usage_parts.append(token_part)

    # Weekly quota
    if wq_pct:
        wq_part = f"Weekly: {progress_bar(wq_pct)}"
        if wq_reset_str:
            wq_part += f" {C.DIM}({wq_reset_str}){C.RESET}"
        usage_parts.append(wq_part)

    # MCP
    mcp_part = f"MCP: {mcp_pct}%"

    line1 = (
        f" {C.GRAY}\u2502{C.RESET} "
        f"{model_part} {C.GRAY}\u2502{C.RESET} "
        + "  ".join(usage_parts)
        + f" {C.GRAY}\u2502{C.RESET} "
        f"{mcp_part} "
    )

    # ── Line 2 ──
    parts = []
    if cwd:
        parts.append(f"{C.CYAN}\u25b6 {cwd}{C.RESET}")
    if git_branch:
        parts.append(f"{C.MAGENTA}\u2261 {git_branch}{C.RESET}")

    cost = data.get("total_cost", "0.00")
    if cost and cost != "0.00":
        parts.append(f"{C.GREEN}${cost}{C.RESET}")

    line2 = " " + f" {C.GRAY}\u2502{C.RESET} ".join(parts) if parts else ""

    return f"{line1}\n{line2}"
