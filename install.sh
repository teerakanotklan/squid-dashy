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
    echo -e "${RED}[ERROR] กรุณารันสคริปต์นี้ด้วยสิทธิ์ root หรือใช้ sudo:${NC}"
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
    echo -e "${BOLD}กรุณาเลือกรูปแบบการทำงาน:${NC}"
    echo -e "  ${CYAN}[1]${NC} ${BOLD}ทดสอบ (Test)${NC}      - รันแบบ Virtual Env (venv) บน Terminal ทันที"
    echo -e "  ${GREEN}[2]${NC} ${BOLD}โปรดักชัน (Production)${NC} - ติดตั้งเป็น Systemd Service รันเบื้องหลังอัตโนมัติ"
    echo ""
    
    # Check if input is from terminal or pipe
    if [ -t 0 ]; then
        read -rp "เลือกหมายเลข [1 หรือ 2] (ค่าเริ่มต้น 2): " USER_INPUT
    elif [ -e /dev/tty ]; then
        read -rp "เลือกหมายเลข [1 หรือ 2] (ค่าเริ่มต้น 2): " USER_INPUT < /dev/tty
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
    echo -e "${MAGENTA}${BOLD}>> เลือกโหมด: [1] ทดสอบ (Test - Virtual Env)${NC}\n"
else
    echo -e "${GREEN}${BOLD}>> เลือกโหมด: [2] โปรดักชัน (Production - Systemd Service)${NC}\n"
fi

# 3. Determine Installation Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/app.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    INSTALL_DIR="$SCRIPT_DIR"
    echo -e "${GREEN}[INFO] ตรวจพบไฟล์โปรเจกต์ในไดเรกทอรีปัจจุบัน: ${BOLD}$INSTALL_DIR${NC}"
else
    INSTALL_DIR="/opt/squid-dashy"
    echo -e "${YELLOW}[INFO] ไม่พบไฟล์โปรเจกต์ในไดเรกทอรีปัจจุบัน จะทำการติดตั้งที่: ${BOLD}$INSTALL_DIR${NC}"
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}[INFO] โฟลเดอร์ $INSTALL_DIR มีอยู่แล้ว กำลังอัปเดตโค้ด...${NC}"
        cd "$INSTALL_DIR"
        git pull || true
    else
        echo -e "${GREEN}[INFO] กำลัง Clone โค้ดจาก GitHub...${NC}"
        git clone https://github.com/teerakanotklan/squid-dashy.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

# 4. Detect OS & Package Manager
echo -e "\n${BLUE}[1/4] กำลังตรวจสอบและติดตั้ง System Dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-full python3-pip curl git
elif command -v dnf &> /dev/null; then
    dnf install -y python3 python3-pip git curl
elif command -v yum &> /dev/null; then
    yum install -y python3 python3-pip git curl
else
    echo -e "${RED}[ERROR] ไม่พบ package manager ที่รองรับ (apt, dnf, yum)${NC}"
    exit 1
fi

# 5. Setup Python Virtual Environment (venv)
echo -e "\n${BLUE}[2/4] กำลังสร้างและกำหนดค่า Python Virtual Environment (venv)...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    echo -e "${GREEN}[OK] สร้าง venv สำเร็จที่ $INSTALL_DIR/venv${NC}"
else
    echo -e "${YELLOW}[INFO] ตรวจพบ venv อยู่แล้ว ข้ามการสร้างใหม่${NC}"
fi

# 6. Install Dependencies inside venv
echo -e "\n${BLUE}[3/4] กำลังติดตั้ง Python Dependencies (FastAPI, Uvicorn, WebSockets)...${NC}"
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# Verify websockets & uvicorn
if "$INSTALL_DIR/venv/bin/python" -c "import fastapi, uvicorn, websockets" &> /dev/null; then
    echo -e "${GREEN}[OK] ติดตั้ง Python dependencies ครบถ้วน (รวม WebSocket support)${NC}"
else
    echo -e "${RED}[ERROR] ตรวจพบปัญหาในการติดตั้ง dependencies กรุณาตรวจสอบ logs ด้านบน${NC}"
    exit 1
fi

# Detect Local IP Address
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="<SERVER_IP>"
fi

# 7. Execute according to chosen mode
if [ "$MODE" == "1" ]; then
    echo -e "\n${BLUE}[4/4] เตรียมเปิดใช้งานเซิร์ฟเวอร์ในโหมดทดสอบ...${NC}"
    echo -e "\n${GREEN}${BOLD}"
    echo "  ================================================================"
    echo "    🚀 พร้อมเริ่มการทดสอบ (Test Mode)                             "
    echo "  ================================================================"
    echo -e "${NC}"
    echo -e "  🌐 เปิดใช้งานหน้าแดชบอร์ดได้ที่:"
    echo -e "     ${BOLD}${CYAN}http://$SERVER_IP:8080${NC} หรือ ${BOLD}${CYAN}http://localhost:8080${NC}"
    echo ""
    echo -e "  ⚠️  ${YELLOW}กด Ctrl + C เพื่อหยุดการทำงานเมื่อทดสอบเสร็จสิ้น${NC}"
    echo "  ================================================================"
    echo ""

    # Run app directly in foreground
    "$INSTALL_DIR/venv/bin/python" app.py

else
    # Production: Setup Systemd Service
    echo -e "\n${BLUE}[4/4] กำลังสร้างและตั้งค่า Systemd Service (squid-dashy.service)...${NC}"
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
    echo "    🎉 ติดตั้ง Service โปรดักชัน (Production Mode) สำเร็จ!       "
    echo "  ================================================================"
    echo -e "${NC}"
    if systemctl is-active --quiet squid-dashy.service; then
        echo -e "  สถานะ Service: ${GREEN}${BOLD}● Active (Running)${NC}"
    else
        echo -e "  สถานะ Service: ${YELLOW}กำลังเริ่มต้น หรือกรุณาตรวจสอบด้วย journalctl -u squid-dashy${NC}"
    fi
    echo ""
    echo -e "  🌐 เปิดใช้งานหน้าแดชบอร์ดได้ที่:"
    echo -e "     ${BOLD}${CYAN}http://$SERVER_IP:8080${NC} หรือ ${BOLD}${CYAN}http://localhost:8080${NC}"
    echo ""
    echo -e "  📌 คำสั่งที่มีประโยชน์ในการจัดการ Service:"
    echo -e "     - ดูสถานะ:      ${YELLOW}systemctl status squid-dashy${NC}"
    echo -e "     - ดูบันทึกการรัน: ${YELLOW}journalctl -u squid-dashy -f${NC}"
    echo -e "     - รีสตาร์ท:     ${YELLOW}systemctl restart squid-dashy${NC}"
    echo -e "     - หยุดการทำงาน:  ${YELLOW}systemctl stop squid-dashy${NC}"
    echo ""
    echo -e "  📁 ตำแหน่งโปรเจกต์: ${BOLD}$INSTALL_DIR${NC}"
    echo "  ================================================================"
    echo ""
fi
