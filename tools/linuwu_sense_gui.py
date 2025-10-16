#!/usr/bin/env python3
"""
Linuwu Sense (GTK)

A minimal GTK4 + libadwaita GUI to control the Linuwu-Sense kernel module.

Features:
- Keyboard RGB four-zone: per-zone static or simple effect
- Power profile: get/set ACPI platform_profile
- Fans: set auto or CPU/GPU percentages

Notes:
- This GUI writes to /sys paths via the Linuwu-Sense module. Most actions
  require root privileges. Run with sudo or install a polkit rule (not provided).
- Uses constants from tools/linuwuctl.py but avoids calling its CLI helpers
  directly to prevent sys.exit() from killing the GUI on missing paths.

Dependencies (Debian/Ubuntu):
- sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

Run:
- python3 tools/linuwu_sense_gui.py
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk, Gio
except Exception as e:
    sys.stderr.write(
        f"Failed to import GTK4/libadwaita Python bindings: {e}\n"
        "Install with: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1\n"
    )
    raise


# Ensure we can import sibling tool module when executed from repo root
HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    import linuwuctl as ctl
except Exception as e:
    sys.stderr.write(
        f"Failed to import linuwuctl from tools/: {e}\n"
    )
    raise


def path_exists(p: str) -> bool:
    return os.path.exists(p)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(content)


def parse_hex_color(s: str) -> str:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ValueError("Use RRGGBB or #RRGGBB")
    return s.lower()


def detect_sense_fan_path() -> Optional[str]:
    base = None
    if path_exists(ctl.SYSFS_BASE):
        if path_exists(ctl.SENSE_PRED):
            base = ctl.SENSE_PRED
        elif path_exists(ctl.SENSE_NITRO):
            base = ctl.SENSE_NITRO
    if base is None:
        return None
    p = os.path.join(base, "fan_speed")
    return p if path_exists(p) else None


class StatusNotifier:
    def __init__(self, label: Gtk.Label):
        self.label = label

    def info(self, msg: str) -> None:
        self.label.set_text(msg)
        self.label.remove_css_class("error")

    def error(self, msg: str) -> None:
        self.label.set_text(msg)
        if "error" not in self.label.get_css_classes():
            self.label.add_css_class("error")


class LinuwuApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.LinuwuSense", flags=Gio.ApplicationFlags.FLAGS_NONE)
        # Follow system appearance; DEFAULT maps to system preference in libadwaita.
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def do_activate(self):
        if self.props.active_window:
            self.props.active_window.present()
            return

        win = Adw.ApplicationWindow(application=self)
        win.set_title("Linuwu Sense")
        win.set_default_size(680, 520)

        # Header and status
        header = Adw.HeaderBar()
        status = Gtk.Label(xalign=0)
        status.add_css_class("dim-label")
        notifier = StatusNotifier(status)

        # Build pages
        stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcherBar()
        switcher.set_stack(stack)

        keyboard = self._build_keyboard_page(notifier)
        power = self._build_power_page(notifier)
        fans = self._build_fans_page(notifier)

        stack.add_titled(keyboard, "keyboard", "Keyboard")
        stack.add_titled(power, "power", "Power")
        stack.add_titled(fans, "fans", "Fans")

        # Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.append(header)
        vbox.append(stack)
        vbox.append(switcher)

        # Footer status
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer.set_margin_top(6)
        footer.set_margin_bottom(6)
        footer.set_margin_start(12)
        footer.set_margin_end(12)
        footer.append(status)
        vbox.append(footer)

        win.set_content(vbox)
        win.present()
        notifier.info("Ready")

    # Keyboard page
    def _build_keyboard_page(self, notifier: StatusNotifier) -> Gtk.Widget:
        page = Adw.PreferencesPage(title="Keyboard")

        # Group: Per-zone static
        g_static = Adw.PreferencesGroup(title="Per-zone static colors")

        single_row = Adw.SwitchRow(title="Single color for all zones")
        single_row.set_active(True)
        g_static.add(single_row)

        single_color = Adw.EntryRow(title="Color (RRGGBB)")
        single_color.set_text("00aaff")
        g_static.add(single_color)

        # Zone rows
        z_entries: List[Adw.EntryRow] = []
        for i in range(4):
            er = Adw.EntryRow(title=f"Zone {i+1} (RRGGBB)")
            er.set_text("00aaff" if i == 0 else "00aaff")
            er.set_sensitive(False)  # start disabled when single color on
            z_entries.append(er)
            g_static.add(er)

        def on_single_toggled(_row, _pspec=None):
            use_single = single_row.get_active()
            single_color.set_sensitive(use_single)
            for er in z_entries:
                er.set_sensitive(not use_single)

        single_row.connect("notify::active", on_single_toggled)

        bright_row = Adw.SpinRow(title="Brightness", adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1, page_increment=10, value=100))
        g_static.add(bright_row)

        btn_apply_static = Gtk.Button(label="Apply static")
        btn_apply_static.add_css_class("suggested-action")
        btn_apply_static.set_halign(Gtk.Align.START)
        btn_apply_static.set_margin_top(6)
        btn_apply_static.set_margin_bottom(6)
        btn_apply_static.set_margin_start(12)

        def apply_static(_btn):
            try:
                if not path_exists(ctl.KB_PER_ZONE):
                    raise FileNotFoundError(f"Missing per_zone_mode at {ctl.KB_PER_ZONE}")

                brightness = int(bright_row.get_value())
                if single_row.get_active():
                    c = parse_hex_color(single_color.get_text())
                    colors = [c]
                else:
                    colors = [parse_hex_color(er.get_text()) for er in z_entries]
                    if len(colors) != 4:
                        raise ValueError("Provide 4 colors")

                if len(colors) == 1:
                    colors = colors * 4

                payload = ",".join(colors + [str(brightness)]) + "\n"
                write_text(ctl.KB_PER_ZONE, payload)
                notifier.info("Keyboard static colors applied")
            except PermissionError:
                notifier.error("Permission denied: run as root to apply.")
            except Exception as e:
                notifier.error(f"Error: {e}")

        btn_apply_static.connect("clicked", apply_static)

        # Add an action row with the apply button
        row_apply_static = Adw.ActionRow(title="Apply static")
        row_apply_static.add_suffix(btn_apply_static)
        row_apply_static.set_activatable_widget(btn_apply_static)
        g_static.add(row_apply_static)

        # Group: Effect
        g_effect = Adw.PreferencesGroup(title="Effect (four_zone_mode)")

        # Mode Combo
        mode_names = list(ctl.MODE_NAME_TO_ID.keys())
        mode_store = Gtk.StringList.new(mode_names)
        mode_row = Adw.ComboRow(title="Mode")
        mode_row.set_model(mode_store)
        mode_row.set_selected(mode_names.index("wave") if "wave" in mode_names else 0)
        g_effect.add(mode_row)

        speed_row = Adw.SpinRow(title="Speed", adjustment=Gtk.Adjustment(lower=0, upper=9, step_increment=1, page_increment=1, value=1))
        bright2_row = Adw.SpinRow(title="Brightness", adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1, page_increment=10, value=100))
        dir_row = Adw.SpinRow(title="Direction (1-2)", adjustment=Gtk.Adjustment(lower=1, upper=2, step_increment=1, page_increment=1, value=2))
        color_row = Adw.EntryRow(title="Color (optional RRGGBB)")
        color_row.set_text("")
        g_effect.add(speed_row)
        g_effect.add(bright2_row)
        g_effect.add(dir_row)
        g_effect.add(color_row)

        btn_apply_effect = Gtk.Button(label="Apply effect")
        btn_apply_effect.add_css_class("suggested-action")
        btn_apply_effect.set_halign(Gtk.Align.START)
        btn_apply_effect.set_margin_top(6)
        btn_apply_effect.set_margin_bottom(6)
        btn_apply_effect.set_margin_start(12)

        def apply_effect(_btn):
            try:
                if not path_exists(ctl.KB_FOUR_MODE):
                    raise FileNotFoundError(f"Missing four_zone_mode at {ctl.KB_FOUR_MODE}")

                mode_name = mode_names[mode_row.get_selected()]
                mode_id = ctl.MODE_NAME_TO_ID.get(mode_name, 0)
                speed = int(speed_row.get_value())
                brightness = int(bright2_row.get_value())
                direction = int(dir_row.get_value())

                r = g = b = 0
                ctext = color_row.get_text().strip()
                if ctext:
                    col = parse_hex_color(ctext)
                    r, g, b = int(col[0:2], 16), int(col[2:4], 16), int(col[4:6], 16)

                payload = ",".join(map(str, [mode_id, speed, brightness, direction, r, g, b])) + "\n"
                write_text(ctl.KB_FOUR_MODE, payload)
                notifier.info("Keyboard effect applied")
            except PermissionError:
                notifier.error("Permission denied: run as root to apply.")
            except Exception as e:
                notifier.error(f"Error: {e}")

        btn_apply_effect.connect("clicked", apply_effect)

        row_apply_effect = Adw.ActionRow(title="Apply effect")
        row_apply_effect.add_suffix(btn_apply_effect)
        row_apply_effect.set_activatable_widget(btn_apply_effect)
        g_effect.add(row_apply_effect)

        # Add groups to page
        page.add(g_static)
        page.add(g_effect)
        return page

    # Power page
    def _build_power_page(self, notifier: StatusNotifier) -> Gtk.Widget:
        page = Adw.PreferencesPage(title="Power")
        group = Adw.PreferencesGroup(title="Platform profile")

        # Load choices
        choices: List[str] = []
        current = ""
        if path_exists(ctl.PLATFORM_PROFILE_CHOICES):
            try:
                raw = read_text(ctl.PLATFORM_PROFILE_CHOICES)
                choices = [c for c in raw.split() if c]
            except Exception:
                choices = []
        if not choices:
            # Reasonable defaults
            choices = ["balanced", "performance", "power-saver"]

        try:
            if path_exists(ctl.PLATFORM_PROFILE):
                current = read_text(ctl.PLATFORM_PROFILE)
        except Exception:
            current = ""

        store = Gtk.StringList.new(choices)
        combo = Adw.ComboRow(title="Profile")
        combo.set_model(store)
        if current in choices:
            combo.set_selected(choices.index(current))
        group.add(combo)

        btn_apply = Gtk.Button(label="Apply profile")
        btn_apply.add_css_class("suggested-action")
        btn_apply.set_halign(Gtk.Align.START)
        btn_apply.set_margin_top(6)
        btn_apply.set_margin_bottom(6)
        btn_apply.set_margin_start(12)

        def apply_profile(_btn):
            try:
                if not path_exists(ctl.PLATFORM_PROFILE):
                    raise FileNotFoundError(f"Missing {ctl.PLATFORM_PROFILE}")
                sel = choices[combo.get_selected()] if choices else None
                if not sel:
                    raise ValueError("No profile selected")
                write_text(ctl.PLATFORM_PROFILE, sel + "\n")
                notifier.info(f"Power profile set to {sel}")
            except PermissionError:
                notifier.error("Permission denied: run as root to apply.")
            except Exception as e:
                notifier.error(f"Error: {e}")

        btn_apply.connect("clicked", apply_profile)

        row_apply = Adw.ActionRow(title="Apply profile")
        row_apply.add_suffix(btn_apply)
        row_apply.set_activatable_widget(btn_apply)
        group.add(row_apply)

        page.add(group)
        return page

    # Fans page
    def _build_fans_page(self, notifier: StatusNotifier) -> Gtk.Widget:
        page = Adw.PreferencesPage(title="Fans")
        group = Adw.PreferencesGroup(title="Manual control")

        auto_row = Adw.SwitchRow(title="Auto (both fans)")
        auto_row.set_active(False)
        group.add(auto_row)

        cpu_row = Adw.SpinRow(title="CPU %", adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1, page_increment=10, value=0))
        gpu_row = Adw.SpinRow(title="GPU %", adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1, page_increment=10, value=0))
        group.add(cpu_row)
        group.add(gpu_row)

        def on_auto_changed(_row, _pspec=None):
            is_auto = auto_row.get_active()
            cpu_row.set_sensitive(not is_auto)
            gpu_row.set_sensitive(not is_auto)

        auto_row.connect("notify::active", on_auto_changed)

        btn_apply = Gtk.Button(label="Apply fan settings")
        btn_apply.add_css_class("suggested-action")
        btn_apply.set_halign(Gtk.Align.START)
        btn_apply.set_margin_top(6)
        btn_apply.set_margin_bottom(6)
        btn_apply.set_margin_start(12)

        def apply_fans(_btn):
            try:
                p = detect_sense_fan_path()
                if not p:
                    raise FileNotFoundError("fan_speed path not found (is the module loaded?)")
                if auto_row.get_active():
                    payload = "0,0\n"  # auto
                else:
                    cpu = int(cpu_row.get_value())
                    gpu = int(gpu_row.get_value())
                    if not (0 <= cpu <= 100 and 0 <= gpu <= 100):
                        raise ValueError("Percentages must be 0-100")
                    # 0 is auto; use at your own risk. Here we treat 0 as auto if chosen.
                    payload = f"{cpu},{gpu}\n"
                write_text(p, payload)
                notifier.info("Fan settings applied")
            except PermissionError:
                notifier.error("Permission denied: run as root to apply.")
            except Exception as e:
                notifier.error(f"Error: {e}")

        btn_apply.connect("clicked", apply_fans)

        row_apply = Adw.ActionRow(title="Apply fan settings")
        row_apply.add_suffix(btn_apply)
        row_apply.set_activatable_widget(btn_apply)
        group.add(row_apply)

        page.add(group)
        return page


def main(argv: Optional[List[str]] = None) -> int:
    app = LinuwuApp()
    return app.run(argv or sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
