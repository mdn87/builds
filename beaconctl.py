#!/usr/bin/env python3
"""
beaconctl.py — LCUS-4 relay control for 3-colour beacon lamp + buzzer
Phase 1: minimum viable CLI relay control

Usage examples:
  python beaconctl.py --port COM5 --ch 1 --on
  python beaconctl.py --port COM5 --ch 1 --off
  python beaconctl.py --port COM5 --alloff
  python beaconctl.py --port COM5 --ch 4 --pulse 750
  python beaconctl.py --port COM5 --ch 2 --on --exclusive
  python beaconctl.py --dry-run --ch 3 --on

Exit codes:
  0  success
  1  invalid arguments
  2  COM port access denied
  3  COM port not found / in use
  4  serial write timeout
  99 unexpected error
"""

import argparse
import json
import logging
import os
import sys
import time

try:
    import serial
except ImportError:
    print("error: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(99)

# ---------------------------------------------------------------------------
# Protocol byte builders
# ---------------------------------------------------------------------------

def build_lcus_a(channel: int, on: bool) -> bytes:
    """Standard LCUS-4: header + ch + state + (sum & 0xFF)"""
    header = 0xA0
    state  = 0x01 if on else 0x00
    ch     = channel & 0xFF
    cksum  = (header + ch + state) & 0xFF
    return bytes([header, ch, state, cksum])


def build_lcus_b(channel: int, on: bool) -> bytes:
    """Alternate clone variant: header + ch + state + (XOR of prior bytes)"""
    header = 0xA0
    state  = 0x01 if on else 0x00
    ch     = channel & 0xFF
    cksum  = (header ^ ch ^ state) & 0xFF
    return bytes([header, ch, state, cksum])


def build_command(channel: int, on: bool, protocol: str) -> bytes:
    if protocol == "lcus_b":
        return build_lcus_b(channel, on)
    return build_lcus_a(channel, on)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "comPort":   "COM5",
    "baudRate":  9600,
    "protocol":  "lcus_a",
    "exclusive": True,
    "channels":  {"red": 1, "yellow": 2, "green": 3, "buzzer": 4},
}


def find_config() -> str | None:
    """Walk up from script location looking for config/channels.json."""
    # CWD first
    cwd_path = os.path.join(os.getcwd(), "config", "channels.json")
    if os.path.exists(cwd_path):
        return cwd_path
    # Walk up from script location
    base = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidate = os.path.join(base, "config", "channels.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(base)
        if parent == base:
            break
        base = parent
    return None


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    resolved = path or find_config()
    if resolved and os.path.exists(resolved):
        with open(resolved, encoding="utf-8") as f:
            data = json.load(f)
        cfg.update(data)
    return cfg


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

class RelayDriver:
    def __init__(self, port: str, baud: int, protocol: str, dry_run: bool, log: logging.Logger):
        self.port     = port
        self.baud     = baud
        self.protocol = protocol
        self.dry_run  = dry_run
        self.log      = log
        self._serial  = None

    def open(self):
        if self.dry_run:
            print(f"[DRY-RUN] Would open {self.port} @ {self.baud} baud  protocol={self.protocol}")
            return
        self._serial = serial.Serial(
            port=self.port, baudrate=self.baud,
            bytesize=8, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
            timeout=0.5, write_timeout=0.5
        )
        self.log.info("Opened %s @ %d baud  protocol=%s", self.port, self.baud, self.protocol)

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()

    def set_channel(self, channel: int, on: bool):
        cmd = build_command(channel, on, self.protocol)
        state_str = "ON" if on else "OFF"
        if self.dry_run:
            print(f"[DRY-RUN] CH{channel} -> {state_str}  bytes={cmd.hex(' ').upper()}")
            return
        self.log.debug("CH%d %s → %s", channel, state_str, cmd.hex(" ").upper())
        self._serial.write(cmd)

    def all_off(self, max_channel: int):
        for ch in range(1, max_channel + 1):
            self.set_channel(ch, False)
            if not self.dry_run:
                time.sleep(0.02)  # brief inter-command gap

    def pulse(self, channel: int, ms: int):
        self.set_channel(channel, True)
        if self.dry_run:
            print(f"[DRY-RUN] (waiting {ms} ms)")
        else:
            time.sleep(ms / 1000.0)
        self.set_channel(channel, False)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="beaconctl",
        description="LCUS-4 relay control for 3-colour beacon lamp + buzzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  beaconctl --port COM5 --ch 1 --on
  beaconctl --port COM5 --ch 2 --off
  beaconctl --port COM5 --alloff
  beaconctl --port COM5 --ch 4 --pulse 750
  beaconctl --dry-run --ch 3 --on --exclusive
"""
    )
    p.add_argument("--port",         metavar="COMx",  help="COM port (overrides config)")
    p.add_argument("--ch",           type=int,         metavar="N",    help="Relay channel 1-4")
    p.add_argument("--on",           action="store_true",               help="Turn channel on")
    p.add_argument("--off",          action="store_true",               help="Turn channel off")
    p.add_argument("--alloff",       action="store_true",               help="Turn all channels off")
    p.add_argument("--pulse",        type=int,         metavar="MS",   help="Pulse channel ON for N ms then off")
    p.add_argument("--protocol",     choices=["lcus_a", "lcus_b"],      help="Protocol variant (default: lcus_a)")
    p.add_argument("--exclusive",    action="store_true",               help="Turn off other channels before turning one on")
    p.add_argument("--nonexclusive", action="store_true",               help="Allow multiple channels on simultaneously")
    p.add_argument("--dry-run",      action="store_true",               help="Print commands without sending")
    p.add_argument("--log-file",     metavar="PATH",                    help="Append log lines to file")
    p.add_argument("--config",       metavar="PATH",                    help="Path to channels.json")
    return p


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    # ── Load config ──────────────────────────────────────────────────────────
    cfg = load_config(args.config)

    # ── Logging ──────────────────────────────────────────────────────────────
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    log = logging.getLogger("beaconctl")

    # ── Resolve settings ─────────────────────────────────────────────────────
    com_port    = args.port or cfg.get("comPort", "COM5")
    baud_rate   = cfg.get("baudRate", 9600)
    protocol    = args.protocol or cfg.get("protocol", "lcus_a")
    channels    = cfg.get("channels", DEFAULT_CONFIG["channels"])
    max_channel = max(channels.values()) if channels else 4
    dry_run     = args.dry_run

    # exclusive: CLI --nonexclusive overrides all; else --exclusive flag; else config
    if args.nonexclusive:
        exclusive = False
    elif args.exclusive:
        exclusive = True
    else:
        exclusive = bool(cfg.get("exclusive", True))

    # ── Validate ─────────────────────────────────────────────────────────────
    if not args.alloff and args.ch is None:
        parser.error("specify --ch N or --alloff")

    if not args.alloff and args.pulse is None and not args.on and not args.off:
        parser.error("specify --on, --off, or --pulse <ms>")

    if args.on and args.off:
        parser.error("--on and --off are mutually exclusive")

    if args.ch is not None and not (1 <= args.ch <= 4):
        parser.error("--ch must be 1, 2, 3, or 4")

    # ── Execute ──────────────────────────────────────────────────────────────
    try:
        with RelayDriver(com_port, baud_rate, protocol, dry_run, log) as driver:
            if args.alloff:
                log.info("alloff: turning channels 1-%d off", max_channel)
                driver.all_off(max_channel)

            elif args.pulse is not None:
                log.info("CH%d pulse %d ms (exclusive=%s)", args.ch, args.pulse, exclusive)
                if exclusive:
                    driver.all_off(max_channel)
                driver.pulse(args.ch, args.pulse)

            elif args.on:
                log.info("CH%d ON (exclusive=%s)", args.ch, exclusive)
                if exclusive:
                    driver.all_off(max_channel)
                driver.set_channel(args.ch, True)

            else:  # off
                log.info("CH%d OFF", args.ch)
                driver.set_channel(args.ch, False)

        return 0

    except PermissionError as exc:
        print(f"error: COM port access denied — {exc}", file=sys.stderr)
        log.error("COM port access denied: %s", exc)
        return 2

    except serial.SerialException as exc:
        msg = str(exc).lower()
        if "access" in msg or "denied" in msg:
            print(f"error: COM port access denied — {exc}", file=sys.stderr)
            return 2
        print(f"error: COM port not found or in use — {exc}", file=sys.stderr)
        log.error("Serial error: %s", exc)
        return 3

    except serial.SerialTimeoutException as exc:
        print(f"error: serial write timeout — {exc}", file=sys.stderr)
        log.error("Serial timeout: %s", exc)
        return 4

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        log.exception("Unexpected error")
        return 99


if __name__ == "__main__":
    sys.exit(main())
