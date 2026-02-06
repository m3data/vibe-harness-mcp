# Vibe Harness

An MCP server that tunes human-AI interaction rhythm based on working modes.

Humans are variable and models are adjustable. Most AI tools assume stable humans and optimize model output. Vibe Harness inverts this — it adjusts AI behavior to match the human's working state.

## Modes

```
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
~        E X P L O R E        ~        >          B U I L D          >
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
Open, divergent, follow threads        Concise, code-first, action-biased

???????????????????????????????        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
?      T H I N K - W I T H    ?        !           S H I P           !
???????????????????????????????        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Reflective, holds complexity           Decisive, catches scope creep

...............................
.       C O O L - O F F       .
...............................
Minimal output, wind-down
```

## Transition Friction

Not all mode switches are equal. Some transitions have friction:

- **None**: Natural progression (explore → build, build → ship)
- **Medium**: Stepping back — acknowledged but allowed (build → explore)
- **High**: Big leap — requires calling `vibe_set_mode()` twice to confirm (explore → ship, cool-off → ship)

Cool-off is always friction-free to enter.

## Tools

| Tool | Purpose |
|------|---------|
| `vibe_set_mode(mode)` | Switch working mode |
| `vibe_check()` | Current state + pending nudges |
| `vibe_nudge()` | Request a contextual suggestion |
| `vibe_history()` | Mode transition timeline |
| `vibe_session_export()` | Export session JSON to `~/.vibe-harness/sessions/` |
| `vibe_configure(setting, value)` | Adjust thresholds at runtime |

## Slash Commands

If running inside Claude Code with skills configured:

- `/vibe` — check current state
- `/vibe-mode <mode>` — switch mode
- `/vibe-history` — transition timeline

## Governor (Nudge Logic)

Pull-only — nudges surface when you call `vibe_check()` or `vibe_nudge()`. Never proactively injected.

Rules (in priority order):
1. **Cooldown** — max one nudge per 15min
2. **Session duration** — after 120min, suggest cool-off
3. **Mode duration** — after 45min in one mode, mode-specific check-in
4. **Mode drift** — e.g. explore with high interactions → "might be building without naming it"
5. **Interaction count** — 100+ actions without a mode switch → check in

All thresholds configurable via `vibe_configure()` or config files.

## Configuration

Three-layer resolution: `defaults < ~/.vibe-harness/config.json < .vibe-harness.json < runtime`

```json
{
  "nudges.time_check_minutes": 45,
  "nudges.session_max_minutes": 120,
  "nudges.interaction_threshold": 100,
  "nudges.cooldown_minutes": 15,
  "friction.enabled": true,
  "export.auto_export": false
}
```

## Persistence

- **Mode history**: `~/.vibe-harness/mode-history.jsonl` (append-only, every transition)
- **Session exports**: `~/.vibe-harness/sessions/*.json` (on-demand via `vibe_session_export()`)
- **Config**: `~/.vibe-harness/config.json` (user-level) or `.vibe-harness.json` (project-level)

## Layers

- **Layer 1** (current): Manual mode switching with research-informed presets
- **Layer 2** (designed): Polar H10 BLE integration for biosignal-informed nudges
- **Layer 3** (future): Full loop — semantic coupling + biosignal + session history patterns

## Setup

```bash
cd vibe-harness
pip install -r requirements.txt
python server.py  # stdio transport for MCP
```

Register in `~/.claude.json` under `mcpServers`:

```json
{
  "vibe-harness": {
    "command": "python",
    "args": ["/path/to/vibe-harness/server.py"],
    "type": "stdio"
  }
}
```

## Tests

```bash
cd vibe-harness
python -m pytest tests/ -v
```

## License

Earthian Stewardship License (ESL-A) v0.1
