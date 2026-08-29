#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════
#  Room Entry & Lab Management System — Clean Uninstaller
# ═════════════════════════════════════════════════════════════════════

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash uninstall.sh"
    exit 1
fi

SERVICE_NAME="student-entry"
INSTALL_DIR="/opt/student_entry"

echo "Stopping and disabling $SERVICE_NAME service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

echo "Removing CLI commands..."
rm -f "/usr/local/bin/student-entry"

read -p "Do you want to keep the database backups? [Y/n]: " KEEP_DB
if [[ "$KEEP_DB" =~ ^[Nn]$ ]]; then
    echo "Removing application directory ($INSTALL_DIR)..."
    rm -rf "$INSTALL_DIR"
else
    echo "Preserving database directory at $INSTALL_DIR/data..."
    find "$INSTALL_DIR" -maxdepth 1 ! -name 'data' ! -name '.' -exec rm -rf {} +
fi

echo "✓ Uninstallation complete."
