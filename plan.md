Phase 0 - assumptions and constraints

## Hardware and wiring (3-color beacon + buzzer)

**Device:** Windows PC + LCUS-4 (CH340 USB-serial relay board) + 12 V beacon lamp. PC talks to the relay board over a COM port. USB powers the board logic only; an external DC supply powers the beacon and buzzer.

**Beacon lamp:** One unit with four controllable loads — red light, yellow light, green light, buzzer — and one common positive (black). Five wires: red, yellow, green, grey (buzzer), black (common). **Common anode wiring: black wire is +12 V; each colour wire goes low to illuminate.**

**Actual colours:** deep red, orange/amber, deep green.

**Wiring model (common anode — relays switch the GND side):**

- PSU positive → beacon black (common +).
- Relay NO terminals → colour wires (negative side of each load): NO1 → red, NO2 → yellow, NO3 → green, NO4 → buzzer.
- Relay COM terminals → PSU negative (GND).

**Relay logic:** Relay ON = colour wire pulled to GND (load illuminates). Relay OFF = colour wire floating (load off).

**Channel mapping (configurable in config/channels.json; never hardcode in app):**

| Channel | Default logical name | Beacon connection |
|---------|----------------------|--------------------|
| 1       | red                  | Red light          |
| 2       | yellow               | Yellow light       |
| 3       | green                | Green light        |
| 4       | buzzer               | Buzzer             |

**Goal:** First get deterministic command control working (CLI switches). Then add "email inbox stale unread" status logic that drives the same relay commands.

**Hardware rework (planned):** Replace LCUS-4 with Blue Pill + 4× low-side MOSFETs for PWM control (fades, on-device patterns, buzzer modulation). Wiring and software impact are in **`docs/hardware-rework-bluepill.md`**. Status engine and states stay the same; beaconctl gains a Blue Pill backend and new serial protocol.

---

Phase 1 - CLI relay control (prove the pipe) — COMPLETE

**Implementation:** `beaconctl.py` (Python 3.11 + pyserial). C# project scaffold also written in `src/` and ready to compile with .NET 10 SDK.

**COM port:** COM6 (set in config/channels.json)

### Command-line interface

Low-level channel control:

```
beaconctl --ch 1|2|3|4 --on
beaconctl --ch 1|2|3|4 --off
beaconctl --ch 1|2|3|4 --pulse <ms>
beaconctl --alloff
```

Named state control (preferred for status engine):

```
beaconctl --state ok
beaconctl --state warn
beaconctl --state critical
beaconctl --state escalated
beaconctl --state fault
beaconctl --state off
beaconctl --state warn --no-buzzer    (suppress buzzer, e.g. repeat polls)
```

Buzzer pattern only (lights untouched):

```
beaconctl --pattern warn
beaconctl --pattern alert
beaconctl --pattern critical
```

All flags:

```
--port COMx          Override COM port
--protocol lcus_a|lcus_b   Swap if relay doesn't click
--exclusive          Turn off others before turning one on (default)
--nonexclusive       Allow multiple channels on simultaneously
--dry-run            Print bytes without opening port
--log-file PATH      Append timestamped log to file
--config PATH        Override path to channels.json
```

### Named states (config/channels.json "states")

| State     | Lights            | Buzzer on entry | When to use                          |
|-----------|-------------------|-----------------|--------------------------------------|
| off       | none              | none            | No mail / system idle                |
| ok        | green             | none            | Inbox current                        |
| warn      | yellow            | warn (1 beep)   | Unread > 60 min                      |
| critical  | red               | alert (3 beeps) | Unread > 120 min                     |
| escalated | red + yellow      | none            | Red for a long time and still growing|
| fault     | red+yellow+green  | alert (3 beeps) | Status engine error / unknown state  |

### Buzzer patterns (config/channels.json "patterns")

| Pattern  | Sequence                       | Sound           |
|----------|--------------------------------|-----------------|
| warn     | 200ms on, 300ms off            | 1 short beep    |
| alert    | 3x (150ms on, 150ms off)       | 3 beeps         |
| critical | 5x (100ms on, 100ms off)       | 5 rapid beeps   |

Relay mechanics limit minimum reliable pulse to ~100 ms. Patterns are defined
as `[[on_ms, off_ms], ...]` lists in config — add or modify without touching code.

**Buzzer note:** Active buzzer is very loud. Use patterns/duty-cycle rather than
continuous ON. Physical tape over the port is also effective (-6 to -10 dB).

### Colour combination rationale

- Red + yellow (escalated): two lenses lit = unmissable; reads as "beyond red" visually
- All three (fault): distinct from all normal states, immediately obvious as "something is wrong with the tool"
- Red + green is avoided (muddy colour, no intuitive meaning)

### Protocol

LCUS-A (default): `A0 CH STATE (A0+CH+STATE)&0xFF`
LCUS-B (alternate clone): `A0 CH STATE (A0^CH^STATE)&0xFF`
Try `--protocol lcus_b` if the relay doesn't respond.

### Deliverable (done)

- `beaconctl.py` reliably controls each relay and plays buzzer patterns
- `config/channels.json` holds all channel mapping, states, and patterns
- `README.md` with wiring diagram and example commands
- C# project in `src/` compiles with .NET 10 SDK

---

Phase 2 - thin "status engine" that calls the same command layer

Keep layers strictly separated:

- **relay driver** — sends relay commands (beaconctl.py / BeaconCtl.Core)
- **command interface** — parses CLI, calls relay driver
- **status engine** — decides desired beacon state, shells out to beaconctl

The status engine calls `beaconctl --state <name>` or `beaconctl --state <name> --no-buzzer`
depending on whether this is a state transition or a steady-state repeat poll.

---

Phase 3 - email inbox status integration

**Target:** O365 mailbox, Outlook desktop installed and running.

**Objective:** Turn beacon on if any unread email is older than threshold.

### State machine

| Condition                              | State     | Transition buzzer |
|----------------------------------------|-----------|-------------------|
| No stale unread                        | ok        | none              |
| Unread > 60 min                        | warn      | warn (on entry)   |
| Unread > 120 min                       | critical  | alert (on entry)  |
| Critical for N+ consecutive polls      | escalated | none              |
| Status engine exception / unknown      | fault     | alert (on entry)  |

- **Hysteresis:** condition must hold for 2 consecutive polls before state change
- **Buzzer:** fires only on state *transition*, not on repeat polls
- **Escalation:** `escalated` triggers after `critical` persists for N polls (configurable)
- **Poll interval:** 2–5 minutes (configurable)

### Implementation approach

**Option A: Outlook COM via pywin32 (preferred — Outlook is installed)**
- `win32com.client` dispatches to `Outlook.Application`
- Query folder items: filter unread, check `ReceivedTime` vs cutoff
- No credentials needed; uses running Outlook profile
- Runs as scheduled task every N minutes (user must be logged on so Outlook is running)
- **Dev vs target:** See `docs/outlook-integration.md` for Windows 10 vs 11, targeting specific folders, shared inboxes, and a target-machine checklist.

**Option B: IMAP polling**
- App password / OAuth
- Search UNSEEN, fetch headers/date, compare timestamps
- Works without Outlook installed

**Option C: Microsoft Graph REST API**
- App registration, OAuth token, Graph query for unread + `receivedDateTime`
- Most correct for M365 but more setup overhead

### Deliverable for Phase 3

- `status_engine.py` (or separate process) that computes state and calls `beaconctl --state`
- All thresholds, poll interval, channel mapping, and COM port in `config/channels.json`
- Instructions for running as a Windows scheduled task or startup script
