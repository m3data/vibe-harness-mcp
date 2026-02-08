# Vibe Harness — MCP Server Implementation Plan

## Context

Vibe Harness is a local-first MCP server that tunes human-AI interaction rhythm based on working modes and optional biosignal data. It repackages research infrastructure from Tend (mode engine), EBS (biosignal processing), and Semantic Climate (session management, safety gate) into a lightweight tool for builders and vibe coders.

The key insight: "Humans are variable and models are adjustable." Most AI tools assume stable humans and optimize model output. Vibe Harness inverts this — it adjusts AI behavior to match the human's working state.

**Layer 1 (this plan):** Manual mode switching with research-informed presets. No hardware.
**Layer 2 (future):** Polar H10 BLE integration for real biosignal (HRV, phase dynamics).
**Layer 3 (future):** Full loop — semantic coupling + biosignal + session history patterns.

---

## Architecture

### File Structure

```
vibe-harness/
├── server.py                # FastMCP entry point (stdio transport)
├── session.py               # Session state (VibeSession dataclass)
├── modes.py                 # Mode definitions, transitions, friction
├── governor.py              # Nudge logic (time-based, count-based)
├── config.py                # Config loading (user + project + runtime)
├── formatters.py            # String formatting for MCP tool returns
├── presets/
│   └── modes.json           # Mode definitions (orientations, friction matrix)
├── biosignal/               # Layer 2 stub
│   ├── __init__.py
│   └── provider.py          # Abstract BiosignalProvider interface
├── tests/
│   ├── test_session.py
│   ├── test_modes.py
│   ├── test_governor.py
│   └── test_formatters.py
├── pyproject.toml
├── requirements.txt         # mcp>=1.25.0
└── README.md
```

### Porting Map

| Source | What | Target | Adaptation |
|--------|------|--------|------------|
| `zotero-mcp/server.py` | MCP server pattern | `server.py` | Same FastMCP + stdio pattern |
| `tend/config/mode-prompts.json` | Mode structure, friction | `presets/modes.json` | Reframe 5 modes for builders |
| `tend/parsers/harness_state.py` | `compute_regulatory_state()` | `governor.py` | Simplify: time + count nudges only, no debt/drift |
| `tend/parsers/harness_state.py` | JSONL mode logging | `session.py` | Same pattern, lighter schema |
| `semantic-climate/safety_gate.py` | Tiered template output | `governor.py` | Adapt for nudge message rendering |
| `semantic-climate/session_manager.py` | Session export pattern | `session.py` | Version-tracked JSON export |

**Not porting:** Tend's markdown state (not appropriate for headless MCP), EBS's BLE code (Layer 2), Semantic Climate's embedding pipeline (Layer 3).

---

## Modes (5)

| Mode | Somatic Posture | AI Behavior |
|------|----------------|-------------|
| **explore** | Open, low activation, wandering safe | Divergent, questions back, surfaces connections, longer responses OK |
| **build** | Forward-leaning, hands want to move | Concise, code-first, minimal hedging, reasonable defaults |
| **think-with** | Settled, comfortable with not-knowing | Reflective, holds complexity, asks hard questions, no premature synthesis |
| **ship** | Committed, mobilized | Decisive, opinionated, catches scope creep, bias toward shipping |
| **cool-off** | System needs downregulation | Minimal, short, captures stray thoughts, suggests stopping |

### Transition Friction

```
explore -> build:      none     (natural progression)
explore -> ship:       high     (skips the in-between)
build -> ship:         none     (natural commitment)
build -> explore:      medium   (stepping back)
think-with -> ship:    high     (reflection to execution is a leap)
think-with -> build:   medium   (reasonable progression)
ship -> explore:       medium   (decommitting)
ship -> cool-off:      none     (relief)
cool-off -> ship:      high     (not ready yet?)
cool-off -> explore:   none     (gentle re-entry)
any -> cool-off:       none     (always allowed)
```

High friction: requires calling `vibe_set_mode()` twice to confirm.

---

## MCP Tools (6)

### `vibe_set_mode(mode: str) -> str`
Switch working mode. Returns orientation text + session stats. High-friction transitions return a warning; repeat the call to confirm.

### `vibe_check() -> str`
Current state: mode, duration, interaction count, pending nudges, biosignal (Layer 2). Called by the AI to understand current context.

### `vibe_nudge() -> str`
Explicitly request a nudge. Governor evaluates session state and returns contextual suggestion or "all clear."

### `vibe_history() -> str`
Mode transition timeline + time-in-mode summary for current session.

### `vibe_session_export() -> str`
Export session data as JSON to `~/.vibe-harness/sessions/`. Returns file path + summary.

### `vibe_configure(setting: str, value: str) -> str`
Runtime config adjustment (nudge thresholds, friction enable/disable).

---

## MCP Resources (2)

### `vibe://context`
Current mode orientation text. MCP clients can inject this into system prompt.

### `vibe://status`
One-line session status: `Build | 42min | 31 interactions | no nudges pending`

---

## Governor (Nudge Logic)

Pull model only — nudges surface when `vibe_check()` or `vibe_nudge()` is called. Never proactively injected.

### Triggers
- **Mode duration:** After 45min (configurable) in same mode, surface check-in. Different message per mode.
- **Session duration:** After 120min (configurable), suggest Cool-off regardless of mode.
- **Interaction count:** After 100 interactions (configurable) without mode switch, surface prompt.
- **Mode drift:** Explore 30+ min with high interactions -> suggest Build. Ship 60+ min -> suggest Build might be more honest.

### Constraints
- Max one nudge per 15 minutes (no nagging)
- Nudges are suggestions, never blocks
- All nudges logged for session export

### Layer 2 extensions (designed, not implemented)
When biosignal available: HRV trend declining + Build -> suggest break. Settling pattern + Explore -> suggest committing. Recovery pattern + Cool-off -> suggest re-engaging.

### Actionable nudge responses (designed, not implemented)
Currently nudges are passive text. Claude Code's bottom-bar buttons/options pattern (AskUserQuestion) demonstrates that guided choices reduce cognitive load at decision points. Nudges should present clear next actions rather than just observations.

For example, a mode duration nudge could surface as:
```
You've been exploring for 50min.
  → /vibe-mode build     (start building)
  → /vibe-mode think-with (sit with it)
  → dismiss              (stay in explore)
```

MCP tools currently return plain strings — no structured UI. Options:
1. Format nudge text with clear action hints (achievable now)
2. Watch for MCP spec extensions supporting richer response types (future)
3. If nudge responses become a Claude Code hook, could integrate with AskUserQuestion natively

---

## State & Persistence

- **Runtime:** `VibeSession` dataclass in memory (authoritative during session)
- **Mode history:** Append-only JSONL at `~/.vibe-harness/mode-history.jsonl`
- **Session export:** JSON at `~/.vibe-harness/sessions/{date}_{time}_{id}.json`
- **Session lifecycle:** Starts implicitly on first tool call. Ends when MCP process terminates. Auto-export via `atexit` if configured.

### Config Resolution
`defaults < ~/.vibe-harness/config.json < .vibe-harness.json (project) < vibe_configure() (runtime)`

---

## Implementation Sequence

### Step 1: Project scaffold [DONE]
- Created `vibe-harness/` in EarthianLabs, own git repo
- `pyproject.toml` with ESL-A license
- Set up venv, installed `mcp>=1.25.0`
- Created `server.py` with FastMCP scaffold, all 6 tools
- Registered in `~/.claude.json`

### Step 2: Modes + state [DONE]
- Wrote `presets/modes.json` (5 modes, friction matrix, orientation text)
- Implemented `modes.py` (load modes, friction lookup, validation)
- Implemented `session.py` (`VibeSession`, `ModeTransition`, mode switching with friction)
- Implemented `vibe_set_mode()` with friction handling (double-call confirm for high friction)
- Implemented `vibe_check()` with current state rendering
- Implemented `vibe://context` and `vibe://status` resources
- Implemented `formatters.py` for consistent tool output
- 16 integration tests passing via MCP protocol

### Step 3: Governor + history [DONE]
- Implemented `governor.py` with 5 priority-ordered rules (cooldown, session duration, mode duration, drift, interaction count)
- All thresholds from `config.get()` — runtime overrides work
- JSONL mode history logging at `~/.vibe-harness/mode-history.jsonl`
- `vibe_check()` now surfaces nudges alongside state
- ASCII banners per mode (`~~~` explore, `>>>` build, `???` think-with, `!!!` ship, `...` cool-off)
- Friction banner (`╳╳╳`), nudge banner (`- - -`), history with emoji bar charts
- Slash commands: `/vibe`, `/vibe-mode`, `/vibe-history`

### Step 4: Config file loading [DONE]
- `config.py` defaults + runtime overrides implemented in Step 2
- `vibe_configure()` runtime overrides working
- `vibe_session_export()` with versioned schema working
- Three-layer file resolution: `defaults < ~/.vibe-harness/config.json < .vibe-harness.json < runtime`
- Unknown keys in config files silently ignored
- `reload()` re-reads files preserving runtime overrides
- `list_config_sources()` shows resolution source per key

### Step 5: Tests + Layer 2 interface [DONE]
- 73 unit tests: 10 modes, 20 session, 20 governor, 16 formatters, 2 JSONL, 5 config
- `BiosignalProvider` abstract class already implemented (Step 1)
- README with mode banners, setup, configuration docs
- All tests passing

---

## Verification

1. **Tool discovery:** After registration, Claude Code shows all 6 `vibe_*` tools [VERIFIED]
2. **Mode switching:** `vibe_set_mode("build")` returns orientation; `vibe_set_mode("ship")` after explore returns friction warning; second call confirms [VERIFIED]
3. **Vibe check:** `vibe_check()` returns mode + duration + interaction count [VERIFIED]
4. **Nudge:** After 45+ min in same mode, `vibe_nudge()` surfaces check-in [VERIFIED]
5. **History:** `vibe_history()` shows timeline after multiple mode switches [VERIFIED]
6. **Export:** `vibe_session_export()` writes valid JSON to `~/.vibe-harness/sessions/` [VERIFIED]
7. **Config:** `vibe_configure("nudges.time_check_minutes", "60")` updates threshold [VERIFIED]
8. **Resource:** `vibe://context` returns current mode orientation text [VERIFIED]

---

## Open Design Threads

Captured 2026-02-08. These emerged from mapping the landing page value proposition against lived-experience research on AI-induced fatigue, then pressure-testing the MCP flow against the interoceptive awareness framing.

### 1. Cross-Session Allostatic Load

Layer 1 is session-scoped. The governor resets with each new MCP process. But the research evidence (context-building/vibing-research.md) shows fatigue accumulates across days, not sessions. "Fine for the first few hours, wrecked the next day." "By day three I'm useless."

The JSONL mode history at `~/.vibe-harness/mode-history.jsonl` is already write-only persistent. Nothing reads it back to inform the next session's starting conditions.

**Design question:** What does carry-forward look like? Options:
- Simple: cumulative session minutes over trailing 3 days, session count, average session length
- Richer: how the last session ended (cool-off reached vs abrupt stop), what mode it was in, whether the session escalated (explore→build→ship without pauses). An abrupt stop with no cool-off is itself a signal, the way a cortisol curve that never returns to baseline tells you something different from one that does.

**Status:** Buildable as Layer 1.x. Data already exists.

### 2. Ground as Exit, Not Mode

The current five modes all assume the human is still working with the AI. There's no response for "I need to stop and remember who I am." The research describes this clearly: "It takes me an hour to feel like a human again." "I close the laptop and feel oddly hollow."

Initial instinct was a sixth mode (Ground/Reclaim). Better framing: this isn't a mode, it's an exit. A mode implies the AI is still active and participating. Grounding means the AI should go quiet. That's architecturally different.

**Design direction:** A governor rule rather than a mode. When accumulated signals suggest dysregulation (sustained build with no cool-off, cross-session escalation, abrupt prior session endings), the recommendation isn't a mode switch. It's "close the laptop." The tool recognising its own boundary.

**Tension:** How does a tool recommend its own absence? What does that look like in MCP output? This connects to the Somatic AI Safety paper.

### 3. The Bootstrap Problem and Consent-to-Push

Pull-only is a principled choice (locus of control stays with the human). But it has a failure mode exactly where it matters most. The research describes dissociative states where metacognitive awareness is reduced: "I'm physically here but mentally still prompting." The people most at risk are the ones least likely to call `vibe_check()`.

Layer 2 biosignal partially addresses this (HRV doesn't require metacognitive awareness to detect dysregulation). But there's a gap between Layer 1 and Layer 2.

**Intermediate design: consent-to-push as a continuum.** Rather than a binary toggle, onboarding could establish a care threshold:

- **Silent** (default) — Pure pull. No AI-initiated check-ins. You call `vibe_check()` when you choose to.
- **Gentle** — AI may ask "how are you feeling?" after long stretches, but only when you're already in conversation. No interruption of flow.
- **Active** — AI periodically calls `vibe_check()` and surfaces nudges. You consented to this. You can revoke anytime.

This is a consent gradient configured once and adjustable. The onboarding moment itself becomes interoceptive: you have to notice what level of support you need.

**Critical principle:** This must be named honestly. "Gentle" and "Active" are push, even when framed as pull. Default must be Silent. Opt-in push, not default push. Otherwise we've built the same always-on nudging system the tool critiques.

### 4. Polyvagal Framing

The transition friction matrix is encoding a claim about ventral vagal windows: certain cognitive transitions are safe when the nervous system is regulated and risky when it's not. The friction isn't about the cognitive leap from explore to ship. It's about the autonomic cost of skipping integrative phases.

This theoretical grounding (Porges, Dana) should be explicit in this document. Currently the friction matrix reads as informed intuition. With polyvagal framing named, it reads as applied neuroscience.

**Status:** Quick write. Needs Porges (2011) polyvagal theory and Dana (2018) clinical applications as explicit references. The friction matrix section above should note the autonomic basis.

### 5. The Tool as Argument

Every design choice in Vibe Harness is a position in the autonomy-vs-care debate:
- Pull-only with its known failure mode: a claim about where the locus of control should sit
- The friction matrix encoding autonomic cost: a claim about embodied transition dynamics
- Defeasible governance with full traces: a claim about transparency in AI behavioural modification
- The interoception-first reframe ("helps you notice where you are"): a claim about what the tool believes

The design choices are evidence for the Somatic AI Safety paper and the preprint. The tool is an argument, not just an instrument.

### 6. Reflexivity as Methodology

This tool is being designed, built, and tested by the same person who is researching human-AI coupling dynamics, while working with an AI collaborator who has full context on the research ecology. Researcher, subject, and tool-builder are the same person. This is methodologically unusual and should be named explicitly in the preprint as a feature of generative action research, not a limitation. The reflexivity is the rigour.

---

## Critical Reference Files

- `zotero-mcp/server.py` — MCP server pattern (FastMCP, stdio, tool registration)
- `tend/config/mode-prompts.json` — Mode definitions to adapt
- `tend/parsers/harness_state.py` — Governor pattern, JSONL logging
- `Earthian-BioSense/src/processing/hrv.py` — Layer 2 reference (HRV metrics)
- `Earthian-BioSense/src/biosignal/provider.py` — Layer 2 abstract interface pattern
- `semantic-climate-phase-space/.../session_manager.py` — Session export pattern
