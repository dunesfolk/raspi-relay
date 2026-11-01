#!/usr/bin/env python3
"""Apply the [network] section of raspi-relay.conf using NetworkManager (nmcli).

Runs once at every boot (raspi-relay-network.service). The config file is the
source of truth, so this works with the read-only overlay file system: any
changes made here live in RAM and are re-created on the next boot.

If the config is invalid, the interface falls back to DHCP so the Pi stays
reachable.
"""

import argparse
import ipaddress
import logging
import shutil
import subprocess
import sys

from config import load_config

CON_NAME = "raspi-relay-eth"
log = logging.getLogger("raspi-relay-network")


class ConfigError(Exception):
    pass


def _iface(value, version, field):
    try:
        addr = ipaddress.ip_interface(value.strip())
    except ValueError:
        raise ConfigError(f"{field}: '{value}' is not a valid address/prefix")
    if addr.version != version:
        raise ConfigError(f"{field}: '{value}' is not IPv{version}")
    if "/" not in value:
        raise ConfigError(f"{field}: add a prefix length, e.g. {value}/24")
    return str(addr)


def _addr(value, version, field):
    try:
        addr = ipaddress.ip_address(value.strip())
    except ValueError:
        raise ConfigError(f"{field}: '{value}' is not a valid address")
    if addr.version != version:
        raise ConfigError(f"{field}: '{value}' is not IPv{version}")
    return str(addr)


def _dns_list(value, version, field):
    items = [v for v in value.replace(" ", ",").split(",") if v.strip()]
    return ",".join(_addr(v, version, field) for v in items)


def build_settings(net):
    """Return a list of nmcli 'setting value' pairs for the connection."""
    s = []

    m4 = net.get("ipv4_method", "dhcp").strip().lower()
    if m4 == "dhcp":
        s += ["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "",
              "ipv4.dns", ""]
    elif m4 == "static":
        addr = _iface(net.get("ipv4_address", ""), 4, "ipv4_address")
        gw = net.get("ipv4_gateway", "").strip()
        gw = _addr(gw, 4, "ipv4_gateway") if gw else ""
        dns = _dns_list(net.get("ipv4_dns", ""), 4, "ipv4_dns")
        s += ["ipv4.method", "manual", "ipv4.addresses", addr,
              "ipv4.gateway", gw, "ipv4.dns", dns]
    else:
        raise ConfigError(f"ipv4_method must be dhcp or static, not '{m4}'")

    m6 = net.get("ipv6_method", "auto").strip().lower()
    if m6 in ("auto", "dhcp"):
        s += ["ipv6.method", "auto", "ipv6.addresses", "", "ipv6.gateway", "",
              "ipv6.dns", ""]
    elif m6 == "static":
        addr = _iface(net.get("ipv6_address", ""), 6, "ipv6_address")
        gw = net.get("ipv6_gateway", "").strip()
        gw = _addr(gw, 6, "ipv6_gateway") if gw else ""
        dns = _dns_list(net.get("ipv6_dns", ""), 6, "ipv6_dns")
        s += ["ipv6.method", "manual", "ipv6.addresses", addr,
              "ipv6.gateway", gw, "ipv6.dns", dns]
    elif m6 == "disabled":
        s += ["ipv6.method", "disabled", "ipv6.addresses", "", "ipv6.gateway", "",
              "ipv6.dns", ""]
    else:
        raise ConfigError(f"ipv6_method must be auto, static or disabled, not '{m6}'")

    return s


def dhcp_settings():
    return ["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "",
            "ipv4.dns", "", "ipv6.method", "auto", "ipv6.addresses", "",
            "ipv6.gateway", "", "ipv6.dns", ""]


def run(cmd, dry_run, check=True):
    log.info("$ %s", " ".join(repr(c) if (c == "" or " " in c) else c for c in cmd))
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def connection_exists(dry_run):
    if dry_run:
        return False
    out = subprocess.run(["nmcli", "-t", "-f", "NAME", "connection", "show"],
                         capture_output=True, text=True).stdout
    return CON_NAME in out.splitlines()


def apply(iface, settings, dry_run):
    common = ["connection.interface-name", iface,
              "connection.autoconnect", "yes",
              # Higher than the default "Wired connection 1", so ours wins
              "connection.autoconnect-priority", "100"]
    if connection_exists(dry_run):
        run(["nmcli", "connection", "modify", CON_NAME] + common + settings, dry_run)
    else:
        run(["nmcli", "connection", "add", "type", "ethernet",
             "con-name", CON_NAME] + common + settings, dry_run)
    # Bring it up. No cable / no DHCP server is not fatal: NetworkManager keeps
    # retrying because autoconnect is on.
    r = run(["nmcli", "--wait", "30", "connection", "up", CON_NAME], dry_run, check=False)
    if r.returncode != 0:
        log.warning("connection up failed (will keep retrying): %s",
                    (r.stderr or r.stdout).strip())


def main():
    ap = argparse.ArgumentParser(description="Apply raspi-relay network config")
    ap.add_argument("--config", help="config file path")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the nmcli commands without running them")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)s %(message)s")

    if not args.dry_run and not shutil.which("nmcli"):
        log.error("nmcli not found. Raspberry Pi OS Bookworm or newer is required.")
        return 1

    cfg, path = load_config(args.config)
    log.info("config: %s", path or "(defaults)")
    net = cfg["network"]
    iface = net.get("interface", "eth0").strip() or "eth0"

    try:
        settings = build_settings(net)
    except ConfigError as e:
        log.error("invalid network config: %s -> using DHCP instead", e)
        settings = dhcp_settings()

    try:
        apply(iface, settings, args.dry_run)
    except subprocess.CalledProcessError as e:
        log.error("nmcli failed: %s", (e.stderr or e.stdout or "").strip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
