import os

class Config:
    HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
    
    # Squid Proxy Settings
    SQUID_HOST = os.getenv("SQUID_HOST", "127.0.0.1")
    SQUID_PORT = int(os.getenv("SQUID_PORT", "3128"))
    SQUID_MGR_USER = os.getenv("SQUID_MGR_USER", "")
    SQUID_MGR_PASS = os.getenv("SQUID_MGR_PASS", "")
    
    # Squid Log Paths (Linux standard default or custom)
    SQUID_ACCESS_LOG = os.getenv("SQUID_ACCESS_LOG", "/var/log/squid/access.log")
    SQUID_CACHE_LOG = os.getenv("SQUID_CACHE_LOG", "/var/log/squid/cache.log")

    # Domain Blocking Configuration
    _default_blocklist = "/etc/squid/blocked_domains.acl"
    if not os.path.exists("/etc/squid") and not os.getenv("SQUID_BLOCKED_DOMAINS_FILE"):
        _default_blocklist = os.path.join(os.path.dirname(__file__), "blocked_domains.acl")
        
    SQUID_BLOCKED_DOMAINS_FILE = os.getenv("SQUID_BLOCKED_DOMAINS_FILE", _default_blocklist)
    SQUID_RECONFIGURE_CMD = os.getenv("SQUID_RECONFIGURE_CMD", "squid -k reconfigure")

    # Data Storage & Graylog-style Log Retention Lifecycle
    # 1. Metrics History: Kept up to 365 days
    # 2. Raw Log Daily Archive: Sliced when log age > 1 day
    # 3. Monthly Consolidation: Bundled into consolidated monthly archives at 30 days
    # 4. Raw Log Rotation/Purge: Deleted when older than 91 days
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    METRICS_RETENTION_DAYS = int(os.getenv("METRICS_RETENTION_DAYS", "365"))
    LOG_ARCHIVE_DAYS = int(os.getenv("LOG_ARCHIVE_DAYS", "1"))
    LOG_CONSOLIDATION_DAYS = int(os.getenv("LOG_CONSOLIDATION_DAYS", "30"))
    LOG_PURGE_DAYS = int(os.getenv("LOG_PURGE_DAYS", "91"))

config = Config()
