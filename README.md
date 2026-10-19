# 🦑 Squid Proxy Web Dashboard (squid-dashy)

เว็บแดชบอร์ดสำหรับติดตามและวิเคราะห์สถานะการทำงานของ **Squid Proxy** แบบเรียลไทม์ (Real-time Web Monitoring & Analytics) ออกแบบให้ทันสมัย ใช้งานง่าย มีประสิทธิภาพสูง และติดตั้งได้รวดเร็ว

---

## ✨ ความสามารถหลัก (Features)

1. **สถิติและประสิทธิภาพแคช (Cache Performance Metrics):**
   - **Request Hit Ratio (%)**: สัดส่วนคำขอที่ดึงข้อมูลจากแคชสำเร็จโดยไม่ต้องออกอินเทอร์เน็ต
   - **Byte Hit Ratio (%)**: สัดส่วนปริมาณข้อมูลและแบนด์วิดท์ที่ประหยัดได้ (Bandwidth Saved)
   - **Throughput & Request Rate**: วัดอัตราคำขอต่อวินาที (Requests/sec) และปริมาณทราฟฟิก (KB/s, MB/s)
   - **ทรัพยากรระบบ**: อัตราการใช้งาน RAM Cache, Disk Swap Cache, CPU Usage และ File Descriptors

2. **กราฟิกแสดงผลเรียลไทม์ (Real-time Visualizations):**
   - กราฟเส้น Throughput Timeline แสดงอัตราคำขอและแบนด์วิดท์ต่อเนื่อง
   - กราฟโดนัทจำแนกสัดส่วน Hits, Misses และ Denied/Blocked requests

3. **Live Access Log Streamer & Filter:**
   - อ่านและแสดงผลไฟล์ `access.log` แบบสดๆ ผ่าน WebSocket (`/ws/live`)
   - มีช่องค้นหาแบบเรียลไทม์ตาม Client IP, Domain, URL หรือ Result Code
   - ฟิลเตอร์คัดกรองเฉพาะ Hits, Misses หรือ Blocked (403 Forbidden)
   - ปุ่มกดพักหน้าจอ (Pause/Resume) สำหรับตรวจสอบ Log ที่น่าสงสัย

4. **การวิเคราะห์ข้อมูลผู้ใช้งาน (Traffic Analytics):**
   - **Top Client IPs**: ตรวจดูว่าเครื่องลูกข่าย IP ใดใช้คำขอและแบนด์วิดท์สูงสุด พร้อมอัตรา Hit Ratio รายเครื่อง
   - **Top Domains**: จัดอันดับเว็บไซต์ที่ถูกเรียกใช้งานบ่อยที่สุด และสถิติการถูกบล็อก

5. **เครื่องมือเชื่อมต่อ Squid Cache Manager:**
   - รองรับการดึงข้อมูลและสถิติเชิงลึกผ่าน `mgr:info`, `mgr:5min`, `mgr:utilization`, `mgr:client_list`, `mgr:ipcache`, `mgr:counters`
   - มีปุ่มคลิกคัดลอกข้อความผลลัพธ์ (Copy to Clipboard)

---

## 🚀 วิธีการติดตั้งและเริ่มใช้งาน (Installation Guide)

### ⚡ วิธีที่ 1: ติดตั้งอัตโนมัติในคำสั่งเดียว (Automated One-Liner — แนะนำ)

รันคำสั่งด้านล่างนี้บนเซิร์ฟเวอร์ (Ubuntu / Debian / CentOS / AlmaLinux / Rocky):

```bash
curl -sSL https://raw.githubusercontent.com/teerakanotklan/squid-dashy/main/install.sh | sudo bash
```

> 💡 **หรือหากดาวน์โหลดโค้ดมาแล้ว:**
> ```bash
> cd ~/squid-dashy
> sudo bash install.sh
> ```

สคริปต์จะมีเมนูให้เลือก 2 รูปแบบ:
- **`[1] ทดสอบ (Test)`**: สร้าง `venv`, ติดตั้ง dependencies และรันเซิร์ฟเวอร์บน Terminal ทันที เหมาะสำหรับทดสอบดูหน้าเว็บก่อน
- **`[2] โปรดักชัน (Production)`**: ติดตั้งและสร้าง Linux **Systemd Service** ให้อัตโนมัติ รันเบื้องหลังและเปิดใช้งานตอนบูตระบบ

*(สามารถระบุล่วงหน้าได้ด้วย `sudo bash install.sh --test` หรือ `sudo bash install.sh --prod`)*

---

### 🛠️ วิธีที่ 2: ติดตั้งด้วยตนเองทีละขั้นตอน (Manual Installation with venv)

> ⚠️ **สำหรับ Ubuntu 24.04 / Debian 12 (Python 3.12+):**  
> ระบบจะมีระบบป้องกัน **PEP 668 (`externally-managed-environment`)** เพื่อความปลอดภัยของระบบปฏิบัติการ แนะนำให้ติดตั้งและรันผ่าน Python Virtual Environment เสมอ

#### 1. ติดตั้งแพ็กเกจระบบที่จำเป็น
```bash
apt update
apt install -y python3-venv python3-full git
```

#### 2. ดาวน์โหลดโค้ดโปรเจกต์
```bash
git clone https://github.com/teerakanotklan/squid-dashy.git ~/squid-dashy
cd ~/squid-dashy
```

#### 3. สร้างและเปิดใช้งาน Virtual Environment
```bash
# สร้าง venv
python3 -m venv venv

# เปิดใช้งาน (Activate)
source venv/bin/activate
```
เมื่อเปิดใช้งานสำเร็จ Prompt บน Terminal จะมีเครื่องหมาย `(venv)` นำหน้า เช่น:
```text
(venv) root@squid01:~/squid-dashy#
```

#### 4. อัปเกรด pip และติดตั้ง Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
*(ใน `requirements.txt` รวม `uvicorn[standard]` และ `websockets` ไว้แล้วเพื่อรองรับการเชื่อมต่อแบบ WebSocket สมบูรณ์แบบ)*

#### 5. เริ่มต้นรันแอปพลิเคชัน
```bash
python app.py
```

เปิดเบราว์เซอร์ไปที่:
👉 **`http://<SERVER_IP>:8080`**

> 💡 **หมายเหตุ:** เมื่อเปิด Terminal เซสชันใหม่ในครั้งถัดไป ให้เปิดใช้งาน venv ก่อนเสมอ:
> ```bash
> cd ~/squid-dashy
> source venv/bin/activate
> python app.py
> ```

---

### วิธีที่ 3: ติดตั้งให้ทำงานเบื้องหลังอัตโนมัติแบบกำหนดเอง (Linux Systemd Service)

หากต้องการให้ `squid-dashy` รันอัตโนมัติตลอดเวลาและเปิดขึ้นมาใหม่เองเมื่อรีบูตเครื่อง (กรณีไม่ได้ใช้ `install.sh`):

1. ปรับแต่งไฟล์ Service ให้เรียกใช้ Python ใน `venv` โดยตรง (ตรวจสอบ path โฟลเดอร์โปรเจกต์ เช่น `/root/squid-dashy` หรือ `/opt/squid-dashy`):
   ```bash
   sudo cp squid-dashboard.service /etc/systemd/system/squid-dashy.service
   ```

2. ตรวจสอบเนื้อหาใน `/etc/systemd/system/squid-dashy.service`:
   ```ini
   [Unit]
   Description=Squid Proxy Web Dashboard (squid-dashy)
   After=network.target squid.service
   Wants=squid.service

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/squid-dashy
   ExecStart=/root/squid-dashy/venv/bin/python app.py
   Restart=always
   RestartSec=5
   Environment=DASHBOARD_HOST=0.0.0.0
   Environment=DASHBOARD_PORT=8080
   Environment=SQUID_HOST=127.0.0.1
   Environment=SQUID_PORT=3128
   Environment=SQUID_ACCESS_LOG=/var/log/squid/access.log

   [Install]
   WantedBy=multi-user.target
   ```

3. สั่งโหลดและเปิดใช้งาน Service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now squid-dashy
   ```

4. ตรวจสอบสถานะการทำงาน:
   ```bash
   sudo systemctl status squid-dashy
   ```

---

### วิธีที่ 4: รันผ่าน Docker / Docker Compose

หากต้องการรันแดชบอร์ดเป็น Container โดยแชร์ Log จาก Squid บนเครื่องโฮสต์:

```bash
docker compose up -d
```

---

## 🛠️ การแก้ไขปัญหาที่พบบ่อย (Troubleshooting)

### 1. Error: `externally-managed-environment` (PEP 668)
- **สาเหตุ:** เกิดขึ้นบน Linux รุ่นใหม่ (Ubuntu 24.04, Debian 12+) ที่ใช้ Python 3.12 ขึ้นไป เพื่อป้องกันไม่ให้ `pip` ไปเขียนทับแพ็กเกจของ OS
- **วิธีแก้:** หลีกเลี่ยงการใช้ `--break-system-packages` โดยให้สร้าง `venv` ตามขั้นตอน:
  ```bash
  apt update && apt install -y python3-venv python3-full
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### 2. Warning: `No supported WebSocket library detected` หรือ WebSocket 404
- **สาเหตุ:** Uvicorn จำเป็นต้องมีไลบรารี `websockets` ติดตั้งเพิ่มเติมเพื่อรองรับโปรโตคอล WebSocket (`/ws/live`)
- **วิธีแก้:** ตรวจสอบว่าได้ติดตั้ง `uvicorn[standard]` และ `websockets` ภายใน venv:
  ```bash
  source venv/bin/activate
  pip install "uvicorn[standard]" websockets
  ```
  ตรวจสอบความถูกต้อง:
  ```bash
  python -m pip show uvicorn websockets
  ```

---

## ⚙️ การตั้งค่าสภาพแวดล้อม (Environment Variables)

สามารถกำหนดค่าผ่าน Environment Variable หรือไฟล์ `.env` ได้ดังนี้:

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
| :--- | :--- | :--- |
| `DASHBOARD_HOST` | `0.0.0.0` | IP Address สำหรับรับการเชื่อมต่อของ Web Dashboard |
| `DASHBOARD_PORT` | `8080` | พอร์ตของ Web Dashboard |
| `SQUID_HOST` | `127.0.0.1` | IP ของเครื่อง Squid Proxy |
| `SQUID_PORT` | `3128` | พอร์ตของ Squid Proxy |
| `SQUID_ACCESS_LOG` | `/var/log/squid/access.log` | ตำแหน่งไฟล์ access.log ของ Squid |

---

## 🔧 การตั้งค่าบน `squid.conf` เพื่อให้แดชบอร์ดอ่านค่าได้สมบูรณ์

เพื่อให้แดชบอร์ดสามารถเรียกดูค่าสถิติจาก Squid Cache Manager (`mgr:info`) ได้ ให้ตรวจสอบและเพิ่มค่า ACL ใน `/etc/squid/squid.conf`:

```squid
# 1. กำหนด ACL อนุญาต localhost หรือ IP ของเครื่อง Dashboard
acl localhost src 127.0.0.1/32 ::1
acl manager proto cache_object

# 2. อนุญาตให้เรียกดู Cache Manager ได้
http_access allow manager localhost
http_access deny manager

# 3. กำหนดรูปแบบ Log มาตรฐาน
logformat squid %ts.%03tu %6tr %>a %Ss/%03>Hs %<st %rm %ru %[un %Sh/%<a %mt
access_log /var/log/squid/access.log squid
```

หลังจากแก้ไขแล้ว ให้สั่ง Reload Squid:
```bash
sudo squid -k reconfigure
```
