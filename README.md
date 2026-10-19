# 🦑 Squid Proxy Web Dashboard (squid-dashy)

A modern, lightweight, real-time web monitoring and analytics dashboard for **Squid Proxy**. Built with **FastAPI**, **Tailwind CSS**, **Chart.js**, and **WebSockets**.

---

## ✨ Features

1. **Cache Performance Metrics:**
   - **Request Hit Ratio (%)**: Percentage of client requests served directly from cache without accessing the upstream internet.
   - **Byte Hit Ratio (%) / Bandwidth Saved**: Bandwidth volume saved (MB/GB) by caching content.
   - **Throughput & Request Rate**: Real-time request rates (Requests/sec) and network throughput (KB/s, MB/s).
   - **System & Storage Metrics**: RAM Cache, Disk Swap Cache, CPU Usage, and File Descriptors.

2. **Real-time Interactive Visualizations:**
   - Live time-series throughput chart showing request volume and bandwidth over time.
   - Cache distribution donut chart categorizing Hits, Misses, and Denied/Blocked requests.

3. **Live Access Log Streamer & Filters:**
   - Real-time `access.log` streaming via WebSocket (`/ws/live`).
   - Instant search filtering by Client IP, Domain, URL, or Result Code.
   - Quick-toggle status filter buttons: **All**, **Hits Only**, **Miss Only**, or **Blocked (403)**.
   - Pause/Resume and Clear controls for inspecting suspicious traffic.

4. **Traffic Analytics:**
   - **Top Client IPs**: Identifies top client machines by request count, hit ratio, and transferred bandwidth.
   - **Top Domains**: Ranks most frequently requested domains and shows blocked/denied statistics.

5. **Integrated Squid Cache Manager Explorer:**
   - Run queries directly against the Squid Cache Manager API (`mgr:info`, `mgr:5min`, `mgr:utilization`, `mgr:client_list`, `mgr:ipcache`, `mgr:counters`).
   - Terminal-style raw output viewer with one-click copy to clipboard.

---

## 🚀 Installation & Getting Started

### ⚡ Option 1: Automated Installer (Recommended)

Run the one-line installer command on your server (supports **Ubuntu 20.04/22.04/24.04**, **Debian 11/12**, **CentOS/RHEL 8/9**, **AlmaLinux/Rocky Linux**):

```bash
curl -sSL https://raw.githubusercontent.com/teerakanotklan/squid-dashy/main/install.sh | sudo bash
```

> 💡 **If you have already cloned the repository locally:**
> ```bash
> cd ~/squid-dashy
> sudo bash install.sh
> ```

The installer provides two modes:
- **`[1] Test`**: Sets up `venv`, installs dependencies, and runs the server in foreground on the terminal for immediate testing.
- **`[2] Production`**: Sets up `venv`, installs dependencies, and configures an automatic **Systemd Service** that runs in the background and starts on boot.

*(You can also skip the prompt using flags: `sudo bash install.sh --test` or `sudo bash install.sh --prod`)*

---

### 🛠️ Option 2: Manual Installation with Virtual Environment (venv)

> ⚠️ **For Ubuntu 24.04 / Debian 12 (Python 3.12+):**  
> Modern Linux distributions enforce **PEP 668 (`externally-managed-environment`)**. Installing inside a dedicated Python virtual environment is required and best practice.

#### 1. Install System Dependencies
```bash
apt update
apt install -y python3-venv python3-full python3-pip git curl
```

#### 2. Clone the Repository
```bash
git clone https://github.com/teerakanotklan/squid-dashy.git ~/squid-dashy
cd ~/squid-dashy
```

#### 3. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```
Your terminal prompt will indicate that `(venv)` is active:
```text
(venv) root@squid01:~/squid-dashy#
```

#### 4. Upgrade pip and Install Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
*(Includes `fastapi`, `uvicorn[standard]`, and `websockets` for full WebSocket upgrade support)*

#### 5. Start the Application
```bash
python app.py
```

Open your browser and navigate to:
👉 **`http://<SERVER_IP>:8080`**

> 💡 **Tip:** To reactivate the virtual environment in future terminal sessions:
> ```bash
> cd ~/squid-dashy
> source venv/bin/activate
> python app.py
> ```

---

### ⚙️ Option 3: Configure as Linux Systemd Service (Production)

To run `squid-dashy` as a persistent background service managed by systemd:

1. Copy the systemd service template:
   ```bash
   sudo cp squid-dashboard.service /etc/systemd/system/squid-dashy.service
   ```

2. Review `/etc/systemd/system/squid-dashy.service` to verify directory paths:
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

3. Reload systemd and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now squid-dashy
   ```

4. Verify service status:
   ```bash
   sudo systemctl status squid-dashy
   ```

---

### 🐳 Option 4: Run with Docker / Docker Compose

To run the dashboard inside a container and mount host Squid logs:

```bash
docker compose up -d
```

---

## 🛠️ Troubleshooting

### 1. Error: `externally-managed-environment` (PEP 668)
- **Cause:** Occurs on Linux distributions running Python 3.12+ (Ubuntu 24.04, Debian 12+) to protect OS-managed packages from pip overwrites.
- **Solution:** Avoid using `--break-system-packages`. Create a virtual environment instead:
  ```bash
  apt update && apt install -y python3-venv python3-full
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### 2. Warning: `No supported WebSocket library detected` or WebSocket 404
- **Cause:** Uvicorn requires the `websockets` package to handle HTTP WebSocket Upgrade handshakes (`/ws/live`).
- **Solution:** Ensure `uvicorn[standard]` and `websockets` are installed inside the venv:
  ```bash
  source venv/bin/activate
  pip install "uvicorn[standard]" websockets
  ```
  Verify with:
  ```bash
  python -m pip show uvicorn websockets
  ```

---

## ⚙️ Environment Variables

Configuration parameters can be defined via environment variables or a `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DASHBOARD_HOST` | `0.0.0.0` | Listen IP address for Web Dashboard |
| `DASHBOARD_PORT` | `8080` | Listen HTTP port for Web Dashboard |
| `SQUID_HOST` | `127.0.0.1` | IP address of the Squid Proxy instance |
| `SQUID_PORT` | `3128` | Port of the Squid Proxy instance |
| `SQUID_ACCESS_LOG` | `/var/log/squid/access.log` | Path to Squid access log file |
| `SQUID_MGR_USER` | `""` | Optional HTTP basic auth user for Cache Manager |
| `SQUID_MGR_PASS` | `""` | Optional HTTP basic auth password for Cache Manager |

---

## 🔧 Configuring `squid.conf` for Dashboard Access

To allow the dashboard to query the Squid Cache Manager (`mgr:info`), add or verify the following ACL settings in `/etc/squid/squid.conf`:

```squid
# 1. Define ACLs allowing localhost or dashboard host
acl localhost src 127.0.0.1/32 ::1
acl manager proto cache_object

# 2. Allow access to Cache Manager
http_access allow manager localhost
http_access deny manager

# 3. Standard access log configuration
logformat squid %ts.%03tu %6tr %>a %Ss/%03>Hs %<st %rm %ru %[un %Sh/%<a %mt
access_log /var/log/squid/access.log squid
```

Apply changes by reconfiguring Squid:
```bash
sudo squid -k reconfigure
```
