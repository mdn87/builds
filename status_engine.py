#!/usr/bin/env python3
"""
status_engine.py — Status engine: poll inbox (Outlook COM) and set beacon state.

Polls on an interval; computes state from oldest unread email age (Phase 3) or
stub (--state override / BEACON_STATE). Shells out to beaconctl.py --state <name>.
Uses --no-buzzer on repeat polls; buzzer on state transitions.

Usage:
  python status_engine.py                    # Outlook inbox (if config has outlook)
  python status_engine.py --no-outlook       # Stub only (ok)
  python status_engine.py --state warn --once   # Override state for testing
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

try:
    from outlook_inbox import get_oldest_unread_minutes
    _OUTLOOK_AVAILABLE = True
except ImportError:
    _OUTLOOK_AVAILABLE = False

# ---------------------------------------------------------------------------
# Config and paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
BEACONCTL_PY = SCRIPT_DIR / "beaconctl.py"

VALID_STATES = frozenset({"off", "ok", "warn", "critical", "escalated", "fault"})


def find_config(config_path: str | None) -> Path | None:
    if config_path and Path(config_path).exists():
        return Path(config_path)
    cwd = Path.cwd() / "config" / "channels.json"
    if cwd.exists():
        return cwd
    for parent in [SCRIPT_DIR, SCRIPT_DIR.parent]:
        candidate = parent / "config" / "channels.json"
        if candidate.exists():
            return candidate
    return None


def load_config(config_path: Path | None) -> dict:
    if config_path is None:
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def get_poll_interval_minutes(config: dict) -> float:
    try:
        n = config.get("statusEngine", {}).get("pollIntervalMinutes", 3)
        return max(0.25, float(n))
    except (TypeError, ValueError):
        return 3.0


def _get_thresholds(config: dict) -> tuple[float, float, int, int]:
    se = config.get("statusEngine") or {}
    warn = float(se.get("warningThresholdMinutes", 60))
    critical = float(se.get("criticalThresholdMinutes", 120))
    hysteresis = max(1, int(se.get("hysteresisPolls", 2)))
    escalation = max(1, int(se.get("escalationPolls", 3)))
    return warn, critical, hysteresis, escalation


def compute_stub_state(override: str | None = None) -> str:
    """Stub: return state from override or env. Used when --state set or --no-outlook."""
    raw = (override or os.environ.get("BEACON_STATE", "ok")).strip().lower()
    return raw if raw in VALID_STATES else "ok"


# ---------------------------------------------------------------------------
# Phase 3: Outlook inbox → state with hysteresis and escalation
# ---------------------------------------------------------------------------

def _raw_state_from_inbox(oldest_min: float | None, warn_min: float, critical_min: float) -> str:
    """Map oldest unread minutes to raw state (ok, warn, critical)."""
    if oldest_min is None:
        return "ok"
    if oldest_min >= critical_min:
        return "critical"
    if oldest_min >= warn_min:
        return "warn"
    return "ok"


def compute_state_from_inbox(
    config: dict,
    log: logging.Logger,
    raw_history: deque[str],
    consecutive_critical: int,
    previous_displayed_state: str | None,
) -> tuple[str, str, deque[str], int]:
    """
    Poll Outlook folder; apply hysteresis and escalation.
    Returns (state, detail_message, new_raw_history, new_consecutive_critical).
    Only transition when new raw has been stable for hysteresis_polls.
    """
    warn_min, critical_min, hysteresis_polls, escalation_polls = _get_thresholds(config)
    previous_raw = {"ok": "ok", "warn": "warn", "critical": "critical", "escalated": "critical"}.get(
        previous_displayed_state or "", "ok"
    )
    if previous_displayed_state == "fault":
        previous_raw = "ok"

    try:
        result = get_oldest_unread_minutes(config)
    except Exception as e:
        log.exception("Outlook poll failed: %s", e)
        return ("fault", str(e), deque(maxlen=hysteresis_polls), 0)

    raw = _raw_state_from_inbox(
        result.oldest_unread_minutes, warn_min, critical_min
    )
    raw_history.append(raw)
    while len(raw_history) > hysteresis_polls:
        raw_history.popleft()

    # Hysteresis: only transition when same raw for last N polls
    if len(raw_history) >= hysteresis_polls and all(r == raw for r in raw_history):
        effective_raw = raw
    else:
        effective_raw = previous_raw if previous_displayed_state else raw

    # Escalation: after critical for escalation_polls, show escalated
    if effective_raw == "critical":
        consecutive_critical += 1
        if consecutive_critical >= escalation_polls:
            state = "escalated"
            detail = f"critical {consecutive_critical} polls, oldest unread {result.oldest_unread_minutes:.0f} min"
        else:
            state = "critical"
            detail = f"oldest unread {result.oldest_unread_minutes:.0f} min ({result.unread_count} unread)"
    else:
        consecutive_critical = 0
        state = effective_raw
        if result.unread_count == 0:
            detail = "0 unread"
        else:
            detail = f"oldest {result.oldest_unread_minutes:.0f} min ({result.unread_count} unread)"

    return (state, detail, raw_history, consecutive_critical)


# ---------------------------------------------------------------------------
# Shell out to beaconctl
# ---------------------------------------------------------------------------

def run_beaconctl(
    state_name: str,
    config_path: Path | None,
    no_buzzer: bool,
    log: logging.Logger,
) -> bool:
    cmd = [sys.executable, str(BEACONCTL_PY), "--state", state_name]
    if no_buzzer:
        cmd.append("--no-buzzer")
    if config_path is not None:
        cmd.extend(["--config", str(config_path)])

    log.debug("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.warning("beaconctl exited %d: %s", result.returncode, result.stderr or result.stdout)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("beaconctl timed out")
        return False
    except FileNotFoundError:
        log.error("beaconctl.py not found at %s", BEACONCTL_PY)
        return False
    except Exception as e:
        log.exception("Failed to run beaconctl: %s", e)
        return False


def run_beaconctl_off(config_path: Path | None, log: logging.Logger) -> None:
    """On shutdown: set beacon to off."""
    run_beaconctl("off", config_path, no_buzzer=True, log=log)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Status engine: poll and set beacon state via beaconctl.py",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to channels.json (default: auto-detect config/channels.json)",
    )
    parser.add_argument(
        "--state",
        metavar="NAME",
        choices=list(VALID_STATES),
        help="Override stub state for testing (ok, warn, critical, escalated, fault, off)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one poll and exit (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be done without calling beaconctl",
    )
    parser.add_argument(
        "--no-outlook",
        action="store_true",
        help="Disable Outlook inbox polling; use stub state (ok or BEACON_STATE)",
    )
    args = parser.parse_args()

    config_path = find_config(args.config)
    config = load_config(config_path)
    poll_min = get_poll_interval_minutes(config)
    poll_sec = poll_min * 60.0
    _, _, hysteresis_polls, _ = _get_thresholds(config)

    use_outlook = (
        not args.state
        and not args.no_outlook
        and _OUTLOOK_AVAILABLE
        and bool(config.get("outlook"))
    )

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    log = logging.getLogger("status_engine")

    if not BEACONCTL_PY.exists():
        log.error("beaconctl.py not found at %s", BEACONCTL_PY)
        return 1

    if config_path:
        log.info("Config: %s", config_path)
    else:
        log.warning("No config/channels.json found; using defaults")

    if use_outlook:
        log.info("Poll interval: %.1f min (Outlook inbox)", poll_min)
    else:
        if config.get("outlook") and not _OUTLOOK_AVAILABLE:
            log.warning("Config has outlook but pywin32/Outlook unavailable; using stub. pip install pywin32")
        log.info(
            "Poll interval: %.1f min (stub; use --state or BEACON_STATE to override)",
            poll_min,
        )

    previous_state: str | None = None
    raw_history: deque[str] = deque(maxlen=hysteresis_polls)
    consecutive_critical = 0
    shutdown = False

    def on_signal(_sig, _frame):  # noqa: ARG001
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)

    try:
        while not shutdown:
            if use_outlook:
                state, detail, raw_history, consecutive_critical = compute_state_from_inbox(
                    config, log, raw_history, consecutive_critical, previous_state
                )
                log.debug("inbox: %s", detail)
            else:
                state = compute_stub_state(override=args.state)
                detail = ""

            is_repeat_same_state = previous_state is not None and state == previous_state
            no_buzzer = is_repeat_same_state

            if args.dry_run:
                log.info("[dry-run] state=%s no_buzzer=%s %s", state, no_buzzer, detail)
            else:
                ok = run_beaconctl(state, config_path, no_buzzer=no_buzzer, log=log)
                if ok:
                    log.info("state=%s (transition=%s) %s", state, not is_repeat_same_state, detail)
                    previous_state = state
                else:
                    log.warning("beaconctl failed; will retry next poll")

            if args.once:
                break

            deadline = time.monotonic() + poll_sec
            while time.monotonic() < deadline and not shutdown:
                time.sleep(0.5)

    finally:
        if not args.dry_run and not args.once:
            log.info("Shutting down; setting beacon off")
            run_beaconctl_off(config_path, log)

    return 0


if __name__ == "__main__":
    sys.exit(main())
