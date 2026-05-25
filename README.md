# Vibe Harness MCP

![Repo Status](https://img.shields.io/badge/REPO_STATUS-Active_Research-blue?style=for-the-badge&labelColor=8b5e3c&color=e5dac1)
![Version](https://img.shields.io/badge/VERSION-0.5.0-blue?style=for-the-badge&labelColor=3b82f6&color=1e40af)
![License](https://img.shields.io/badge/LICENSE-ESL--A-green?style=for-the-badge&labelColor=10b981&color=047857)
![Tests](https://img.shields.io/badge/TESTS-166_passing-green?style=for-the-badge&labelColor=10b981&color=047857)
![MCP](https://img.shields.io/badge/MCP-stdio-purple?style=for-the-badge&labelColor=7c3aed&color=5b21b6)

An MCP server that attunes human-AI interaction rhythm based on working modes.

Spending time and energy vibing with an AI should feel like a dance. Vibe Harness is an experiment in making that dance more intuitive and responsive. Built from the premise that humans and our nervous systems are variable and AI models are adjustable. Most AI vibing tools assume stable humans and optimise model output. Vibe Harness inverts this. Adjusting AI model behaviour to match your working state.

## Install

One line:

```bash
claude mcp add vibe-harness -- uvx --from "git+https://github.com/m3data/vibe-harness-mcp.git" vibe-harness-mcp
```

Or from a local clone:

```bash
git clone https://github.com/m3data/vibe-harness-mcp.git
cd vibe-harness-mcp
pip install -e .
claude mcp add vibe-harness -- uvx --from . vibe-harness-mcp
```

Or register manually in `~/.claude.json` under `mcpServers`:

```json
{
  "vibe-harness": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/m3data/vibe-harness-mcp.git", "vibe-harness-mcp"],
    "type": "stdio"
  }
}
```

## Modes

| Mode | Orientation |
|------|-------------|
| **Explore** | Open, divergent, follow threads |
| **Build** | Concise, code-first, action-biased |
| **Think-with** | Reflective, holds complexity |
| **Ship** | Decisive, catches scope creep |
| **Cool-off** | Minimal output, wind-down |

## Transition Friction

Not all mode switches are equal. Some transitions have friction:

- **None**: Natural progression (explore -> build, build -> ship)
- **Medium**: Stepping back — acknowledged but allowed (build -> explore)
- **High**: Big leap — requires calling `vibe_set_mode()` twice to confirm (explore -> ship, cool-off -> ship)

Cool-off is always friction-free to enter.

## Tools

| Tool | Purpose |
|------|---------|
| `vibe_set_mode(mode)` | Switch working mode |
| `vibe_check()` | Current state + clock time + pending nudges |
| `vibe_nudge()` | Request a contextual suggestion |
| `vibe_history()` | Mode transition timeline |
| `vibe_session_export()` | Export session JSON to `~/.vibe-harness/sessions/` |
| `vibe_configure(setting, value)` | Adjust thresholds at runtime |

## Slash Commands

The `skills/` directory contains Claude Code skill definitions for convenient slash commands:

- `/vibe` — check current state
- `/vibe-mode <mode>` — switch mode
- `/vibe-history` — transition timeline

To install, copy the skill folders into your project's `.claude/skills/` directory:

```bash
cp -r /path/to/vibe-harness-mcp/skills/* /your/project/.claude/skills/
```

## Temporal Awareness

Vibe Harness knows what time it is and how your day has gone.

`vibe_check()` now shows:
- **Clock time** and period (morning, afternoon, evening, late night)
- **Sessions today** — how many times you've used it and total minutes
- **Late-night nudge** — gentle circadian check-in when working past 10pm or before 6am

Cross-session patterns are mined from `~/.vibe-harness/mode-history.jsonl` — the same file that already records every mode transition. No new data collection.

Late-night thresholds are configurable:
```bash
vibe_configure("temporal.late_night_start", "23")  # default: 22
vibe_configure("temporal.late_night_end", "5")      # default: 6
```

## Governor (Nudge Logic)

Pull-only — nudges surface when you call `vibe_check()` or `vibe_nudge()`. Never proactively injected.

**Active time, not wall-clock time.** The governor tracks when you actually interact with the tool. If your terminal stays open overnight or you go for a walk, idle gaps (30+ min between tool calls) are detected and subtracted. A 10-hour session where you were active for 45 minutes produces no false nudges. `vibe_check()` shows detected away time so you can see what the governor sees.

Rules (in priority order):
1. **Cooldown** — max one nudge per 15min
2. **Session duration** — after 120min active, suggest cool-off
3. **Mode duration** — after 45min active in one mode, mode-specific check-in
4. **Mode drift** — e.g. explore with high interactions -> "might be building without naming it"
5. **Interaction count** — 100+ actions without a mode switch -> check in
6. **Late night** — circadian nudge when working past configured hours

All thresholds configurable via `vibe_configure()` or config files.

## Defeasible Governance

Governance rules can be overridden. This is by design.

Think of it like screen time alerts on your phone. The alert fires based on a rule ("you've been scrolling for 45 minutes") but other rules can override it ("you already saw a nudge 5 minutes ago, don't nag"). The first rule's conclusion is *defeated* by the second rule's higher priority.

Vibe Harness makes this explicit:
- Each rule has a **name**, **priority**, and **type** (suppress, nudge, or drift)
- Each rule declares what can defeat it
- Session exports include a **governance trace** showing which rules fired and which were overridden

This matters for accountability. Silent overrides are invisible governance. Explicit defeasibility means you can see *why* a nudge did or didn't appear.

### Rule Priority (highest first)

| Priority | Rule | Type | Defeated By |
|----------|------|------|-------------|
| 1 | Cooldown suppression | suppress | (nothing) |
| 2 | Session duration | nudge | cooldown |
| 3 | Mode duration | nudge | cooldown, session duration |
| 4 | Mode drift | drift | cooldown, session duration, mode duration |
| 5 | Interaction count | nudge | cooldown, session duration, mode duration, mode drift |
| 6 | Late night | nudge | all higher-priority rules |

Rules are data, not code. Layer 2 (biosignal) and Layer 3 (semantic coupling) will add new rules and defeaters without restructuring existing logic.

## Configuration

Three-layer resolution: `defaults < ~/.vibe-harness/config.json < .vibe-harness.json < runtime`

```json
{
  "nudges.time_check_minutes": 45,
  "nudges.session_max_minutes": 120,
  "nudges.interaction_threshold": 100,
  "nudges.cooldown_minutes": 15,
  "friction.enabled": true,
  "export.auto_export": false,
  "activity.idle_threshold_minutes": 30,
  "temporal.late_night_start": 22,
  "temporal.late_night_end": 6
}
```

## Persistence

- **Mode history**: `~/.vibe-harness/mode-history.jsonl` (append-only, every transition)
- **Session exports**: `~/.vibe-harness/sessions/*.json` (on-demand via `vibe_session_export()` — includes wall-clock and active durations, idle gaps, governance trace)
- **Config**: `~/.vibe-harness/config.json` (user-level) or `.vibe-harness.json` (project-level)

## Layers

- **Layer 1** (current): Manual mode switching with research-informed presets + temporal awareness
- **Layer 2** (designed): Polar H10 BLE integration for biosignal-informed nudges
- **Layer 3** (future): Full loop — semantic coupling + biosignal + session history patterns

## Setup (Development)

```bash
git clone https://github.com/m3data/vibe-harness-mcp.git
cd vibe-harness-mcp
pip install -e .
python -m vibe_harness_mcp  # stdio transport for MCP
```

## Tests

```bash
pip install -e ".[dev]"  # or: pip install pytest
python -m pytest tests/ -v
```

## License

Earthian Stewardship License (ESL-A) v0.1
