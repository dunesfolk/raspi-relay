#!/bin/bash
# Install raspi-relay on Raspberry Pi OS (Bookworm or newer).
# Usage:  sudo ./scripts/install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root:  sudo ./scripts/install.sh" >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR=/opt/raspi-relay

if grep -q " / overlay " /proc/mounts; then
    echo "The overlay (read-only) file system is ON. Changes would be lost on reboot." >&2
    echo "Turn it off first:  sudo raspi-config -> Performance Options -> Overlay File System" >&2
    exit 1
fi

if [ -d /boot/firmware ]; then
    BOOT_DIR=/boot/firmware
else
    BOOT_DIR=/boot
fi

echo "==> Installing packages"
apt-get update
apt-get install -y python3 python3-gpiozero network-manager

echo "==> Copying program to $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$REPO_DIR/src/raspi_relay" "$INSTALL_DIR/"
chmod 755 "$INSTALL_DIR/raspi_relay/"*.py

if [ -f "$BOOT_DIR/raspi-relay.conf" ]; then
    echo "==> Keeping existing $BOOT_DIR/raspi-relay.conf"
else
    echo "==> Creating $BOOT_DIR/raspi-relay.conf"
    cp "$REPO_DIR/config/raspi-relay.conf" "$BOOT_DIR/raspi-relay.conf"
fi

echo "==> Keeping logs in RAM only (less SD card wear)"
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/raspi-relay.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=8M
EOF
systemctl restart systemd-journald

echo "==> Installing services"
cp "$REPO_DIR/systemd/raspi-relay-network.service" /etc/systemd/system/
cp "$REPO_DIR/systemd/raspi-relay.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable raspi-relay-network.service raspi-relay.service
# Not started here on purpose: applying network settings now could cut off
# the SSH session. Everything starts cleanly on the next boot.

echo
echo "Done. Settings file: $BOOT_DIR/raspi-relay.conf"
echo "Edit it if needed, then reboot:  sudo reboot"
echo "After reboot, check:  systemctl status raspi-relay"
