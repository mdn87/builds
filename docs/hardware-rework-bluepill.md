# Hardware rework: LCUS-4 → Blue Pill + 4× low-side MOSFETs

Plan to replace the USB relay board with a Blue Pill (STM32F103) driving four low-side MOSFET modules via PWM. Same beacon tower (common +12 V); control gains PWM (fades, dimming, buzzer modulation) and on-device patterns.

---

## 1. Why rework

- **PWM:** Fade LEDs, blink patterns, modulate buzzer loudness instead of hard on/off.
- **Patterns on device:** Blue Pill can run warn/alert/critical patterns in firmware (≈30 lines with a clean structure); PC sends “play pattern X” instead of many “on/off/pulse” commands.
- **No relay board:** Simpler parts (4× MOSFET modules + Blue Pill), same COM-port-from-PC paradigm.

---

## 2. New hardware

| Item | Role |
|------|------|
| **12 V supply** | Powers beacon and MOSFET load side; GND common with Blue Pill. |
| **Beacon tower** | Unchanged: black = +12 V common; red / yellow / green / grey = one wire per load (low side switched). |
| **4× low-side MOSFET modules** | Each has DC+/DC- (logic power), OUT+/OUT- (load switch). Logic input: PWM+ (and GND). Module switches OUT- to GND when driven. |
| **Blue Pill (STM32F103)** | USB (or UART) to PC; 4× PWM outputs (e.g. PA0–PA3) to MOSFET PWM+ inputs. GND tied to 12 V supply GND. |

**Wiring (per channel):**

- **Power (12 V):**  
  - 12 V+ → tower black  
  - 12 V+ → each MOSFET **OUT+**  
  - 12 V- → each MOSFET **DC-** (and Blue Pill GND)

- **Load (one MOSFET per channel):**  
  - Tower colour wire → MOSFET **OUT-**  
  - MOSFET closes path to GND when driven → load on (same as current “relay ON”).

- **Control (Blue Pill → MOSFETs):**  
  - PA0 → red MOSFET PWM+  
  - PA1 → yellow MOSFET PWM+  
  - PA2 → green MOSFET PWM+  
  - PA3 → buzzer MOSFET PWM+  
  - Blue Pill GND → module GND (and 12 V-).

**Summary:**

```
12 V+
 ├── tower black
 ├── MOSFET1 OUT+
 ├── MOSFET2 OUT+
 ├── MOSFET3 OUT+
 └── MOSFET4 OUT+

12 V-
 ├── MOSFET1 DC-
 ├── MOSFET2 DC-
 ├── MOSFET3 DC-
 ├── MOSFET4 DC-
 └── Blue Pill GND

Blue Pill
 ├── PA0 → red   MOSFET PWM+
 ├── PA1 → yellow MOSFET PWM+
 ├── PA2 → green  MOSFET PWM+
 └── PA3 → buzzer MOSFET PWM+
```

**Critical:** Blue Pill GND must be common with the 12 V supply GND.

---

## 3. Control path and who does what

- **PC** decides **system state** (idle / warning / critical) from email/status; it only sends high-level commands.
- **Blue Pill** handles all timing: LED PWM, fades, blink rates, buzzer modulation. Patterns run in firmware so the PC does not deal with timing jitter or USB latency.
- **Transport:** One USB cable. Blue Pill appears as a **USB CDC** serial port (e.g. COM7). No USB–TTL adapter.

Result: status_engine (or beaconctl) sends e.g. `PATTERN WARNING\n`; the tower runs the pattern autonomously.

---

## 4. Protocol (ASCII, line-based)

**Format:** `CMD ARG ARG...\n` — simple ASCII, one command per line. Easy to debug from a serial terminal.

**Transport:** Serial over COM (USB CDC or UART). Baud rate TBD (e.g. 115200 8N1).

### Commands

| Command | Meaning |
|---------|--------|
| `SET R <duty>` | Red channel PWM, duty 0–100 (%) |
| `SET Y <duty>` | Yellow channel |
| `SET G <duty>` | Green channel |
| `SET B <duty>` | Buzzer channel |
| `PATTERN IDLE` | Firmware runs idle pattern (e.g. green breathe, others off) |
| `PATTERN WARNING` | Firmware runs warning pattern (e.g. yellow blink, buzzer chirp) |
| `PATTERN CRITICAL` | Firmware runs critical pattern (e.g. red flash, buzzer pulsed) |
| `PATTERN OFF` | All channels off, no pattern |
| `BEEP <duty> <duration_ms>` | One-shot buzzer, e.g. `BEEP 70 300` |
| `ALL OFF` | All channels duty 0 immediately |

**Channel letters:** R = red, Y = yellow, G = green, B = buzzer.

**Examples:**

```
SET R 100
SET Y 0
SET G 40
PATTERN WARNING
BEEP 40 200
ALL OFF
```

### Pattern semantics (firmware-defined)

Firmware interprets pattern names locally. Example mapping (exact behavior is firmware choice):

| Pattern | Example behavior |
|---------|------------------|
| IDLE | Green breathe; red/yellow/buzzer off |
| WARNING | Yellow blink ~2 Hz; buzzer short chirp every ~3 s |
| CRITICAL | Red flash ~4 Hz; buzzer ~70% duty pulsed |
| OFF | All off |

Status engine states (ok / warn / critical / escalated / fault / off) map to these: e.g. ok→`PATTERN IDLE`, warn→`PATTERN WARNING`, critical/escalated/fault→`PATTERN CRITICAL` (or firmware can add ESCALATED/FAULT variants), off→`PATTERN OFF`.

---

## 5. Firmware (Blue Pill) — scope

- **USB CDC** so the board appears as a COM port; firmware reads lines from USB serial.
- **Command parser:** Split line on spaces; dispatch SET / PATTERN / BEEP / ALL OFF.
- **PWM driver:** One timer (e.g. TIM2) for all four channels; PA0–PA3; duty 0–100%. LEDs typically 1–2 kHz, buzzer 1–4 kHz.
- **Pattern state machine:** Runs in a ~10 ms tick; updates pattern phase and PWM. PC never sends timing; it only sends `PATTERN <name>`.
- **Safety:** On boot or when no valid command for a while, drive all channels 0 (ALL OFF).

Target: small, readable firmware (on the order of ~100–120 lines for parser + PWM + pattern engine) without heavy frameworks.

---

## 6. Software impact (beaconctl / status_engine)

| Layer | Today (LCUS-4) | After rework |
|-------|-----------------|--------------|
| **Status engine** | Unchanged. Still computes state from Outlook; still calls “beaconctl” | Unchanged. Sends e.g. `beaconctl --state warn`; beaconctl translates to `PATTERN WARNING`. |
| **beaconctl** | Sends LCUS bytes to relay COM port. | Add **backend** `--backend bluepill`: opens Blue Pill COM port, sends ASCII lines (`PATTERN WARNING`, `SET R 100`, `ALL OFF`, etc.). Same CLI: `--state warn`, `--alloff`; optional `--ch N --on/--off` maps to SET R/Y/G/B 0 or 100. |
| **Config** | `comPort`, `protocol` (lcus_a/lcus_b). | Add `backend: "bluepill"`, `comPort` (Blue Pill CDC). Backend maps red/yellow/green/buzzer to SET R/Y/G/B. |
| **States / patterns** | Defined in config; beaconctl.py does on/off/pulse sequences. | Either: (A) beaconctl still does sequences over “ch N duty” and “pattern X” sent as multiple commands, or (B) firmware does patterns and beaconctl sends “state X” / “pattern X” once. (B) preferred to reduce traffic and centralize timing in firmware.) |

**PC side stays simple:** No timing or pattern steps (e.g. `ser.write(b"PATTERN WARNING\n")`). Status engine and config unchanged; only the hardware backend changes.

---

## 7. Migration path

1. **Firmware:** USB CDC, line parser, PWM (TIM2, PA0–PA3), pattern state machine. Test from serial terminal: `PATTERN WARNING`, `ALL OFF`.
2. **beaconctl:** Add Blue Pill backend; send `PATTERN <name>` (and `SET`/`BEEP`/`ALL OFF` when CLI needs direct control). Keep LCUS backend. Config or `--backend` selects which.
3. **Config:** Add `backend: "bluepill"`, `comPort` for Blue Pill.
4. **Deploy:** One USB cable to Blue Pill; status_engine unchanged.

---

## 8. Decided vs optional

- **Decided:** ASCII line protocol; patterns in firmware; USB CDC; commands SET R/Y/G/B, PATTERN IDLE/WARNING/CRITICAL/OFF, BEEP, ALL OFF; duty 0–100%; PC only sends high-level commands.
- **Optional:** Exact blink/chirp timings (firmware choice); ESCALATED/FAULT as distinct patterns or aliases to CRITICAL; baud rate (115200 or 9600).

---

## 9. Reference: current vs new

| Aspect | Current (LCUS-4) | New (Blue Pill + MOSFETs) |
|--------|-------------------|---------------------------|
| PC ↔ device | COM, 9600, LCUS bytes | COM, USB CDC, ASCII lines |
| Commands | Binary (A0 CH STATE sum) | `PATTERN WARNING`, `SET R 100`, `ALL OFF`, etc. |
| Output | Relay on/off (4 ch) | PWM 0–100% per channel (4 ch) |
| Buzzer | On/off/pulse only | PWM; patterns and BEEP duty/duration |
| Patterns | PC (beaconctl sequences) | Firmware (PC sends pattern name only) |
| Config | comPort, protocol lcus_a/b | backend bluepill, comPort |

**Final architecture:** PC → USB → Blue Pill (CDC) → PWM → 4× MOSFET → tower. 12 V supply: + to tower black and MOSFET OUT+; − to MOSFET DC− and Blue Pill GND.
