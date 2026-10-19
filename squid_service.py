import os
import re
import time
import socket
import asyncio
import random
from datetime import datetime, timezone
from collections import deque, Counter
from urllib.parse import urlparse
from config import config

class SquidLogEntry:
    def __init__(self, timestamp: float, duration_ms: int, client_ip: str, 
                 result_code: str, http_status: int, bytes_transferred: int, 
                 method: str, url: str, peer: str, mime_type: str):
        self.timestamp = timestamp
        self.datetime_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.duration_ms = duration_ms
        self.client_ip = client_ip
        self.result_code = result_code      # e.g., TCP_HIT, TCP_MISS, TCP_DENIED, TCP_MEM_HIT
        self.http_status = http_status      # e.g., 200, 304, 403, 500
        self.bytes_transferred = bytes_transferred
        self.method = method                # GET, POST, CONNECT
        self.url = url
        self.domain = self._extract_domain(url)
        self.peer = peer                    # DIRECT/x.x.x.x or HIER_NONE/-
        self.mime_type = mime_type
        self.is_hit = "HIT" in result_code
        self.is_denied = "DENIED" in result_code or http_status in (403, 401)

    @staticmethod
    def _extract_domain(url: str) -> str:
        if not url:
            return "unknown"
        if url.startswith("http://") or url.startswith("https://"):
            try:
                parsed = urlparse(url)
                return parsed.netloc.split(":")[0] or url
            except Exception:
                pass
        # Handle CONNECT domain:443 or raw domain
        clean = url.split("/")[0].split(":")[0]
        return clean if clean else url

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "datetime": self.datetime_str,
            "duration_ms": self.duration_ms,
            "client_ip": self.client_ip,
            "result_code": self.result_code,
            "http_status": self.http_status,
            "bytes": self.bytes_transferred,
            "method": self.method,
            "url": self.url,
            "domain": self.domain,
            "peer": self.peer,
            "mime_type": self.mime_type,
            "is_hit": self.is_hit,
            "is_denied": self.is_denied
        }


class SquidMonitor:
    def __init__(self):
        self.is_demo_mode = config.FORCE_DEMO_MODE
        self.squid_alive = False
        self.squid_version = "Squid Cache"
        self.uptime_seconds = 0
        self.start_time = time.time()
        
        # Log records buffer
        self.recent_logs = deque(maxlen=500)
        
        # Aggregated stats counters
        self.total_requests = 0
        self.hit_requests = 0
        self.miss_requests = 0
        self.denied_requests = 0
        self.total_bytes = 0
        self.saved_bytes = 0  # Bytes served from cache
        
        self.status_counters = Counter()
        self.client_stats = {}    # {ip: {"requests": int, "bytes": int, "hits": int, "last_seen": str}}
        self.domain_stats = {}    # {domain: {"requests": int, "bytes": int, "hits": int, "denied": int}}
        
        # Time-series history for charts (last 30 intervals, ~60 seconds)
        self.history = deque(maxlen=30)
        
        # System/Squid hardware metrics
        self.metrics = {
            "cpu_usage_pct": 2.4,
            "memory_used_mb": 142.5,
            "memory_max_mb": 512.0,
            "disk_cache_used_mb": 1820.0,
            "disk_cache_max_mb": 10240.0,
            "file_descriptors_used": 68,
            "file_descriptors_max": 4096,
            "active_clients": 0,
            "req_per_sec": 0.0,
            "kb_per_sec": 0.0
        }

        # Log file tail state
        self._last_log_size = 0
        self._last_calc_time = time.time()
        self._last_total_req = 0
        self._last_total_bytes = 0

    def parse_log_line(self, line: str) -> SquidLogEntry | None:
        """Parse standard Squid access.log line"""
        # Format: timestamp elapsed client_ip result/status bytes method url rfc931 hierarchy mime
        # Example: 1697734123.456 12 192.168.1.105 TCP_MEM_HIT/200 4821 GET https://google.com/ - HIER_NONE/- text/html
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split()
        if len(parts) < 8:
            return None
        try:
            timestamp = float(parts[0])
            duration = int(parts[1]) if parts[1].isdigit() else 0
            client_ip = parts[2]
            
            code_parts = parts[3].split("/")
            result_code = code_parts[0]
            http_status = int(code_parts[1]) if len(code_parts) > 1 and code_parts[1].isdigit() else 200
            
            bytes_transferred = int(parts[4]) if parts[4].isdigit() else 0
            method = parts[5]
            url = parts[6]
            peer = parts[8] if len(parts) > 8 else "-"
            mime = parts[9] if len(parts) > 9 else "-"
            
            return SquidLogEntry(timestamp, duration, client_ip, result_code, 
                                 http_status, bytes_transferred, method, url, peer, mime)
        except Exception:
            return None

    def record_entry(self, entry: SquidLogEntry):
        self.recent_logs.append(entry.to_dict())
        self.total_requests += 1
        self.total_bytes += entry.bytes_transferred
        self.status_counters[entry.result_code] += 1
        
        if entry.is_hit:
            self.hit_requests += 1
            self.saved_bytes += entry.bytes_transferred
        elif entry.is_denied:
            self.denied_requests += 1
        else:
            self.miss_requests += 1

        # Client stats
        if entry.client_ip not in self.client_stats:
            self.client_stats[entry.client_ip] = {"requests": 0, "bytes": 0, "hits": 0, "last_seen": entry.datetime_str}
        c = self.client_stats[entry.client_ip]
        c["requests"] += 1
        c["bytes"] += entry.bytes_transferred
        c["last_seen"] = entry.datetime_str
        if entry.is_hit:
            c["hits"] += 1

        # Domain stats
        dom = entry.domain
        if dom not in self.domain_stats:
            self.domain_stats[dom] = {"requests": 0, "bytes": 0, "hits": 0, "denied": 0}
        d = self.domain_stats[dom]
        d["requests"] += 1
        d["bytes"] += entry.bytes_transferred
        if entry.is_hit:
            d["hits"] += 1
        if entry.is_denied:
            d["denied"] += 1

    def query_squid_mgr(self, action: str = "info") -> str:
        """Query Squid Cache Manager via raw HTTP socket"""
        host = config.SQUID_HOST
        port = config.SQUID_PORT
        auth_header = ""
        if config.SQUID_MGR_USER and config.SQUID_MGR_PASS:
            import base64
            token = base64.b64encode(f"{config.SQUID_MGR_USER}:{config.SQUID_MGR_PASS}".encode()).decode()
            auth_header = f"Authorization: Basic {token}\r\n"
        
        req = (
            f"GET /squid-internal-mgr/{action} HTTP/1.0\r\n"
            f"Host: {host}:{port}\r\n"
            f"{auth_header}"
            f"User-Agent: Squid-Dashboard/1.0\r\n"
            f"Accept: */*\r\n\r\n"
        )
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            s.connect((host, port))
            s.sendall(req.encode())
            
            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
            s.close()
            
            raw_text = response.decode(errors="replace")
            # Remove HTTP headers
            parts = raw_text.split("\r\n\r\n", 1)
            body = parts[1] if len(parts) > 1 else raw_text
            self.squid_alive = True
            self._parse_mgr_info(body)
            return body
        except Exception as e:
            self.squid_alive = False
            return f"Squid Cache Manager query failed: {str(e)}"

    def _parse_mgr_info(self, raw_info: str):
        """Extract key metrics from Squid's mgr:info output"""
        try:
            for line in raw_info.splitlines():
                if "Squid Object Cache: Version" in line:
                    self.squid_version = line.split(":", 1)[1].strip()
                elif "Start Time:" in line:
                    pass
                elif "Process Data:" in line:
                    pass
                elif "CPU Usage:" in line:
                    m = re.search(r"CPU Usage:\s+([\d\.]+)%", line)
                    if m:
                        self.metrics["cpu_usage_pct"] = float(m.group(1))
                elif "Storage Swap size:" in line:
                    m = re.search(r"([\d]+)\s+KB", line)
                    if m:
                        self.metrics["disk_cache_used_mb"] = round(int(m.group(1)) / 1024, 1)
                elif "Total accounted:" in line:
                    m = re.search(r"([\d]+)\s+KB", line)
                    if m:
                        self.metrics["memory_used_mb"] = round(int(m.group(1)) / 1024, 1)
                elif "Number of file desc currently in use:" in line:
                    m = re.search(r"(\d+)", line)
                    if m:
                        self.metrics["file_descriptors_used"] = int(m.group(1))
        except Exception:
            pass

    def generate_demo_traffic(self):
        """Generates realistic synthetic Squid proxy events for demo & testing"""
        demo_clients = [
            "192.168.1.102", "192.168.1.105", "192.168.1.114", "192.168.1.120", 
            "192.168.1.145", "10.0.0.54", "10.0.0.88", "172.16.0.12"
        ]
        demo_sites = [
            ("cdn.jsdelivr.net", "application/javascript", "TCP_MEM_HIT", 200, 35000),
            ("fonts.googleapis.com", "text/css", "TCP_HIT", 200, 12000),
            ("repo.debian.org", "application/octet-stream", "TCP_HIT", 200, 450000),
            ("api.github.com", "application/json", "TCP_MISS", 200, 4200),
            ("news.ycombinator.com", "text/html", "TCP_MISS", 200, 18500),
            ("img.youtube.com", "image/jpeg", "TCP_MEM_HIT", 200, 68000),
            ("static.cloudflareinsights.com", "application/javascript", "TCP_HIT", 200, 8900),
            ("adservice.google.com", "text/html", "TCP_DENIED", 403, 1420),
            ("tracker.analytics.io", "application/json", "TCP_DENIED", 403, 850),
            ("docker.io", "application/octet-stream", "TCP_MISS", 200, 950000),
            ("raw.githubusercontent.com", "text/plain", "TCP_HIT", 200, 24000),
            ("connect.facebook.net", "application/javascript", "TCP_DENIED", 403, 1100),
        ]
        
        # Generate 1 to 4 random requests per tick
        count = random.randint(1, 4)
        now = time.time()
        for _ in range(count):
            client = random.choice(demo_clients)
            site, mime, code, status, base_bytes = random.choice(demo_sites)
            
            # Add small random variation
            bytes_transferred = int(base_bytes * random.uniform(0.7, 1.4))
            duration = random.randint(3, 120) if "HIT" in code else random.randint(80, 450)
            url = f"https://{site}/resource/{random.randint(100, 999)}?t={int(now)}"
            peer = "HIER_NONE/-" if "HIT" in code or code == "TCP_DENIED" else f"DIRECT/{random.randint(1,220)}.{random.randint(1,220)}.10.5"
            method = "CONNECT" if ":443" in site else "GET"
            
            entry = SquidLogEntry(now, duration, client, code, status, bytes_transferred, method, url, peer, mime)
            self.record_entry(entry)

        # Fluctuate simulated metrics smoothly
        self.metrics["cpu_usage_pct"] = round(max(0.5, min(95.0, self.metrics["cpu_usage_pct"] + random.uniform(-0.6, 0.7))), 1)
        self.metrics["memory_used_mb"] = round(max(50.0, min(480.0, self.metrics["memory_used_mb"] + random.uniform(-1.5, 2.0))), 1)
        self.metrics["disk_cache_used_mb"] = round(max(500.0, min(9800.0, self.metrics["disk_cache_used_mb"] + (self.saved_bytes / (1024*1024*100)))), 1)
        self.metrics["file_descriptors_used"] = random.randint(45, 120)
        self.squid_version = "Squid Cache 6.6 (Demo Simulation Mode)"
        self.squid_alive = True

    def tail_log_file(self):
        """Reads new lines from Squid's access.log if it exists"""
        log_path = config.SQUID_ACCESS_LOG
        if not os.path.exists(log_path):
            return
        
        try:
            curr_size = os.path.getsize(log_path)
            if self._last_log_size == 0:
                # First run: read last 100KB to prefill
                start_pos = max(0, curr_size - 100 * 1024)
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(start_pos)
                    lines = f.readlines()
                    for line in lines[-150:]:
                        entry = self.parse_log_line(line)
                        if entry:
                            self.record_entry(entry)
                self._last_log_size = curr_size
            elif curr_size > self._last_log_size:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self._last_log_size)
                    for line in f:
                        entry = self.parse_log_line(line)
                        if entry:
                            self.record_entry(entry)
                self._last_log_size = curr_size
            elif curr_size < self._last_log_size:
                # Log was rotated!
                self._last_log_size = 0
        except Exception:
            pass

    def tick(self):
        """Called periodically (e.g. every 2 seconds) to compute rates and time-series"""
        now = time.time()
        elapsed = now - self._last_calc_time
        if elapsed <= 0:
            elapsed = 1.0

        # Check real Squid or Demo
        if not self.is_demo_mode and os.path.exists(config.SQUID_ACCESS_LOG):
            self.tail_log_file()
            self.query_squid_mgr("info")
        else:
            # Fallback to demo mode if Squid is not locally present
            self.generate_demo_traffic()

        # Compute rates
        delta_req = self.total_requests - self._last_total_req
        delta_bytes = self.total_bytes - self._last_total_bytes
        
        req_sec = round(delta_req / elapsed, 1)
        kb_sec = round((delta_bytes / 1024) / elapsed, 1)
        
        self.metrics["req_per_sec"] = req_sec
        self.metrics["kb_per_sec"] = kb_sec
        self.metrics["active_clients"] = len(self.client_stats)
        
        self._last_total_req = self.total_requests
        self._last_total_bytes = self.total_bytes
        self._last_calc_time = now
        self.uptime_seconds = int(now - self.start_time)

        # Calculate hit rates
        req_hit_pct = round((self.hit_requests / self.total_requests * 100), 1) if self.total_requests > 0 else 0.0
        byte_hit_pct = round((self.saved_bytes / self.total_bytes * 100), 1) if self.total_bytes > 0 else 0.0

        # Snapshot for chart
        time_label = datetime.now().strftime("%H:%M:%S")
        self.history.append({
            "time": time_label,
            "req_per_sec": req_sec,
            "kb_per_sec": kb_sec,
            "hit_requests": self.hit_requests,
            "miss_requests": self.miss_requests,
            "denied_requests": self.denied_requests,
            "req_hit_pct": req_hit_pct,
            "byte_hit_pct": byte_hit_pct
        })

    def get_summary_state(self):
        """Returns complete state for the dashboard"""
        req_hit_pct = round((self.hit_requests / self.total_requests * 100), 1) if self.total_requests > 0 else 0.0
        byte_hit_pct = round((self.saved_bytes / self.total_bytes * 100), 1) if self.total_bytes > 0 else 0.0

        # Sort top clients
        top_clients = sorted(
            [{"ip": ip, **data, "hit_ratio": round(data["hits"] / data["requests"] * 100, 1) if data["requests"] > 0 else 0} 
             for ip, data in self.client_stats.items()],
            key=lambda x: x["requests"],
            reverse=True
        )[:10]

        # Sort top domains
        top_domains = sorted(
            [{"domain": dom, **data, "hit_ratio": round(data["hits"] / data["requests"] * 100, 1) if data["requests"] > 0 else 0} 
             for dom, data in self.domain_stats.items()],
            key=lambda x: x["requests"],
            reverse=True
        )[:10]

        return {
            "status": {
                "alive": self.squid_alive,
                "version": self.squid_version,
                "uptime": self.uptime_seconds,
                "is_demo_mode": self.is_demo_mode,
                "target_host": config.SQUID_HOST,
                "target_port": config.SQUID_PORT,
                "log_file": config.SQUID_ACCESS_LOG,
                "log_exists": os.path.exists(config.SQUID_ACCESS_LOG)
            },
            "kpi": {
                "total_requests": self.total_requests,
                "hit_requests": self.hit_requests,
                "miss_requests": self.miss_requests,
                "denied_requests": self.denied_requests,
                "req_hit_pct": req_hit_pct,
                "byte_hit_pct": byte_hit_pct,
                "total_bytes": self.total_bytes,
                "saved_bytes": self.saved_bytes,
                "req_per_sec": self.metrics["req_per_sec"],
                "kb_per_sec": self.metrics["kb_per_sec"],
                "active_clients": len(self.client_stats)
            },
            "metrics": self.metrics,
            "status_counters": dict(self.status_counters.most_common(10)),
            "top_clients": top_clients,
            "top_domains": top_domains,
            "history": list(self.history),
            "recent_logs": list(self.recent_logs)[-50:]
        }

monitor = SquidMonitor()
