#!/bin/bash
# Installation script for storage-automount service
# Run with: sudo bash install-service.sh

set -e

echo "========================================="
echo "Storage Auto-Mount Service Installer"
echo "========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash install-service.sh)"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "Installing storage-automount service..."

# Create installation directory
echo "→ Creating /opt/storage-automount directory..."
mkdir -p /opt/storage-automount

# Copy Python script
echo "→ Copying storage-automount-enhanced.py..."
cp "$SCRIPT_DIR/storage-automount-enhanced.py" /opt/storage-automount/
chmod +x /opt/storage-automount/storage-automount-enhanced.py

# Copy systemd service file
echo "→ Installing systemd service..."
cp "$SCRIPT_DIR/storage-automount.service" /etc/systemd/system/

# Reload systemd
echo "→ Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "→ Enabling storage-automount service..."
systemctl enable storage-automount.service

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "To start the service now:"
echo "  sudo systemctl start storage-automount"
echo ""
echo "To check service status:"
echo "  sudo systemctl status storage-automount"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u storage-automount -f"
echo ""
echo "To uninstall:"
echo "  sudo systemctl stop storage-automount"
echo "  sudo systemctl disable storage-automount"
echo "  sudo rm /etc/systemd/system/storage-automount.service"
echo "  sudo rm -rf /opt/storage-automount"
echo "  sudo systemctl daemon-reload"
echo ""
