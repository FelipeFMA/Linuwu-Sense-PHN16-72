# Linuwu-Sense — fork for Acer Predator PHN16-72

This repository is a hardware-specific fork of the original Linuwu-Sense driver. It contains changes developed and tested on the Acer Predator PHN16-72 and may not work on other models or hardware revisions.

Important notes

- Tested only on: Acer Predator PHN16-72.
- The driver uses low-level WMI/ACPI interfaces. On other hardware it may fail to load or behave unpredictably.
- Use at your own risk. The author is not responsible for hardware damage or data loss.

Quick install

1. Install kernel headers for your running kernel (example on Arch: `sudo pacman -S linux-headers`).
2. Build and install the module:

```bash
git clone https://github.com/FelipeFMA/Linuwu-Sense-PHN16-72.git
cd Linuwu-Sense-PHN16-72
make install
```

The `make install` step will attempt to remove the stock `acer_wmi` module and load the modified module in this repo.

To remove the installed module:

```bash
make uninstall
```

What the module exposes

The module creates sysfs entries that provide control over platform-specific features when supported by the firmware, for example:

- Thermal/power profiles (ACPI platform profile).
- Four-zone keyboard backlight (per-zone static colors and effect modes).
- Fan control and manual fan speed settings.
- Battery calibration and charge-limiter settings.
- LCD override and USB charging controls (when supported).

Typical sysfs paths (examples):

- Predator fork path used here:

  `/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense`

- Original Nitro example path:

  `/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/nitro_sense`

Keyboard RGB (four-zone)

When the keyboard is supported, the driver exposes two interfaces:

- `per_zone_mode` — set static RGB per zone (comma-separated hex values and brightness).
- `four_zone_mode` — set effect modes and parameters (mode, speed, brightness, direction, RGB).

Tools and CLI helper

There is a helper script at `tools/linuwuctl.py` that performs common sysfs reads/writes and validates input formats. Root privileges are required for writes.

License and liability

This project is released under the GNU GPLv3. Use it at your own risk; there is no warranty and the author disclaims liability for damages.

For full, verbatim usage examples and low-level cat/echo commands, see the original project's README or inspect `tools/linuwuctl.py` for practical examples.
