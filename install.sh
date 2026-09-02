#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════
#  Room Entry & Lab Management System — One-Line Automated Installer
#  Compatible with: Raspberry Pi OS, Debian 11/12, Ubuntu 20.04/22.04/24.04
# ═════════════════════════════════════════════════════════════════════

set -e

# ── Colors ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Banner ────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}"
cat << "EOF"
  ____                         _____       _              
 |  _ \ ___   ___  _ __ ___   | ____|_ __ | |_ _ __ _   _ 
 | |_) / _ \ / _ \| '_ ` _ \  |  _| | '_ \| __| '__| | | |
 |  _ < (_) | (_) | | | | | | | |___| | | | |_| |  | |_| |
 |_| \_\___/ \___/|_| |_| |_| |_____|_| |_|\__|_|   \__, |
                                                    |___/ 
      Configurable Room Entry & Lab Management Platform
EOF
echo -e "${NC}"

# ── Check Root Privileges ─────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be run as root or with sudo.${NC}"
    echo -e "Please run: ${BOLD}sudo bash install.sh${NC}"
    exit 1
fi

# Detect calling user
REAL_USER=${SUDO_USER:-$(whoami)}
REAL_HOME=$(eval echo "~$REAL_USER")

INSTALL_DIR="/opt/student_entry"
SERVICE_NAME="student-entry"
PORT=8000

echo -e "${BLUE}[1/6]${NC} ${BOLD}Checking system prerequisites...${NC}"
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv sqlite3 git curl
else
    echo -e "${YELLOW}[WARN] apt-get not detected. Ensure Python 3.10+, pip, and sqlite3 are installed.${NC}"
fi

echo -e "${BLUE}[2/6]${NC} ${BOLD}Installing application files to ${INSTALL_DIR}...${NC}"
mkdir -p "$INSTALL_DIR"

# If running from inside the cloned git repository, copy files; otherwise clone from GitHub
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if [ -f "$CURRENT_DIR/main.py" ] && [ -f "$CURRENT_DIR/requirements.txt" ]; then
    echo -e "      Copying local repository files..."
    cp -r "$CURRENT_DIR/"* "$INSTALL_DIR/"
    cp -r "$CURRENT_DIR/".[!.]* "$INSTALL_DIR/" 2>/dev/null || true
else
    echo -e "      Cloning latest release from GitHub..."
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" pull --quiet
    else
        git clone --quiet https://github.com/VishwatejaPalli/student_entry.git "$INSTALL_DIR"
    fi
fi

# Ensure data directory and .env exist
mkdir -p "$INSTALL_DIR/data"
if [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
fi

echo -e "${BLUE}[3/6]${NC} ${BOLD}Setting up Python virtual environment...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# Fix permissions
chown -R "$REAL_USER:$REAL_USER" "$INSTALL_DIR"

echo -e "${BLUE}[4/6]${NC} ${BOLD}Configuring systemd background service (${SERVICE_NAME}.service)...${NC}"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Room Entry & Lab Attendance System
After=network.target

[Service]
Type=simple
User=${REAL_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" --quiet
systemctl restart "${SERVICE_NAME}.service"

echo -e "${BLUE}[5/6]${NC} ${BOLD}Installing CLI management command (/usr/local/bin/student-entry)...${NC}"
cat > "/usr/local/bin/student-entry" << 'EOF'
#!/usr/bin/env bash
SERVICE="student-entry"
INSTALL_DIR="/opt/student_entry"

case "$1" in
    start)
        sudo systemctl start "$SERVICE"
        echo "✓ Room Entry service started"
        ;;
    stop)
        sudo systemctl stop "$SERVICE"
        echo "✓ Room Entry service stopped"
        ;;
    restart)
        sudo systemctl restart "$SERVICE"
        echo "✓ Room Entry service restarted"
        ;;
    status)
        sudo systemctl status "$SERVICE"
        ;;
    logs)
        sudo journalctl -u "$SERVICE" -f
        ;;
    backup)
        BACKUP_FILE="${INSTALL_DIR}/data/backup_$(date +%Y%m%d_%H%M%S).db"
        sqlite3 "${INSTALL_DIR}/data/student_entry.db" ".backup '$BACKUP_FILE'"
        echo "✓ Database backup saved to: $BACKUP_FILE"
        ;;
    update)
        echo "Updating Room Entry System..."
        sudo systemctl stop "$SERVICE"
        git -C "$INSTALL_DIR" pull
        "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
        sudo systemctl start "$SERVICE"
        echo "✓ Updated and restarted successfully!"
        ;;
    *)
        echo "Usage: student-entry {start|stop|restart|status|logs|backup|update}"
        exit 1
        ;;
esac
EOF
chmod +x "/usr/local/bin/student-entry"

# Optional Desktop Shortcut if desktop folder exists
if [ -d "$REAL_HOME/Desktop" ]; then
    cat > "$REAL_HOME/Desktop/Room-Entry.desktop" << EOF
[Desktop Entry]
Version=1.0
Name=Room Entry System
Comment=Open Lab Attendance Terminal
Exec=chromium-browser --app=http://localhost:${PORT} || xdg-open http://localhost:${PORT}
Icon=accessories-dictionary
Terminal=false
Type=Application
Categories=Education;Development;
EOF
    chmod +x "$REAL_HOME/Desktop/Room-Entry.desktop"
    chown "$REAL_USER:$REAL_USER" "$REAL_HOME/Desktop/Room-Entry.desktop"
fi

echo -e "${BLUE}[6/6]${NC} ${BOLD}Detecting network addresses...${NC}"
IP_ADDRS=$(hostname -I 2>/dev/null || echo "127.0.0.1")

echo -e "\n${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓ Installation Completed Successfully!${NC}"
echo -e "${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${NC}"
echo -e "\nAccess the web application in any browser on your network at:"
echo -e "  • ${BOLD}Local Machine:${NC}  ${CYAN}http://localhost:${PORT}${NC}"
for ip in $IP_ADDRS; do
    if [ "$ip" != "127.0.0.1" ]; then
        echo -e "  • ${BOLD}LAN Access:${NC}     ${CYAN}http://${ip}:${PORT}${NC}"
    fi
done

echo -e "\n${BOLD}Quick Management Commands:${NC}"
echo -e "  • Check service status:   ${YELLOW}student-entry status${NC}"
echo -e "  • View live logs:         ${YELLOW}student-entry logs${NC}"
echo -e "  • Restart service:        ${YELLOW}student-entry restart${NC}"
echo -e "  • Backup database:        ${YELLOW}student-entry backup${NC}"
echo -e "  • Update system:          ${YELLOW}student-entry update${NC}\n"
