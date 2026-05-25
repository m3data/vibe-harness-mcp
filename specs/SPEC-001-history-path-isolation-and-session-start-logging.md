# SPEC-001 — History Path Isolation + Session-Start Logging

**Status:** Draft, ready for build
**Created:** 2026-05-25
**Author:** Mat Mytka + Kairos
**Mode to execute in:** build (tests-first)

---

## Problem

`HISTORY_FILE = Path.home() / ".vibe-harness" / "mode-history.jsonl"` is a global module constant (`session.py:13-14`). The test suite imports it directly (`tests/test_session.py` and likely others) and reads/writes the **live production file** — currently 815 lines, read by the statusline, the Ghostty watcher, and `vibe_history`. Running the suite mutates live session state.

There is finished-but-uncommitted work in the tree (since 8 Mar) that *worsens* this coupling:

- `session.py` — a `__post_init__` that logs a `session-start` transition on construction, so external readers reflect the mode from minute one. (This is the fix for the 2026-05-24 blind spot where `vibe_history` showed "no transitions" for 319 minutes because session-start-in-Explore was never logged.)
- `test_session.py` — updated to expect the new `session-start` line.

With `__post_init__` logging, **merely constructing `VibeSession()` writes to live history** — so every test that instantiates a session pollutes the production file. The more-observable feature deepens the test/prod entanglement. We cannot run the suite to verify the feature without corrupting the state the feature exists to report.

(The orchestration-presets change that shared this dirty tree was committed separately as `b2de0b7` — out of scope here.)

## Goal

Make the history path injectable so tests run fully isolated from `~/.vibe-harness/`, then land the session-start logging + its tests cleanly, with downstream consumers correct. One coherent commit.

## Scope — in

1. **Injectable history path.**
   - Resolve the history dir through an env override: `VIBE_HARNESS_HISTORY_DIR` (precedence: env > default `~/.vibe-harness`). Resolve via the existing `config` module (already imported in `session.py`) rather than a bare module constant.
   - Keep a path accessor the tests and other modules can use. **Audit all importers of `HISTORY_FILE`/`HISTORY_DIR` first** (`rg "HISTORY_FILE|HISTORY_DIR"`) — if switching from constant to function, every importer must move with it, or keep a module-level value that's re-resolvable.

2. **Test isolation.** Add `tests/conftest.py` with an **autouse fixture** that points the history dir at `tmp_path` (via the env override or monkeypatch) for the whole suite. No test touches `~/.vibe-harness/`.

3. **Land the session-start logging** (`__post_init__`) + its tests — already written, currently dirty in the tree.

4. **Fix the two downstream landmines the session-start entry creates:**
   - **Span / time-in-mode computation** (`session.py`, the `spans.append((first.from_mode, ...))` logic): with session-start logged, `first.from_mode == "session-start"` — so the opening span would be attributed to a pseudo-mode instead of the real starting mode (`explore`). Use the session-start entry's `to_mode` as the first span's mode, or skip session-start entries in span computation. **Add a test asserting time-in-mode attributes the opening span to the real mode, not "session-start".**
   - **Formatter** (`formatters.py`, renders `{from_mode} > {to_mode}`): decide how a `session-start` row displays (e.g. `· session start → explore`, or suppress the `from` side) rather than the literal `session-start > explore`. Add/adjust a formatter test.

5. **Verify external consumers** (statusline, Ghostty watcher — likely in `EarthianLabs/.claude/`, outside this repo) tolerate a `from_mode` of `session-start` without rendering it as a real mode. Grep for them; if they parse mode-history, confirm or patch. If out of reach this session, note as residue.

## Scope — out

- Orchestration presets (committed `b2de0b7`).
- Any new harness features or mode changes.
- Refactoring `_log_transition` beyond what isolation + the span fix require.

## Acceptance criteria

- [ ] Full `pytest` suite green.
- [ ] **Isolation proof:** line count of `~/.vibe-harness/mode-history.jsonl` is unchanged by a complete test run (capture before/after; assert in a test or document the manual check).
- [ ] Constructing a `VibeSession()` writes exactly one `session-start` line (to the isolated path under test; to the real path in production).
- [ ] Time-in-mode / spans attribute the opening span to the real starting mode, not `session-start` — covered by a test.
- [ ] `vibe_history` / formatter output renders the session-start row per the chosen display decision — covered by a test.
- [ ] `session.py` + `test_session.py` + new `conftest.py` (+ any formatter edit) committed together as one change.

## Test plan (tests-first)

1. Write `conftest.py` isolation fixture first; confirm existing suite still green against the isolated path.
2. Write the failing tests for: session-start logged on construction; opening-span attribution; formatter rendering of session-start.
3. Implement: env-resolved path, `__post_init__` logging (already drafted), span fix, formatter handling.
4. Green, then the isolation-proof check.

## Risks / notes

- **Import surface:** `HISTORY_FILE` is imported in at least `test_session.py`; changing its nature ripples. Audit before refactoring.
- **Env-at-import vs env-at-call:** if the path is resolved once at import, the conftest must set the env *before* `session` is imported, or monkeypatch the resolved value. A per-call resolver (`config.history_file()`) avoids the import-order trap — prefer it.
- **`session-start` as sentinel:** it's a pseudo-mode in the `from_mode` slot. Anything that enumerates or validates modes must not treat it as a real mode (check `validate_mode` call sites and any mode-count/aggregation logic, not just spans + formatter).
- This is the disentanglement half of the 2026-05-25 think-with; the cooling-thread framing and why it sat 7 weeks is in that session's trace.
