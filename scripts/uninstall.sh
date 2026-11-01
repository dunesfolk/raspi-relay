#!/bin/bash
# Remove raspi-relay. The settings file on the boot partition is kept.
# Usage:  sudo ./scripts/uninstall.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root:  sudo ./scripts/uninstall.sh" >&2
    exit 1
fi

systemctl disable --now raspi-relay.service raspi-relay-network.service 2>/dev/null || true
rm -f /etc/systemd/system/raspi-relay.service /etc/systemd/system/raspi-relay-network.service
systemctl daemon-reload
rm -rf /opt/raspi-relay
rm -f /etc/systemd/journald.conf.d/raspi-relay.conf

# Remove our network profile; the default "Wired connection" (DHCP) takes over
if command -v nmcli >/dev/null; then
    nmcli connection delete raspi-relay-eth 2>/dev/null || true
fi

echo "Removed. (raspi-relay.conf on the boot partition was left in place.)"
