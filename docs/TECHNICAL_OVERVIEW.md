# Nekro-Sense for PHN16-72 — Technical Overview and Rationale

This document explains how Nekro‑Sense is built, how the platform was reverse‑engineered, and why a transparent, open‑source implementation delivers a better user experience than proprietary OEM tooling.


## Executive summary

Nekro‑Sense adds first‑class Linux support for key device features on the Acer Predator Helios Neo PHN16‑72:

- Four‑zone keyboard RGB (static and effects)
- Back‑lid logo/lightbar color, brightness, and power
- Fan control (auto/manual CPU/GPU)
- Platform performance profile (ACPI platform_profile)
- Battery charge limiter integration


It achieves this by interfacing directly with the machine’s ACPI/WMI firmware methods, following a careful, device‑specific reverse‑engineering process. The result is a small, auditable kernel module with a clean sysfs API, plus a CLI and a minimal GTK4 GUI that work out of the box on Linux—without background daemons, heavyweight services, or lock‑in.

## Project history and scope

Nekro‑Sense began as a community fork of the `linuwu-sense` project. While the original project provided a valuable foundation, development for the PHN16‑72 required additional model‑specific work. Over time this repository diverged in several meaningful ways:

- Re‑derivation of ACPI/WMI mappings from disassembled firmware tables for higher accuracy on PHN16‑72.
- Additional defensive checks and DMI gating to avoid applying model‑specific methods on other hardware.
- Expanded user‑space tooling: a fully scriptable CLI (`tools/linuwuctl.py`) and a GTK4 GUI (`tools/linuwu_sense_gui.py`) that use the CLI for privileged operations.
- Multiple firmware method paths and fallbacks (e.g., dedicated logo color methods and unified setters) to improve compatibility and reliability.

Although we borrow lessons and patterns from the upstream project, the current codebase is tailored to PHN16‑72 and designed to be self‑contained, auditable, and easy to script and extend.


## Architecture at a glance

- Kernel module: `src/linuwu_sense.c`
  - Registers a platform driver under the existing Acer WMI stack
  - Uses the vendor WMID interface to invoke ACPI methods exposed by firmware
  - Exposes a stable sysfs surface under `drivers/platform:acer-wmi/acer-wmi/…`
  - Device‑specific capabilities are gated by DMI (PHN16‑72 only for the back logo)
- User space
  - CLI: `tools/linuwuctl.py` — scriptable control for every feature
  - GUI: `tools/linuwu_sense_gui.py` — lightweight GTK4/libadwaita frontend
  - Privileged writes use `pkexec` when needed; the GUI never writes `/sys` directly

All code paths prefer minimalism: no background telemetry, no network calls, no opaque services. You can audit every line.


## Reverse engineering methodology

The PHN16‑72 exposes an ACPI WMID device (`PNP0C14`) that dispatches vendor methods via GUIDs. The workflow:

1. Collect ACPI tables safely (read‑only):
   - `acpidump` → extract tables
   - `acpixtract` → split to individual blobs
   - `iasl -d` → disassemble AML to ASL for human‑readable analysis
2. Locate the WMID device and method dispatchers
   - Identify the WMID device and the GUID used for gamer/lighting features
   - On this platform the GUID of interest is `7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56` (aka “GUID4”), mapped to the `WMBH` dispatcher (object id "BH")
   - Method families observed: `WMBH`, `WMBL`, `WMBK`
3. Decode method semantics from ASL
   - For keyboard and lightbar (logo), the `WMBH` dispatcher accepts an `Arg1` selector and, for some cases, a fixed‑size buffer
  - Key cases used by Nekro‑Sense:
     - `0x14` (unified set): programs a 16‑byte structure often referred to as BHLK; selector field `BHLK[9]` picks target (1=keyboard, 2=logo/lightbar)
     - `0x15` (unified get): returns the same 16‑byte buffer for the selected target
     - `0x0C` (logo color/brightness/power set): programs dedicated EC fields `LBLR/LBLG/LBLB/LBLT/LBLF`
     - `0x0D` (logo color/brightness/power get): returns those same fields
     - `0x06/0x07` (per‑segment paths): available as a fallback for logo segments LB1/LB2
4. Validate with no‑risk probes
   - Start with getters to confirm layout
   - Use setters only with conservative values and after verifying buffer lengths and status codes
5. Implement, test, and document
   - Changes are DMI‑gated to PHN16‑72 when feature behavior is model‑specific

Safety first: we never poke undocumented EC offsets directly; we go through the vendor’s ACPI dispatchers and reject unexpected formats or status codes.


## Firmware interface details (PHN16‑72)

- WMID GUID (lighting/game features): `7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56`
- Dispatcher: `WMBH`
- Keyboard (4‑zone):
  - Set (effect/static): `Arg1=0x14`, BHLK with selector `1`
  - Get: `Arg1=0x15`, selector `1`
- Back‑lid logo/lightbar (LB):
  - Preferred set: `Arg1=0x0C` with payload `[select=1, R, G, B, Brightness(0‑100), Enable(0/1)]`
  - Preferred get: `Arg1=0x0D` → returns `[status, R, G, B, Brightness, Enable]`
  - Some firmware honors power gating only via unified set: `Arg1=0x14` with selector `2` and `LBLE` bit. Linuwu‑Sense drives both where necessary.

Note: The driver is conservative by design; unknown statuses or unexpected buffer sizes cause the call to be rejected and surfaced to the kernel log.


## Kernel module design

- DMI‑gated capabilities
  - The back‑logo controls are enabled only on PHN16‑72 where they’ve been validated
- Sysfs API surface
  - Keyboard:
    - `four_zoned_kb/per_zone_mode` — `RRGGBB,RRGGBB,RRGGBB,RRGGBB,brightness`
    - `four_zoned_kb/four_zone_mode` — `mode,speed,brightness,direction,R,G,B`
  - Back logo:
    - `back_logo/color` — `RRGGBB,brightness,enable`
  - Platform profile and fan control live under predictable nodes as well
- Implementation highlights
  - All WMI calls go through WMID with strict buffer validations
  - Logo set/get use `0x0C/0x0D` for color/brightness/power and also toggle power via `0x14` for robustness
  - For models that ignore the “enable” flag, the driver enforces OFF by setting brightness `0`


## User‑space tooling

- CLI (`tools/linuwuctl.py`)
  - Scriptable control over keyboard, logo, fans, platform profile, and battery limiter
  - Writes to sysfs and returns helpful errors; elevated writes prompt for sudo if used from the GUI
- GUI (`tools/linuwu_sense_gui.py`)
  - GTK4/libadwaita application: a small, clean front‑end
  - RGB page includes both keyboard and back‑logo controls
  - Privileged operations are executed via `pkexec` by invoking the CLI; the GUI never touches `/sys` directly


## Testing and quality gates

- Build: simple `make` produces the kernel object in `src/`
- Load/unload: `insmod` and `rmmod` during development; packaging is optional
- Lint/type: kernel warnings treated strictly; Python sources byte‑compiled during CI or locally
- Runtime checks: 
  - Read back via sysfs after each write
  - Visual verification for LED colors/brightness
  - Fallback logic engaged only when the primary path isn’t honored by firmware


## Why open source beats proprietary OEM control panels

Open solutions like Nekro‑Sense provide tangible and durable advantages:

- Transparency and trust
  - You can read the exact calls made to system firmware and audit their safety
  - No hidden services, background processes, or undisclosed data flows
- Portability and performance
  - Native Linux support with minimal overhead; no emulation or bloated UI stacks
  - Scriptable via CLI; integrate with your dotfiles or systemd units
- Reliability and longevity
  - Community‑maintained; fixes and enhancements aren’t gated by product cycles
  - Clear device scoping and defensive programming reduce “mystery failures”
- Accessibility and inclusivity
  - Works across distributions; GUI is optional and lightweight
  - Power users can automate everything; casual users have a simple app

In contrast, proprietary Windows utilities (e.g., vendor “control center” apps) often:

- Depend on heavy frameworks and background services that consume resources
- Provide no insight into what they change or how they interact with firmware
- Are tied to specific OS versions and product lines, limiting long‑term support

The open‑source path prioritizes user agency, auditability, and a great Linux experience—today and years from now.


## Responsible disclosure and safety notes

- All interactions go through ACPI/WMI methods the firmware already exposes
- We do not write raw EC offsets; we avoid undefined behavior
- Back‑logo support is DMI‑gated to PHN16‑72 due to model‑specific wiring
- If you’d like to extend support to other models, follow the methodology above and gate your changes by DMI with a clear test matrix


## Roadmap

- Optional per‑segment logo control via `0x06/0x07` on models that implement segment effects
- Packaging for major distributions
- Upstreaming select pieces to mainline where appropriate
- Additional laptop models via community‑contributed DMI entries


## Appendix A — Quick reference (PHN16‑72)

- WMID GUID: `7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56`
- Methods used (dispatcher `WMBH`):
  - `0x14` unified set (BHLK selector: `1` keyboard, `2` logo)
  - `0x15` unified get
  - `0x0C` logo set (R,G,B,Brightness,Enable)
  - `0x0D` logo get (R,G,B,Brightness,Enable)
  - `0x06/0x07` per‑segment paths (not required for baseline functionality)


## Appendix B — Getting started

- Build: `make`
- Load: `sudo insmod src/linuwu_sense.ko`
- CLI examples:
  - Keyboard per‑zone static: `tools/linuwuctl.py rgb per-zone ff0000 00ff00 0000ff ffffff -b 60`
  - Keyboard effect: `tools/linuwuctl.py rgb effect wave -s 2 -b 80 -d 2 -c ff00ff`
  - Back logo: `tools/linuwuctl.py logo set ff6600 -b 70 --on`
  - Fans: `tools/linuwuctl.py fan auto` or `tools/linuwuctl.py fan set --cpu 35 --gpu 35`

All commands operate on local sysfs paths; no internet connectivity is used or required.
