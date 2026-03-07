---
last_updated: 2026-03-06T23:00:00-05:00
session_summary: Phase 3 Outlook inbox done; Blue Pill rework doc locked in (ASCII protocol, USB CDC, patterns in firmware).
---

# Session Handoff

## What Was Done
- Phase 3: Outlook COM inbox polling in `outlook_inbox.py`; `status_engine.py` computes state from oldest unread (hysteresis + escalation), shells out to beaconctl. Config: `outlook` section, `statusEngine.escalationPolls`; `--no-outlook` / `--state` for stub. README + requirements.txt (pywin32).
- Status engine: `--state NAME` and `--once` for testing without env vars (PowerShell-friendly).
- Hardware rework: `docs/hardware-rework-bluepill.md` — Blue Pill + 4× MOSFETs, wiring, **ASCII line protocol** (SET R/Y/G/B, PATTERN IDLE/WARNING/CRITICAL/OFF, BEEP, ALL OFF), patterns in firmware, USB CDC, state mapping. One stale table row in that doc (States/patterns) could be cleaned up next session.

## Current State
- Phase 1–3 done: beaconctl.py (LCUS), status_engine.py (Outlook or stub), outlook_inbox.py (pywin32), config has outlook + statusEngine.
- Plan: `plan.md` points to Blue Pill rework in `docs/hardware-rework-bluepill.md`.

## Next Up
- **Blue Pill path:** Implement firmware (USB CDC, line parser, PWM, pattern state machine); add beaconctl `--backend bluepill` that sends `PATTERN WARNING` etc. Config `backend`, `comPort`.
- Optional: Fix remaining “States / patterns” row in `docs/hardware-rework-bluepill.md` (curly quotes / wording).

## Gotchas
- Outlook COM: Outlook must be running; task “Run only when user is logged on.” See `docs/outlook-integration.md`.
- Blue Pill: One USB cable (CDC); PC sends high-level commands only; timing lives in firmware.
