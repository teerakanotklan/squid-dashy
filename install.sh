#!/usr/bin/env bash
# ==============================================================================
# Squid Proxy Web Dashboard (squid-dashy) - Automated Installer
# Supported OS: Ubuntu 20.04/22.04/24.04, Debian 11/12, CentOS/RHEL 8/9, Alma/Rocky
# ==============================================================================

set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
echo "  ================================================================"
echo "    🦑 Squid Proxy Web Dashboard (squid-dashy) - Auto Installer   "
echo "  ================================================================"
echo -e "${NC}"

# 1. Check Root Privileges
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run this script with root privileges or use sudo:${NC}"
    echo "  sudo bash install.sh"
    exit 1
fi

# 2. Select Installation Mode
MODE=""
if [ "$1" == "--test" ] || [ "$1" == "1" ]; then
    MODE="1"
elif [ "$1" == "--prod" ] || [ "$1" == "2" ]; then
    MODE="2"
fi

if [ -z "$MODE" ]; then
    echo -e "${BOLD}Please select the installation mode:${NC}"
    echo -e "  ${CYAN}[1]${NC} ${BOLD}Test${NC}       - Run inside Virtual Environment (venv) in foreground"
    echo -e "  ${GREEN}[2]${NC} ${BOLD}Production${NC} - Install and enable background Systemd Service"
    echo ""
    
    # Check if input is from terminal or pipe
    if [ -t 0 ]; then
        read -rp "Enter choice [1 or 2] (default 2): " USER_INPUT
    elif [ -e /dev/tty ]; then
        read -rp "Enter choice [1 or 2] (default 2): " USER_INPUT < /dev/tty
    else
        USER_INPUT="2"
    fi

    case "$USER_INPUT" in
        1)
            MODE="1"
            ;;
        *)
            MODE="2"
            ;;
    esac
fi

if [ "$MODE" == "1" ]; then
    echo -e "${MAGENTA}${BOLD}>> Selected mode: [1] Test (Virtual Env)${NC}\n"
else
    echo -e "${GREEN}${BOLD}>> Selected mode: [2] Production (Systemd Service)${NC}\n"
fi

# 3. Determine Installation Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/app.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    INSTALL_DIR="$SCRIPT_DIR"
    echo -e "${GREEN}[INFO] Project files detected in current directory: ${BOLD}$INSTALL_DIR${NC}"
else
    INSTALL_DIR="/opt/squid-dashy"
    echo -e "${YELLOW}[INFO] Installing project to: ${BOLD}$INSTALL_DIR${NC}"
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}[INFO] Directory $INSTALL_DIR already exists. Pulling latest updates...${NC}"
        cd "$INSTALL_DIR"
        git pull || true
    else
        echo -e "${GREEN}[INFO] Cloning repository from GitHub...${NC}"
        git clone https://github.com/teerakanotklan/squid-dashy.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

# 4. Detect OS & Package Manager
echo -e "\n${BLUE}[1/4] Checking and installing system dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-full python3-pip curl git
elif command -v dnf &> /dev/null; then
    dnf install -y python3 python3-pip git curl
elif command -v yum &> /dev/null; then
    yum install -y python3 python3-pip git curl
else
    echo -e "${RED}[ERROR] Unsupported package manager (apt, dnf, yum not found)${NC}"
    exit 1
fi

# 5. Setup Python Virtual Environment (venv)
echo -e "\n${BLUE}[2/4] Setting up Python Virtual Environment (venv)...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    echo -e "${GREEN}[OK] Created virtual environment at $INSTALL_DIR/venv${NC}"
else
    echo -e "${YELLOW}[INFO] Virtual environment already exists. Skipping creation.${NC}"
fi

# 6. Install Dependencies inside venv
echo -e "\n${BLUE}[3/4] Installing Python dependencies (FastAPI, Uvicorn, WebSockets)...${NC}"
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# Verify websockets & uvicorn
if "$INSTALL_DIR/venv/bin/python" -c "import fastapi, uvicorn, websockets" &> /dev/null; then
    echo -e "${GREEN}[OK] Python dependencies verified (including WebSocket support)${NC}"
else
    echo -e "${RED}[ERROR] Failed to verify Python dependencies. Please inspect logs above.${NC}"
    exit 1
fi

# Detect Local IP Address
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="<SERVER_IP>"
fi

# 7. Execute according to chosen mode
if [ "$MODE" == "1" ]; then
    echo -e "\n${BLUE}[4/4] Starting server in Test Mode...${NC}"
    echo -e "\n${GREEN}${BOLD}"
    echo "  ================================================================"
    echo "    🚀 Test Mode Ready!                                           "
    echo "  ================================================================"
    echo -e "${NC}"
    echo -e "  🌐 Access the web dashboard at:"
    echo -e "     ${BOLD}${CYAN}http://$SERVER_IP:8080${NC} or ${BOLD}${CYAN}http://localhost:8080${NC}"
    echo ""
    echo -e "  ⚠️  ${YELLOW}Press Ctrl + C to stop the test server when finished.${NC}"
    echo "  ================================================================"
    echo ""

    # Run app directly in foreground
    "$INSTALL_DIR/venv/bin/python" app.py

else
    # Production: Setup Systemd Service
    echo -e "\n${BLUE}[4/4] Configuring and starting Systemd Service (squid-dashy.service)...${NC}"
    SERVICE_FILE="/etc/systemd/system/squid-dashy.service"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Squid Proxy Web Dashboard (squid-dashy)
After=network.target squid.service
Wants=squid.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=always
RestartSec=5
Environment=DASHBOARD_HOST=0.0.0.0
Environment=DASHBOARD_PORT=8080
Environment=SQUID_HOST=127.0.0.1
Environment=SQUID_PORT=3128
Environment=SQUID_ACCESS_LOG=/var/log/squid/access.log

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable squid-dashy.service
    systemctl restart squid-dashy.service

    sleep 2

    echo -e "\n${GREEN}${BOLD}"
    echo "  ================================================================"
    echo "    🎉 Production Service Installation Completed!                "
    echo "  ================================================================"
    echo -e "${NC}"
    if systemctl is-active --quiet squid-dashy.service; then
        echo -e "  Service Status: ${GREEN}${BOLD}● Active (Running)${NC}"
    else
        echo -e "  Service Status: ${YELLOW}Starting... Check status using: journalctl -u squid-dashy -f${NC}"
    fi
    echo ""
    echo -e "  🌐 Access the web dashboard at:"
    echo -e "     ${BOLD}${CYAN}http://$SERVER_IP:8080${NC} or ${BOLD}${CYAN}http://localhost:8080${NC}"
    echo ""
    echo -e "  📌 Useful Service Management Commands:"
    echo -e "     - Check status:  ${YELLOW}systemctl status squid-dashy${NC}"
    echo -e "     - View logs:     ${YELLOW}journalctl -u squid-dashy -f${NC}"
    echo -e "     - Restart:       ${YELLOW}systemctl restart squid-dashy${NC}"
    echo -e "     - Stop service:  ${YELLOW}systemctl stop squid-dashy${NC}"
    echo ""
    echo -e "  📁 Project Directory: ${BOLD}$INSTALL_DIR${NC}"
    echo "  ================================================================"
    echo ""
fi
