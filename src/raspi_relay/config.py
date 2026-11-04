"""Shared config loading for raspi-relay."""

import configparser
import os

DEFAULT_CONFIG_PATHS = (
    "/boot/firmware/raspi-relay.conf",  # Raspberry Pi OS Bookworm and newer
    "/boot/raspi-relay.conf",           # older layout
)

DEFAULTS = {
    "network": {
        "interface": "eth0",
        "ipv4_method": "dhcp",
        "ipv4_address": "",
        "ipv4_gateway": "",
        "ipv4_dns": "",
        "ipv6_method": "auto",
        "ipv6_address": "",
        "ipv6_gateway": "",
        "ipv6_dns": "",
    },
    "relay": {
        "gpio_pin": "17",
        "active_high": "true",
        "contact": "nc",
        "break_seconds": "1.0",
    },
    "server": {
        "port": "8080",
        "web_port": "80",
        "web_page": "true",
        "bind": "::",
    },
}


def find_config(path=None):
    """Return the config path to use (explicit path wins)."""
    if path:
        return path
    for candidate in DEFAULT_CONFIG_PATHS:
        if os.path.exists(candidate):
            return candidate
    return None


def load_config(path=None):
    """Load the config. Missing file or keys fall back to DEFAULTS."""
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read_dict(DEFAULTS)
    path = find_config(path)
    if path:
        # utf-8-sig: tolerate the BOM that Windows Notepad may add
        with open(path, encoding="utf-8-sig") as f:
            cp.read_file(f)
    # Older configs used "pulse_seconds"; honour it if break_seconds is not set
    relay = cp["relay"]
    if "pulse_seconds" in relay and relay["break_seconds"] == DEFAULTS["relay"]["break_seconds"]:
        relay["break_seconds"] = relay["pulse_seconds"]
    return cp, path
