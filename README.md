# beaconctl — LCUS-4 relay control for 3-colour beacon lamp

Controls a 12 V 3-colour beacon lamp (red / yellow / green + buzzer) via an
LCUS-4 CH340 USB serial relay board.

---

## Wiring assumptions

```
PSU (+12 V) ──┬── COM1 ── NO1 ── Red light ──┐
              ├── COM2 ── NO2 ── Yellow light ─┤
              ├── COM3 ── NO3 ── Green light ──┤  → Beacon black (common)
              └── COM4 ── NO4 ── Buzzer ───────┘     ↓
                                                PSU (−12 V / GND)
```

- Relay ON  = load gets +12 V (circuit complete).
- Relay OFF = load open circuit (no power).

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
- pyserial (`pip install pyserial`)
- LCUS-4 board connected via USB (CH340 driver installed)

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

## C# build (future)

The `src/` directory contains a .NET 8 C# implementation (BeaconCtl.Cli, BeaconCtl.Core).
Requires the .NET 8 SDK: https://dot.net/download

```bat
dotnet build beaconctl.sln
dotnet run --project src/BeaconCtl.Cli -- --port COM5 --ch 1 --on
```

The Python script and C# project are functionally equivalent for Phase 1.
