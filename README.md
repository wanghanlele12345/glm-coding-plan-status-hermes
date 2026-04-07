# glm-coding-plan-status-hermes

> Z.AI / Zhipu AI Coding Plan usage monitor plugin for [Hermes Agent](https://github.com/emcie-co/hermes-agent)

![Status Bar Preview](preview.png)

Real-time usage status bar for Z.AI (Zhipu AI) Coding Plan subscribers. Displays token quota, MCP usage, estimated cost, and model info in a Claude Code-style status bar.

Converted from [glm-coding-plan-statusline](https://github.com/jeongsk/glm-coding-plan-statusline) (by @jeongsk) to Hermes plugin format.

## Features

- **Real-time usage monitoring** - Token and MCP quota with smart caching (5 min success / 2 min failure / 10 min stale)
- **Dual quota display** - Shows both 5-Hour and Weekly token quotas with reset countdowns
- **Auto status bar** - Usage info printed to terminal after each LLM turn via `post_llm_call` hook
- **Hermes CLI integration** - Patch included to show 5H + Weekly quota in the built-in TUI status bar
- **On-demand query** - Use the `zai_usage` tool to get a colorful ANSI status bar anytime
- **Zero dependencies** - Pure Python stdlib (urllib, json, pathlib)
- **Multiple platforms** - Supports Z.AI (`api.z.ai`), Zhipu AI (`open.bigmodel.cn`), and dev (`dev.bigmodel.cn`)
- **Cost estimation** - Estimates cost based on token usage (input: $3/M, output: $15/M)
- **Reset countdown** - Shows time until next quota reset for both 5H and Weekly
- **Claude Code-style design** - Colorful ANSI progress bars and layout matching Claude Code's status line

## Prerequisites

- [Hermes Agent](https://github.com/emcie-co/hermes-agent) installed and configured
- Z.AI / Zhipu AI Coding Plan subscription
- API credentials configured in Hermes (see below)

## Installation

### Option 1: Clone directly into plugins directory

```bash
cd ~/.hermes/plugins
git clone https://github.com/wanghanlele12345/glm-coding-plan-status-hermes.git zai-statusline
```

### Option 2: Manual copy

```bash
mkdir -p ~/.hermes/plugins/zai-statusline
# Copy all .py files, plugin.yaml into this directory
```

## Configuration

The plugin reads credentials from your existing Hermes configuration. Make sure your `~/.hermes/config.yaml` or `.env` file has:

```yaml
# In ~/.hermes/config.yaml
providers:
  zai:
    base_url: "https://api.z.ai/api/anthropic"
    auth_token: "your-api-token-here"
```

Or via environment variables:

```bash
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="your-api-token-here"
```

The plugin also checks Claude Code settings files as fallback:
- `.claude/settings.local.json`
- `.claude/settings.json`
- `~/.claude/settings.json`

## Usage

### Automatic (Recommended)

Once installed, the status bar is printed to the terminal after each assistant response:

```
 ▶ GLM-5 Turbo │ 5 Hours: [███████░░░] 79% (Resets in 3h 56m)  Weekly: [█████░░░░░] 64% (Resets in 3d 4h) │ MCP: 75%
 ▶ my-project ≡ main │ $0.42
```

### Hermes CLI Status Bar (Optional)

The plugin ships with a patch for Hermes CLI's built-in TUI status bar. After applying, the bottom status bar shows both 5H and Weekly quotas:

```
⚕ glm-5-turbo │ 19.4K/200K │ [███░░░░░░░░] 10% │ 3m │ 5H: 35% resets in 4h 13m │ Weekly: 67% resets in 4d 5h MCP: 75%
```

Apply the patch:

```bash
cd ~/.hermes/hermes-agent
git apply < ~/.hermes/plugins/zai-statusline/patches/hermes-cli-weekly-quota.patch
```

Then restart Hermes.

### On-Demand Tool

You can also ask the agent to show the full colorful status bar:

> "Show my usage status"

Or the agent can call the `zai_usage` tool directly, which outputs:

```
 │ ▶ GLM-5 Turbo │ Tokens: ████████░░ 79% (Resets in 3h 56m) │ MCP: 75%
 │ ▶ my-project ≡ main │ $0.42
```

## Plugin Structure

```
zai-statusline/
├── plugin.yaml        # Plugin manifest (name, version, hooks, tools)
├── __init__.py        # Entry point: register(ctx) - tools + hooks
├── api_client.py      # Z.AI API client: quota, model usage, tool usage
├── formatting.py      # ANSI colors, progress bars, status line rendering
├── model_mapper.py    # Claude/Anthropic model name -> GLM model name mapping
├── patches/
│   └── hermes-cli-weekly-quota.patch  # Patch for Hermes CLI TUI status bar
└── README.md
```

## How It Works

1. **post_llm_call hook** - After each LLM call completes, the plugin fetches usage data from the Z.AI monitoring API and prints a colorful status bar directly to the terminal
2. **zai_usage tool** - Registered as an on-demand tool for manual status checks with full ANSI formatting
3. **Hermes CLI integration** - A patch is provided to modify Hermes CLI's built-in TUI status bar to also display 5H + Weekly quotas
4. **Caching** - API responses are cached for 5 minutes (success), 2 minutes (failure), with a 10-minute stale fallback
5. **Auto-credentials** - Reads API tokens from environment variables, Hermes config, or Claude Code settings

## Supported API Endpoints

| Platform | Domain |
|----------|--------|
| Z.AI | `api.z.ai` |
| Zhipu AI | `open.bigmodel.cn` |
| Zhipu Dev | `dev.bigmodel.cn` |

## Caching

Usage data is cached at `~/.hermes/zai-usage-cache.json`:
- **Success**: 5 minute TTL
- **Failure**: 2 minute TTL (fast retry)
- **Stale fallback**: 10 minute absolute max — prevents status bar from disappearing during transient API failures

## Troubleshooting

### Status bar not showing

1. Check that the plugin is loaded: `hermes plugins list`
2. Verify your API credentials are set (see Configuration above)
3. Check Hermes logs: `~/.hermes/logs/` for any plugin errors
4. Ensure `ANTHROPIC_BASE_URL` points to a supported domain

### API errors / SSL issues

If you see SSL or connection errors, the plugin gracefully falls back and shows "Loading usage data...". This is usually a transient network issue - the cache will retry automatically.

### Status bar disappears mid-conversation

This was a known issue in v1.x (pre_llm_call approach). Since v2.0, the plugin uses `post_llm_call` to print directly to terminal, so this should no longer occur. If it does, check that the plugin is loaded and API credentials are valid.

## Credits

- Original [glm-coding-plan-statusline](https://github.com/jeongsk/glm-coding-plan-statusline) by @jeongsk - Claude Code plugin for Z.AI usage monitoring
- Converted to Hermes plugin format for [Hermes Agent](https://github.com/emcie-co/hermes-agent)

## License

MIT
