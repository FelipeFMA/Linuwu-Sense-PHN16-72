# Linuwu-Sense — fork for Acer Predator PHN16-72

This repository is a hardware-specific fork of the original Linuwu-Sense driver. It contains changes developed and tested on the Acer Predator PHN16-72 and may not work on other models or hardware revisions.

Important support and OS scope

- No support is provided. Please do not open issues or ask for help — they will PROBABLY not be answered.
- Tested only on Arch Linux. It will probably work on most mainstream Linux distributions with standard kernels and headers, but this is not guaranteed.

Important notes

- Tested only on: Acer Predator PHN16-72.
- OS compatibility: Developed and validated on Arch Linux only; other distros are untested. Likely compatible with common Linux distributions, but you are on your own.
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

## Build toolchain note (Clang vs GCC)

Many distributions (e.g., CachyOS) build their kernels with Clang/LLVM. When your running kernel is built with Clang, trying to build this out-of-tree module with GCC can fail with errors like:

- `gcc: error: unrecognized command-line option ‘-mretpoline-external-thunk’`
- `gcc: error: unrecognized command-line option ‘-fsplit-lto-unit’`
- `gcc: error: unrecognized command-line option ‘-mllvm’`

In that case, rebuild using the kernel’s LLVM toolchain:

```bash
# Build with Clang/LLVM to match the kernel toolchain
make LLVM=1
sudo make LLVM=1 install
```

Alternatively, you can export the variables once for your shell/session:

```bash
export LLVM=1
# Optionally make it explicit:
export CC=clang
export LD=ld.lld
```

## Troubleshooting

- Missing headers: ensure kernel headers for your exact running kernel are installed.
  - Arch/CachyOS: `sudo pacman -S linux-headers` (or your kernel flavor’s headers)
  - Debian/Ubuntu: `sudo apt install linux-headers-"$(uname -r)"`

- GCC vs Clang flags: if you see GCC complaining about unknown `-mllvm`, `-fsplit-lto-unit`, or similar flags, rebuild with `LLVM=1` as shown above.

- Operation not permitted in `src/`: if you see errors like `unable to open output file 'src/linuwu_sense.o': Operation not permitted`, it usually means there are root-owned or protected build artifacts in the repo (from a previous sudo build) or immutable attributes.
  - Fix ownership and clean:
    ```bash
    sudo chown -R "$USER":"$USER" /path/to/Linuwu-Sense-PHN16-72
    make clean
    ```
  - If files are immutable, clear the flag (rare):
    ```bash
    lsattr -R src
    # If you see an 'i' attribute, remove it then clean
    sudo chattr -i src/*
    make clean
    ```
  - Prefer compiling as your user and using `sudo` only for the install step:
    ```bash
    make LLVM=1
    sudo make LLVM=1 install
    ```

- Module conflicts: the install target tries to remove the stock `acer_wmi` and load this module. If you still see conflicts, unload related modules before installing:
  ```bash
  sudo modprobe -r acer_wmi
  sudo modprobe -r wmi
  sudo make LLVM=1 install
  ```

If issues persist, you are on your own. No support is provided for this fork and bug reports probably won't receive a response. Consult your distro documentation, upstream resources, or debug locally at your own risk.

## Contributions

Pull requests are welcome if they:

- Target exactly the same hardware: Acer Predator PHN16-72 (this fork’s focus).
- Keep the scope minimal and avoid unnecessary bloat or broad, untested feature additions.
- Maintain existing behavior for this model and do not introduce cross-model abstractions without clear benefit here.

PRs that add generic features for other models, or introduce complexity without a direct need for PHN16-72, will likely be declined.

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

### GUI (GTK4 + libadwaita)

A simple GUI is available at `tools/linuwu_sense_gui.py`.

Run it with Python 3 (you may need to install `python3-gi` and libadwaita bindings on your distro):

```bash
python3 tools/linuwu_sense_gui.py
```

You can start the GUI directly on a specific page using these flags:

- `-k` / `--keyboard` — open on the Keyboard page (default)
- `-p` / `--power` — open on the Power page
- `-f` / `--fans` — open on the Fans page

Examples:

```bash
python3 tools/linuwu_sense_gui.py --power
python3 tools/linuwu_sense_gui.py -f
```

Battery limiter (80%)

On supported machines the driver exposes a `battery_limiter` sysfs attribute (1=limit to ~80%, 0=full charge). The CLI provides convenient wrappers:

```bash
# Show if the 80% limiter is enabled (1) or disabled (0)
sudo python3 tools/linuwuctl.py battery get

# Enable 80% charge limit
sudo python3 tools/linuwuctl.py battery on

# Disable 80% charge limit
sudo python3 tools/linuwuctl.py battery off

# Or explicitly set with on/off or 1/0
sudo python3 tools/linuwuctl.py battery set on
sudo python3 tools/linuwuctl.py battery set 0
```

License and liability

This project is released under the GNU GPLv3. Use it at your own risk; there is no warranty and the author disclaims liability for damages.

For full, verbatim usage examples and low-level cat/echo commands, see the original project's README or inspect `tools/linuwuctl.py` for practical examples.
