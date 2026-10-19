# 🦑 Squid Proxy Web Dashboard

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
   - อ่านและแสดงผลไฟล์ `access.log` แบบสดๆ ผ่าน WebSocket
   - มีช่องค้นหาแบบเรียลไทม์ตาม Client IP, Domain, URL หรือ Result Code
   - ฟิลเตอร์คัดกรองเฉพาะ Hits, Misses หรือ Blocked (403 Forbidden)
   - ปุ่มกดพักหน้าจอ (Pause/Resume) สำหรับตรวจสอบ Log ที่น่าสงสัย

4. **การวิเคราะห์ข้อมูลผู้ใช้งาน (Traffic Analytics):**
   - **Top Client IPs**: ตรวจดูว่าเครื่องลูกข่าย IP ใดใช้คำขอและแบนด์วิดท์สูงสุด พร้อมอัตรา Hit Ratio รายเครื่อง
   - **Top Domains**: จัดอันดับเว็บไซต์ที่ถูกเรียกใช้งานบ่อยที่สุด และสถิติการถูกบล็อก

5. **เครื่องมือเชื่อมต่อ Squid Cache Manager:**
   - รองรับการดึงข้อมูลและสถิติเชิงลึกผ่าน `mgr:info`, `mgr:5min`, `mgr:utilization`, `mgr:client_list`, `mgr:ipcache`, `mgr:counters`
   - มีปุ่มคลิกคัดลอกข้อความผลลัพธ์ (Copy to Clipboard)

6. **ระบบ Demo / Simulation Mode:**
   - ตรวจจับอัตโนมัติ หากยังไม่ได้ต่อกับ Squid จริง หรือรันบนเครื่อง Local/Windows ระบบจะจำลองข้อมูลทราฟฟิกและสถิติให้ทดสอบหน้าจอได้ทันที

---

## 🚀 วิธีการติดตั้งและเริ่มใช้งาน (Quick Start)

### วิธีที่ 1: รันด้วย Python โดยตรง (แนะนำสำหรับทดสอบหรือรันบนโฮสต์ Squid)

1. เข้าไปยังโฟลเดอร์โปรเจกต์:
   ```bash
   cd squid-dashboard
   ```

2. ติดตั้ง Library ที่จำเป็น:
   ```bash
   pip install -r requirements.txt
   ```

3. เริ่มต้นรันแดชบอร์ด:
   ```bash
   python app.py
   ```

4. เปิดเบราว์เซอร์ไปที่:
   ```
   http://localhost:8080
   ```

---

### วิธีที่ 2: รันผ่าน Docker / Docker Compose (สะดวกที่สุดบน Production)

หากต้องการรันแดชบอร์ดเป็น Container โดยแชร์ Log จาก Squid บนเครื่องโฮสต์:

```bash
docker compose up -d
```

---

### วิธีที่ 3: ติดตั้งเป็น Linux Systemd Service (สำหรับ Ubuntu / Debian / CentOS)

1. คัดลอกโฟลเดอร์โปรเจกต์ไปที่ `/opt/squid-dashboard`
2. คัดลอกไฟล์ Service:
   ```bash
   sudo cp squid-dashboard.service /etc/systemd/system/
   ```
3. สั่งโหลดและเปิดใช้งาน Service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now squid-dashboard
   ```
4. ตรวจสอบสถานะการทำงาน:
   ```bash
   sudo systemctl status squid-dashboard
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
| `FORCE_DEMO_MODE` | `false` | บังคับเปิดโหมดจำลองทราฟฟิกสำหรับทดสอบ UI |

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
