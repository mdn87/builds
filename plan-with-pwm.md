STM32F103C8T6 Tower Beacon Control Spec
1. Hardware goal

Use a Blue Pill STM32F103C8T6 as the single USB-connected controller for a 12 V tower beacon with:

red light

yellow light

green light

buzzer

The tower is wired as:

black  = common +12 V
red    = switched ground for red
yellow = switched ground for yellow
green  = switched ground for green
gray   = switched ground for buzzer

That means the controller does not source 12 V to the tower functions.
It uses MOSFETs to sink each function wire to ground.

2. Final hardware architecture
PC
 │
USB
 │
STM32F103C8T6 Blue Pill
 │
 ├─ PWM/GPIO → Red MOSFET
 ├─ PWM/GPIO → Yellow MOSFET
 ├─ PWM/GPIO → Green MOSFET
 └─ PWM/GPIO → Buzzer MOSFET

12 V power supply
 ├─ +12 V → tower black + MOSFET power rails
 └─ GND  → MOSFET ground rail + Blue Pill GND

Blue Pill is powered by USB.

The tower and MOSFET load side are powered by 12 V DC.

3. Pin assignment

Use the pins already chosen:

PA0 → Red channel
PA1 → Yellow channel
PA2 → Green channel
PA3 → Buzzer channel
GND → common signal ground

These pins are a good choice because they are grouped and easy to treat as a 4-channel output set.

Implementation-wise, these should be configured so they support:

digital on/off

PWM output

pattern timing under firmware control

4. MOSFET channel mapping
Light channels

You have 3 MOSFET modules with:

VIN+  VIN-
OUT+  OUT-
TRIG/PWM
GND

Use them as:

Red MOSFET
VIN+  → +12 V
VIN-  → 12 V GND
OUT+  → +12 V
OUT-  → tower red
TRIG  → PA0
GND   → Blue Pill GND
Yellow MOSFET
VIN+  → +12 V
VIN-  → 12 V GND
OUT+  → +12 V
OUT-  → tower yellow
TRIG  → PA1
GND   → Blue Pill GND
Green MOSFET
VIN+  → +12 V
VIN-  → 12 V GND
OUT+  → +12 V
OUT-  → tower green
TRIG  → PA2
GND   → Blue Pill GND
Buzzer MOSFET

You have 1 MOSFET module with:

+   LOAD   -
PWM/TRIG
GND

Use it as:

+      → +12 V
LOAD   → tower gray
-      → 12 V GND
PWM    → PA3
GND    → Blue Pill GND
Tower common
tower black → +12 V directly

Do not route tower black through a MOSFET.

5. Power rail requirements
+12 V rail must feed:
tower black
red MOSFET VIN+
red MOSFET OUT+
yellow MOSFET VIN+
yellow MOSFET OUT+
green MOSFET VIN+
green MOSFET OUT+
buzzer MOSFET +
Ground rail must feed:
red MOSFET VIN-
yellow MOSFET VIN-
green MOSFET VIN-
buzzer MOSFET -
Blue Pill GND

This can be a daisy chain or bus. It does not need to be a ring.

Do not make the +12 V rail a closed loop. Treat it as a distribution bus.

6. Capacitor placement

Add one supply capacitor across the 12 V rail near the MOSFET boards:

capacitor + → +12 V rail
capacitor - → ground rail

Best placement:

across VIN+ / VIN- on the first light MOSFET board, or

across + / - on the buzzer MOSFET board if that is the main power entry point

Do not place the capacitor:

across OUT+ / OUT-

across LOAD / -

on PWM pins

Suggested values:

100 µF electrolytic minimum

optional 0.1 µF ceramic in parallel

7. Grounding requirements

All grounds must be common at the electrical reference level:

12 V supply negative
light MOSFET power negatives
buzzer MOSFET power negative
Blue Pill GND
MOSFET control GND pins

Practical rule:

use thicker wire for the main 12 V ground bus

use thinner wire for Blue Pill signal ground and PWM wires

Any Blue Pill GND pin can be used.

8. Control-side electrical assumptions

The MOSFET modules accept logic input on their TRIG/PWM pins and use GND as control reference.

The Blue Pill pins should drive them as standard digital outputs or PWM outputs.

Working assumptions for firmware:

logic HIGH on PAx = channel active

logic LOW on PAx = channel inactive

If any channel behaves inverted, that can be corrected in software by inverting duty or logic state.

9. Intended behavior model

The firmware should own behavior.
The PC should not micromanage timing.

The PC sends a high-level command or state.
The Blue Pill handles:

PWM duty

fades

blink timing

buzzer pulse timing

pattern transitions

This avoids timing jitter and keeps the serial protocol simple.

10. Channel behavior requirements
Red, Yellow, Green lights

Each light channel should support:

hard OFF

hard ON

variable PWM brightness

blink patterns

fade in / fade out

breathing effect if desired

Buzzer

The buzzer channel should support:

OFF

ON

PWM-based intensity shaping

repeated pulse patterns

one-shot chirps/beeps

pattern-based alarm cadence

Important practical note:
If the tower buzzer is an active buzzer, PWM will mostly affect perceived intensity and texture, not musical pitch.

11. Firmware control model

The firmware should conceptually have three layers.

Layer 1 - hardware abstraction

Simple channel control API:

set_channel_duty(channel, duty_0_to_100)
set_channel_on(channel)
set_channel_off(channel)

Channels:

RED
YELLOW
GREEN
BUZZER
Layer 2 - pattern engine

A state machine that updates outputs every fixed tick.

Example tick interval:

10 ms

This layer computes:

blink phase

fade ramps

pulse durations

transitions

Layer 3 - command interface

Receives commands from PC over USB serial and changes:

active pattern

channel duty overrides

buzzer events

idle/warning/critical state

12. Recommended control concepts
Direct channel control

Used for testing and manual commands.

Examples of internal concepts:

SET RED 100
SET YELLOW 0
SET GREEN 25
SET BUZZER 60
ALL OFF

This means:

100 = full duty

0 = off

Pattern control

Used for actual system behavior.

Examples:

PATTERN OFF
PATTERN IDLE
PATTERN WARNING
PATTERN CRITICAL

Pattern meaning should live in firmware.

13. Suggested default pattern definitions

These are just a sane starting point.

OFF
all channels off
IDLE
green low breathing or steady dim
red off
yellow off
buzzer off
WARNING
yellow blink at moderate rate
green off
red off
buzzer short chirp occasionally
CRITICAL
red fast blink or pulse
yellow optional off
green off
buzzer repeated pulse pattern

Optional alternate logic:

IDLE can also mean all off

warning can be steady yellow

critical can be solid red + buzzer pulse

14. PWM and timing concepts

Exact register setup is implementation detail, but the functional requirement is:

light PWM should be flicker-free

buzzer PWM should support shaping without sounding broken

pattern timing should be independent of USB command timing

Practical concepts:

use hardware PWM for each channel if convenient

use a periodic firmware tick for pattern scheduling

brightness and fade changes should be incremental, not blocking delays

Avoid firmware design that relies on long delay() calls for patterns.

Prefer:

timer/tick-based state machine

non-blocking pattern updates

15. PC-to-controller role split
PC side responsibilities

determine system status

decide desired high-level state

send simple commands over USB serial

Later example:

monitor mailbox

if unread older than threshold, send PATTERN WARNING

if severely overdue, send PATTERN CRITICAL

if clear, send PATTERN IDLE

Blue Pill responsibilities

maintain output timing

render patterns

apply PWM

enforce smooth transitions if desired

This is the right split.

16. USB communication concept

Use the Blue Pill as the single device the PC talks to.

Preferred conceptual interface:

USB serial style command stream

line-based ASCII commands

Loose format idea:

COMMAND ARG ARG\n

Examples:

SET R 100
SET Y 40
SET G 0
SET B 70
PATTERN WARNING
PATTERN CRITICAL
ALL OFF
BEEP 70 200

The exact protocol can stay simple as long as it is:

human-readable

tolerant of malformed lines

easy to test from a terminal

17. Wiring and implementation constraints

The implementation should assume:

Tower black is always tied to +12 V.

All other tower wires are low-side switched.

The three light MOSFET modules need both VIN and OUT tied correctly.

The buzzer MOSFET uses + / LOAD / -, with the tower gray wire on LOAD.

Blue Pill PWM outputs are:

PA0 red

PA1 yellow

PA2 green

PA3 buzzer

Blue Pill is USB-powered.

The 12 V adapter powers the tower and MOSFET load side only.

Blue Pill GND must be tied to the system ground rail.

18. Mechanical and build notes

PWM wires and control ground can be light gauge.

Main 12 V rails should be more robust.

RTV silicone is acceptable for strain relief and board mounting.

Do not rely on adhesive instead of proper solder joints.

A small amount of RTV on wire insulation near pads is fine.

One supply capacitor across the 12 V rails is recommended.

19. What the next implementation step should look like

The firmware spec should start from these capabilities:

Initialize PA0-PA3 as output-capable PWM channels.

Provide internal channel abstraction for R/Y/G/B.

Implement non-blocking pattern scheduler.

Implement simple serial command parser.

Support both direct channel control and high-level patterns.

Keep PC protocol simple and stateless where possible.

That is the correct loose implementation target without locking into a specific framework too early.