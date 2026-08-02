# ISSUE-001 — Idle detection is blind between tool calls, so the step-away nudge fires on unmeasured time

**Filed:** 2026-08-01 · `m3air`, Tulsa
**Severity:** High — the instrument reports a confident number it did not measure, and acts on it
**Affects:** `v0.5.0`+ · introduced with `646d093 feat(governor): step-away nudge fires on continuous stretch, not cumulative active`
**Status:** Open. Fix deliberately not designed here — see *Scope* below.

## Observed

At the close of a session on 2026-08-01, `vibe_check` returned:

```
  mode      1871min
  session   1871min active
  stretch   1871min unbroken
  actions   1
  switches  0
  nudges    1

Nudge: You've been going 1871 minutes without a real break. How does your
body feel? This might be a good time to step away and move.
```

**Every one of those numbers is wrong, and the nudge is false.**

1871 minutes is 31 hours. The session had been open since 2026-07-31 13:47 and was punctuated by, at minimum: an **18h 25m** gap between turns, a **6h 41m** gap, and a **3h 27m** gap — all three independently recorded by the `chronos` session hook, which printed *"last turn 18h 25m ago"* at the time. In that window Mat slept, drove to two print shops, and went to Office Depot.

`actions 1` is the tell. One recorded interaction across a session with dozens of exchanges.

## Root cause — verified, not inferred

The chain, confirmed by reading the call sites:

1. Idle gaps are appended **only** inside `Session.record_interaction()` (`session.py:125–139`).
2. `record_interaction()` is called from **exactly six places, all of them MCP tool handlers** in `server.py` (lines 75, 89, 109, 126, 139, 183). There is no other caller.
3. This session invoked one vibe tool, once, at the very end. So `interaction_count == 1`.
4. On that single call `last_interaction_at` was still `None`, so the gap-detection branch never executed. `_idle_gaps` stayed **empty**.
5. `continuous_active_minutes()` (`session.py:308–326`) walks `_idle_gaps` to find the stretch start. With no gaps, `stretch_start = self.started_at` — so the stretch is simply *session age*.
6. `governor.py:112` fires `session_duration` on that value. Nudge.

**The instrument can only perceive elapsed time at the instants it is being called.** A human who works 31 hours without pause and a human who works twenty minutes, sleeps eight hours, and drives across Tulsa are **indistinguishable** to it — provided neither calls a vibe tool in between.

`activity.idle_threshold_minutes` (default 30) is not the problem and lowering it will not help. The threshold is correct; it is simply never evaluated.

## Why this matters more than an off-by-some

The 646d093 commit message and the `continuous_active_minutes()` docstring both state the design intent precisely:

> *"A session open for hours but punctuated by real breaks has a short continuous stretch and should not be nudged to rest."*

**That is exactly the case that occurred, and the instrument did the opposite.** The feature's own stated failure mode is the one it now produces.

The cost is not a wrong number — it is the credibility of the signal. A nudge that fires after a full night's sleep teaches the body to ignore nudges, which is the one thing this instrument exists to prevent. **A false nudge is worse than no nudge.** See `feedback_nudge_from_instrument_not_wallclock`.

**The deeper shape: the harness is measuring its own usage and reporting it as the human's state.** That is a coupling failure, not an accuracy bug. It belongs to a family this ecosystem keeps finding — `infra-health.sh` reporting a calm `IDLE` for servers whose binaries did not exist; a `git fetch` against an unauthenticated remote reporting "up to date" for a remote it never reached; a PDF MediaBox certifying a page size while the content inside was scaled to 71%. **In every case an instrument produced confidence about something it never actually examined.**

## Notes toward a fix — directions only, not a design

Deliberately not resolved here. Recorded so the thinking is not lost.

- **The signal already exists elsewhere in the same harness.** The `chronos` session hook computes and prints *"last turn 18h 25m ago"* on re-anchor. One instrument in this harness holds precisely the datum the other lacks. That coupling is probably the whole fix.
- **Make activity turn-driven rather than tool-driven** — a `UserPromptSubmit` hook pinging the session would make `record_interaction()` fire once per turn regardless of whether a vibe tool is called.
- **Passive clock** — the conversation JSONL is append-only; its mtime is a free, always-current activity timestamp requiring no cooperation from the model.
- **Fail closed.** Independent of which signal is adopted: **if `interaction_count` is low relative to session age, the stretch is unmeasured and must not be reported as long.** Suppress the nudge and say the stretch is unknown. Applied here, one action across 31 hours would have silenced it. *No state may read as actionable unless it was actually measured.*

## Scope

Mat's framing when filing: **accuracy, fidelity, and coupling performance of the vibe harness**, to be worked when back from Tulsa (after 2026-08-05). This issue covers the accuracy limb. Fidelity and coupling are broader and likely want their own treatment — `actions 1` and `switches 0` suggest the harness has a thin picture of the session generally, not only of its gaps.

Per the USDD gate, the fix wants a SPEC and a failing test before implementation. **The test to write first: a session with a recorded gap longer than the idle threshold must report a short stretch and must not fire `session_duration`** — and it must hold when the gap is observed by something other than a vibe tool call.

## Reproduce

1. Start a session.
2. Call any vibe tool once.
3. Wait longer than `activity.idle_threshold_minutes` — genuinely away, no vibe tools.
4. Call `vibe_check`.

**Expected:** stretch resets to roughly zero; no step-away nudge.
**Actual:** stretch equals full session age; nudge fires.
