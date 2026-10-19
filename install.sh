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

# 2. Determine Installation Directory
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

# 3. Detect OS & Package Manager
echo -e "\n${BLUE}[1/5] กำลังตรวจสอบและติดตั้ง System Dependencies...${NC}"
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

# 4. Setup Python Virtual Environment (venv) to prevent PEP 668 issues
echo -e "\n${BLUE}[2/5] กำลังสร้างและกำหนดค่า Python Virtual Environment (venv)...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    echo -e "${GREEN}[OK] สร้าง venv สำเร็จที่ $INSTALL_DIR/venv${NC}"
else
    echo -e "${YELLOW}[INFO] ตรวจพบ venv อยู่แล้ว ข้ามการสร้างใหม่${NC}"
fi

# 5. Install Dependencies inside venv
echo -e "\n${BLUE}[3/5] กำลังติดตั้ง Python Dependencies (FastAPI, Uvicorn, WebSockets)...${NC}"
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# Verify websockets & uvicorn
if "$INSTALL_DIR/venv/bin/python" -c "import fastapi, uvicorn, websockets" &> /dev/null; then
    echo -e "${GREEN}[OK] ติดตั้ง Python dependencies ครบถ้วน (รวม WebSocket support)${NC}"
else
    echo -e "${RED}[ERROR] ตรวจพบปัญหาในการติดตั้ง dependencies กรุณาตรวจสอบ logs ด้านบน${NC}"
    exit 1
fi

# 6. Configure Systemd Service
echo -e "\n${BLUE}[4/5] กำลังสร้างและตั้งค่า Systemd Service (squid-dashy.service)...${NC}"
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

# 7. Check Service Status
echo -e "\n${BLUE}[5/5] กำลังตรวจสอบสถานะการทำงานของ Service...${NC}"
sleep 2

if systemctl is-active --quiet squid-dashy.service; then
    echo -e "${GREEN}[OK] squid-dashy.service ทำงานเรียบร้อยแล้ว (Active: Running)${NC}"
else
    echo -e "${RED}[WARNING] Service อาจยังไม่เริ่มทำงาน สามารถตรวจสอบสาเหตุได้ด้วย: journalctl -u squid-dashy -n 20${NC}"
fi

# Detect Local IP Address
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="<SERVER_IP>"
fi

echo -e "\n${GREEN}${BOLD}"
echo "  ================================================================"
echo "    🎉 ติดตั้ง Squid Proxy Web Dashboard (squid-dashy) สำเร็จ!   "
echo "  ================================================================"
echo -e "${NC}"
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
