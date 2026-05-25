"""Shared test fixtures for the Vibe Harness suite.

The history file (`~/.vibe-harness/mode-history.jsonl`) is live production
state — read by the statusline, the Ghostty watcher, and `vibe_history`.
Constructing a `VibeSession()` writes a `session-start` line to it, so any
test that instantiates a session would otherwise mutate that live file.

This autouse fixture redirects the history directory to a per-test temp dir
via the `VIBE_HARNESS_HISTORY_DIR` env override (resolved per call in
`config.history_dir()`), so the whole suite is fully isolated from real state.
"""

import os
import tempfile

import pytest

# Set the override at conftest import time — BEFORE any test module imports
# vibe_harness_mcp.server, which constructs a VibeSession() at module level and
# would otherwise write a session-start line to the live history file during
# collection (before the function-scoped fixture below can run).
_COLLECTION_HISTORY_DIR = tempfile.mkdtemp(prefix="vibe-harness-test-collection-")
os.environ["VIBE_HARNESS_HISTORY_DIR"] = _COLLECTION_HISTORY_DIR


@pytest.fixture(autouse=True)
def isolate_history_dir(tmp_path, monkeypatch):
    """Point the mode-history directory at a fresh temp dir for every test."""
    monkeypatch.setenv("VIBE_HARNESS_HISTORY_DIR", str(tmp_path))
    yield tmp_path
