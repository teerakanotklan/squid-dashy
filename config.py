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

config = Config()
