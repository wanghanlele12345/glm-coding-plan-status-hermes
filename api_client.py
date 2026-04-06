"""
Z.AI / Zhipu AI API client for quota and usage data.
Pure Python + stdlib (urllib) — no external dependencies.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Supported API domains
SUPPORTED_DOMAINS = (
    "api.z.ai",
    "open.bigmodel.cn",
    "dev.bigmodel.cn",
)

DEFAULT_TIMEOUT = 3  # seconds

# Cache file and TTL
CACHE_FILE = Path.home() / ".hermes" / "zai-usage-cache.json"
CACHE_TTL_SUCCESS = 60_000   # 60 seconds
CACHE_TTL_FAILURE = 15_000   # 15 seconds


def _build_api_urls(base_url: str) -> Dict[str, str]:
    """Derive monitoring API URLs from base URL."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or ""
    proto = parsed.scheme or "https"

    if not any(host.endswith(d) or d in host for d in SUPPORTED_DOMAINS):
        raise ValueError(
            f"Unsupported base URL domain. Supported: {', '.join(SUPPORTED_DOMAINS)}"
        )

    base = f"{proto}://{host}"
    return {
        "quota_limit_url": f"{base}/api/monitor/usage/quota/limit",
        "model_usage_url": f"{base}/api/monitor/usage/model-usage",
        "tool_usage_url": f"{base}/api/monitor/usage/tool-usage",
    }


def _https_get(url: str, auth_token: str,
               params: str = "", timeout: int = DEFAULT_TIMEOUT) -> Any:
    """Make an HTTPS GET request and return parsed JSON."""
    full_url = f"{url}{params}" if params else url
    req = urllib.request.Request(full_url, method="GET")
    req.add_header("Authorization", auth_token)
    req.add_header("Accept-Language", "en-US,en")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise urllib.error.HTTPError(full_url, resp.status, resp.reason, {}, None)
        return json.loads(resp.read().decode("utf-8"))


def _fmt_datetime(dt: datetime) -> str:
    """Format datetime as 'yyyy-MM-dd HH:mm:ss'."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config() -> Optional[Dict[str, str]]:
    """Read API credentials from environment or Claude settings files.

    Checks (in order):
      1. Environment variables ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN
      2. .claude/settings.local.json
      3. .claude/settings.json
      4. ~/.claude/settings.json
    """
    import os

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

    if base_url and auth_token:
        return {"base_url": base_url, "auth_token": auth_token}

    # Try Claude settings files
    candidates = []
    cwd_config = Path.cwd() / ".claude"
    for name in ("settings.local.json", "settings.json"):
        candidates.append(cwd_config / name)
    candidates.append(Path.home() / ".claude" / "settings.json")

    for fp in candidates:
        try:
            data = json.loads(fp.read_text("utf-8"))
            env = data.get("env", {})
            bu = env.get("ANTHROPIC_BASE_URL", "")
            at = env.get("ANTHROPIC_AUTH_TOKEN", "")
            if bu and at:
                return {"base_url": bu, "auth_token": at}
        except (OSError, json.JSONDecodeError, KeyError):
            continue

    return None


def fetch_quota(urls: Dict[str, str], auth_token: str) -> Dict[str, Any]:
    """Fetch token and MCP quota limits."""
    result = _https_get(urls["quota_limit_url"], auth_token)
    limits = result.get("data", {}).get("limits", [])

    mcp_pct = 0
    next_reset_ms: Optional[int] = None

    # Collect all TOKENS_LIMIT entries, pick the one with highest usage
    token_limits = [lim for lim in limits if lim.get("type") == "TOKENS_LIMIT"]
    if token_limits:
        # Sort by percentage descending to get the most-consumed tier
        token_limits.sort(key=lambda l: l.get("percentage", 0), reverse=True)
        token_pct = round(token_limits[0].get("percentage", 0))
        # Use the earliest reset time (soonest limit)
        resets = [l.get("nextResetTime") for l in token_limits if l.get("nextResetTime")]
        next_reset_ms = min(resets) if resets else None
    else:
        token_pct = 0

    for lim in limits:
        if lim.get("type") == "TIME_LIMIT":
            mcp_pct = round(lim.get("percentage", 0))

    return {
        "token_percent": token_pct,
        "mcp_percent": mcp_pct,
        "next_reset_time": next_reset_ms,
    }


def fetch_model_usage(urls: Dict[str, str], auth_token: str,
                      start_time: str, end_time: str) -> Dict[str, Any]:
    """Fetch model usage and estimate cost."""
    params = f"?startTime={urllib.parse.quote(start_time)}&endTime={urllib.parse.quote(end_time)}"
    result = _https_get(urls["model_usage_url"], auth_token, params)
    items = result.get("data", {}).get("list", [])

    total_in = sum(i.get("inputTokens", 0) for i in items)
    total_out = sum(i.get("outputTokens", 0) for i in items)
    cost = (total_in / 1_000_000) * 3 + (total_out / 1_000_000) * 15
    raw_model = items[0].get("model", "Unknown") if items else "Unknown"

    return {
        "total_cost": f"{cost:.2f}",
        "raw_model": raw_model,
        "has_data": len(items) > 0,
    }


def fetch_tool_usage(urls: Dict[str, str], auth_token: str,
                     start_time: str, end_time: str) -> int:
    """Fetch tool usage count and return MCP percentage estimate."""
    params = f"?startTime={urllib.parse.quote(start_time)}&endTime={urllib.parse.quote(end_time)}"
    result = _https_get(urls["tool_usage_url"], auth_token, params)
    items = result.get("data", {}).get("list", [])
    return min(100, len(items) * 5) if items else 0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _load_cache() -> Optional[Dict]:
    try:
        if CACHE_FILE.exists():
            raw = CACHE_FILE.read_text("utf-8")
            return json.loads(raw)
    except Exception:
        pass
    return None


def _save_cache(data: Dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data), "utf-8")
    except Exception:
        pass


def fetch_usage_data() -> Dict[str, Any]:
    """Fetch all usage data with caching.

    Returns a dict with: token_percent, mcp_percent, total_cost,
    model_name, next_reset_time, next_reset_time_str, error.
    """
    # Check cache first
    cache = _load_cache()
    if cache:
        ts = cache.get("timestamp", 0)
        ttl = CACHE_TTL_FAILURE if cache.get("data", {}).get("apiUnavailable") else CACHE_TTL_SUCCESS
        if time.time() * 1000 - ts < ttl:
            return cache["data"]

    # Load config
    cfg = load_config()
    if not cfg:
        return {"error": "setup_required", "model_name": "Unknown",
                "token_percent": 0, "mcp_percent": 0, "total_cost": "0.00"}

    try:
        urls = _build_api_urls(cfg["base_url"])
        auth = cfg["auth_token"]

        # Time window: last 5 hours
        now = datetime.now()
        five_h_ago = now - timedelta(hours=5)
        start = _fmt_datetime(five_h_ago)
        end = _fmt_datetime(now)

        # Parallel-ish fetch (sequential is fine for 3 lightweight calls)
        quota = fetch_quota(urls, auth)

        mcp_pct = quota.get("mcp_percent", 0)
        try:
            tool_pct = fetch_tool_usage(urls, auth, start, end)
            if tool_pct > 0:
                mcp_pct = tool_pct
        except Exception:
            pass

        total_cost = "0.00"
        raw_model = "Unknown"
        try:
            mu = fetch_model_usage(urls, auth, start, end)
            total_cost = mu["total_cost"]
            raw_model = mu["raw_model"]
        except Exception:
            pass

        from .model_mapper import map_model_name
        model_name = map_model_name(raw_model)

        # Format reset time
        next_reset_str = ""
        if quota.get("next_reset_time"):
            from .formatting import format_reset_time
            next_reset_str = format_reset_time(quota["next_reset_time"])

        data = {
            "token_percent": quota.get("token_percent", 0),
            "mcp_percent": mcp_pct,
            "total_cost": total_cost,
            "model_name": model_name,
            "timestamp": int(time.time() * 1000),
            "next_reset_time": quota.get("next_reset_time"),
            "next_reset_time_str": next_reset_str,
        }

        _save_cache({"data": data, "timestamp": data["timestamp"]})
        return data

    except Exception as exc:
        logger.debug("fetch_usage_data failed: %s", exc)
        return {"error": "loading", "apiUnavailable": True}
