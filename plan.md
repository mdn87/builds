Phase 0 - assumptions and constraints

Hardware: Windows PC + LCUS-4 (CH340 USB-serial relay board) + 12 V beacon. PC talks to the relay board over a COM port. The relay board switches 12 V to the beacon wires. No Blue Pill in the first implementation.

Goal: First get deterministic command control working (CLI switches). Then add “email inbox stale unread” status logic that drives the same relay commands.

Phase 1 - CLI relay control (prove the pipe)

Define a small relay control program (single executable or script) that:

opens a specified COM port at 9600 baud

sends relay on/off commands

exits with proper error codes if COM port is missing, access denied, timeout, or protocol mismatch

supports a “dry-run” mode that prints what would be sent

Command-line interface (initial)
Minimum viable switches:

--port COM5

--ch 1|2|3|4

--on or --off

--alloff

--status (optional, if board supports query)

--pulse 1000 (milliseconds, optional)

Examples:

beaconctl --port COM5 --ch 1 --on

beaconctl --port COM5 --ch 1 --off

beaconctl --port COM5 --alloff

beaconctl --port COM5 --ch 4 --pulse 750

Logical mapping layer
Create a stable mapping in config (json/yaml) so code never hardcodes channel meaning:

channels:

red: 1

yellow: 2

green: 3

buzzer: 4

Then allow:

beaconctl --port COM5 --red on

beaconctl --port COM5 --buzzer pulse=750

beaconctl --port COM5 --set red=on yellow=off green=off buzzer=off

But implement the simple --ch first.

Safety behavior
Default behavior when setting a color:

If a color is turned on, optionally turn other colors off (exclusive mode).
Add switch:

--exclusive (default on) or --nonexclusive

Logging

--log-file path

log timestamp, COM port, bytes sent, and any errors
This will matter once it runs unattended.

Known risk: LCUS protocol variants
Implement protocol as a pluggable strategy:

protocol = lcus_a (default)

protocol = lcus_b (alternate)
Expose:

--protocol lcus_a|lcus_b
If relay does not click, swap protocol without rewriting the app.

Deliverable for Phase 1

beaconctl can reliably turn each relay on/off and pulse buzzer

a short README with wiring assumptions and example commands

Phase 2 - thin “status engine” that calls the same command layer

Do not merge email logic into the relay code. Keep layers:

relay driver: “send relay commands”

command interface: parses CLI, calls relay driver

status engine: decides desired beacon state, calls relay driver (or shells out to beaconctl)

Phase 3 - email inbox status integration (vague but actionable)

Objective: Turn beacon on if there exists any unread email older than threshold (example 60 minutes). Optional: different colors for different states.

Status definitions (initial)

OK: no stale unread -> green on (or all off)

Warning: unread older than 60 min exists -> yellow on

Critical: unread older than 120 min exists -> red on + optional buzzer pulse on transition

Implementation approach (pick one later, after commands work)
Option A: Outlook COM (fastest if Outlook is installed and mailbox is in profile)

Use pywin32 or a .NET app to query Inbox items

Filter unread, check ReceivedTime vs cutoff

Runs as scheduled task every N minutes

Option B: IMAP polling (works for Gmail and some providers)

Log in with app password/OAuth

Search UNSEEN, fetch headers/date

Compare timestamps

Option C: Microsoft Graph (most correct for M365, but more setup)

App registration, OAuth, Graph query for unread messages and receivedDateTime

Potentially subscriptions later, but polling is fine at first

Control loop behavior

Poll interval: 2-5 minutes

Hysteresis: require condition to be true for 2 consecutive polls before switching to avoid flapping

Transition actions: buzzer pulses only when entering Warning/Critical, not continuously

Deliverable for Phase 3

a “monitor” process (script or service) that computes state and calls the relay layer

configuration file for thresholds, poll interval, channel mapping, and COM port

Instructions to your Cursor agent (paste this)

Build a Windows relay control utility for an LCUS-4 USB relay board (CH340, serial). Phase 1 is CLI-only. Provide: beaconctl --port COMx --ch 1-4 --on/--off, plus --alloff and --pulse ms. Implement logging and proper exit codes. Make relay protocol pluggable via --protocol, because LCUS-4 clones vary. Keep channel mapping in a config file.

After CLI control is stable, implement a separate “status engine” that polls an email inbox and decides beacon state. Keep it layered: status engine -> relay driver. Start with polling (2-5 min). State rules: if any unread email is older than 60 minutes, turn yellow on; if older than 120 minutes, red on; otherwise green or off. Pulse buzzer only on transition into warning/critical. Email access method can be selected later (Outlook COM if Outlook is installed, otherwise IMAP or Microsoft Graph).

This will be for O365 running the script in whichever language or platform will be best for monitoring a mailbox on the computer with office desktop installed and running in realtime.