# beaconctl — LCUS-4 relay control for 3-colour beacon lamp

Controls a 12 V 3-colour beacon lamp (red / yellow / green + buzzer) via an
LCUS-4 CH340 USB serial relay board.

---

## Wiring assumptions

The beacon is **common anode** (common positive): the black wire is +12 V and
each colour wire goes low (to GND) to illuminate. The relays switch the
**negative/ground side** of each load.

```
PSU (+12 V) ──────────────────────────── Beacon black (common +)

Beacon red    ── NO1 ── COM1 ──┐
Beacon yellow ── NO2 ── COM2 ──┤
Beacon green  ── NO3 ── COM3 ──┴── PSU (−12 V / GND)
Beacon buzzer ── NO4 ── COM4 ──┘
```

- Relay ON  = colour wire pulled to GND → load illuminates.
- Relay OFF = colour wire floating → load off.

| Channel | Default name | Beacon wire |
|---------|-------------|-------------|
| 1       | red         | Red light   |
| 2       | yellow      | Yellow light|
| 3       | green       | Green light |
| 4       | buzzer      | Grey/buzzer |

Channel mapping lives in `config/channels.json` — never hardcoded.

---

## Requirements

- Python 3.11+ (`python --version`)
- pyserial (`pip install pyserial`) — for beaconctl.py relay control
- pywin32 (`pip install pywin32`) — for status engine Outlook inbox polling (Windows only)
- LCUS-4 board connected via USB (CH340 driver installed)

Or install from repo root: `pip install -r requirements.txt`

---

## Quick start

```bat
:: Find the COM port in Device Manager, e.g. COM5

:: Turn red on (exclusive: turns yellow+green+buzzer off first)
python beaconctl.py --port COM5 --ch 1 --on

:: Turn yellow on (leave others as-is)
python beaconctl.py --port COM5 --ch 2 --on --nonexclusive

:: Turn green on
python beaconctl.py --port COM5 --ch 3 --on

:: Pulse buzzer for 750 ms
python beaconctl.py --port COM5 --ch 4 --pulse 750

:: Turn channel 1 off
python beaconctl.py --port COM5 --ch 1 --off

:: Turn everything off
python beaconctl.py --port COM5 --alloff
```

---

## Options

| Flag | Description |
|------|-------------|
| `--port COMx` | COM port. Overrides `config/channels.json`. |
| `--ch N` | Channel 1–4 |
| `--on` | Turn channel on |
| `--off` | Turn channel off |
| `--alloff` | Turn all channels off |
| `--pulse MS` | Pulse on for N ms, then off |
| `--exclusive` | (default) Turn off others before turning one on |
| `--nonexclusive` | Allow multiple channels on simultaneously |
| `--protocol lcus_a\|lcus_b` | Try `lcus_b` if relay doesn't click on default |
| `--dry-run` | Print bytes without opening the port |
| `--log-file PATH` | Append timestamped log to file |
| `--config PATH` | Custom path to channels.json |

---

## Protocol

**LCUS-A (default):** 4-byte command `A0 CH STATE (A0+CH+STATE)&0xFF`

```
CH1 ON:  A0 01 01 A2
CH1 OFF: A0 01 00 A1
CH2 ON:  A0 02 01 A3
CH3 ON:  A0 03 01 A4
CH4 ON:  A0 04 01 A5
```

**LCUS-B (alternate clone):** Same header, XOR checksum `A0 CH STATE (A0^CH^STATE)&0xFF`

If the relay board doesn't respond, try `--protocol lcus_b`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `COM port not found` | Check Device Manager; board may need CH340 driver |
| `access denied` | Another app (Cursor serial monitor, etc.) has the port open |
| Board receives bytes but relay doesn't click | Try `--protocol lcus_b` |
| Relay clicks but wrong load energises | Check wiring; update channel mapping in `config/channels.json` |

---

## Status engine (Phase 2 & 3)

A separate process that periodically decides a beacon state and calls `beaconctl.py`.

**With Outlook (Phase 3):** If `config/channels.json` has an `outlook` section and pywin32 is installed, the engine polls the configured folder (default Inbox or shared mailbox), computes state from oldest unread age (warn > 60 min, critical > 120 min), applies hysteresis and escalation, then sets the beacon.

```bat
python status_engine.py
python status_engine.py --config path/to/channels.json
python status_engine.py --no-outlook        # stub only (no Outlook)
python status_engine.py --state warn --once   # override state for testing
```
PowerShell env override: `$env:BEACON_STATE='warn'; python status_engine.py --once`

**Config:** `statusEngine.pollIntervalMinutes`, `warningThresholdMinutes`, `criticalThresholdMinutes`, `hysteresisPolls`, `escalationPolls`; `outlook.folderSource` (`default_inbox` or shared store), `outlook.storeDisplayName`, `outlook.folderPath`. See `docs/outlook-integration.md` for folder targeting and target-machine checklist.

**Scheduled task (Windows):** Run the status engine every N minutes with “Run only when user is logged on” so Outlook is running. Example: Task Scheduler → Create Task → Trigger every 3 min → Action `python C:\path\to\status_engine.py` (or a .bat that does the same).

---

## C# build

The `src/` directory contains a .NET 10 C# implementation (BeaconCtl.Cli, BeaconCtl.Core).
Requires the .NET 10 SDK: https://dot.net/download

```bat
dotnet build beaconctl.sln
dotnet run --project src/BeaconCtl.Cli -- --port COM5 --ch 1 --on
```

The C# CLI supports **low-level relay control only**: `--ch`, `--on`/`--off`, `--alloff`, `--pulse`, `--port`, `--protocol`, `--dry-run`, etc. It does **not** yet support `--state` or `--pattern`; use `beaconctl.py` for named states and buzzer patterns (and for the status engine).
