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
    
    # Demo/Simulation Mode (defaults to Auto: True if Squid host or log is unreachable)
    FORCE_DEMO_MODE = os.getenv("FORCE_DEMO_MODE", "").lower() in ("true", "1", "yes")

config = Config()
