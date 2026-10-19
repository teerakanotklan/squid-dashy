import os
import re
import subprocess
from urllib.parse import urlparse
from config import config

class DomainBlocker:
    def __init__(self):
        self.file_path = config.SQUID_BLOCKED_DOMAINS_FILE
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure the ACL file and its parent directories exist"""
        try:
            parent_dir = os.path.dirname(self.file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            if not os.path.exists(self.file_path):
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write("# Squid Proxy Blocked Domains ACL List\n")
                    f.write("# One domain per line. Leading dot (.example.com) blocks all subdomains.\n")
        except Exception as e:
            print(f"Warning: Could not create blocklist file {self.file_path}: {e}")

    @staticmethod
    def normalize_domain(domain: str) -> str:
        """Cleans and validates a domain input string"""
        if not domain:
            return ""
        domain = domain.strip().lower()
        if domain.startswith("http://") or domain.startswith("https://"):
            try:
                parsed = urlparse(domain)
                domain = parsed.netloc or domain
            except Exception:
                pass
        # Strip port if present
        domain = domain.split(":")[0]
        # Strip trailing slash or path
        domain = domain.split("/")[0].strip()
        return domain

    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        """Checks if a domain string is valid for Squid dstdomain ACL"""
        if not domain or len(domain) > 253:
            return False
        # Optional leading dot for wildcard subdomains (e.g. .facebook.com)
        pattern = r"^(\.?[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"
        return bool(re.match(pattern, domain))

    def get_blocked_domains(self) -> dict:
        """Returns the list of blocked domains from the ACL file"""
        self._ensure_file_exists()
        domains = []
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            domains.append(line)
            except Exception as e:
                return {"error": f"Failed to read blocklist file: {str(e)}", "domains": [], "file_path": self.file_path}

        return {
            "domains": sorted(domains),
            "count": len(domains),
            "file_path": self.file_path,
            "writable": os.access(self.file_path, os.W_OK) if os.path.exists(self.file_path) else False
        }

    def add_domain(self, raw_domain: str) -> dict:
        """Adds a domain to the blocklist and reconfigures Squid"""
        domain = self.normalize_domain(raw_domain)
        if not domain:
            return {"success": False, "message": "Domain name cannot be empty."}
        if not self.is_valid_domain(domain):
            return {"success": False, "message": f"Invalid domain format: '{raw_domain}'."}

        current = self.get_blocked_domains().get("domains", [])
        if domain in current:
            return {"success": False, "message": f"Domain '{domain}' is already in the blocklist."}

        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"{domain}\n")
        except Exception as e:
            return {"success": False, "message": f"Failed to write to {self.file_path}: {str(e)}"}

        reload_status = self.reconfigure_squid()
        return {
            "success": True,
            "message": f"Domain '{domain}' blocked successfully. {reload_status.get('message', '')}",
            "domain": domain,
            "reconfigure": reload_status
        }

    def remove_domain(self, raw_domain: str) -> dict:
        """Removes a domain from the blocklist and reconfigures Squid"""
        domain = self.normalize_domain(raw_domain)
        if not domain:
            return {"success": False, "message": "Domain name cannot be empty."}

        current = self.get_blocked_domains().get("domains", [])
        if domain not in current:
            return {"success": False, "message": f"Domain '{domain}' is not in the blocklist."}

        try:
            lines = []
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

            with open(self.file_path, "w", encoding="utf-8") as f:
                for line in lines:
                    stripped = line.strip()
                    if stripped != domain:
                        f.write(line)
        except Exception as e:
            return {"success": False, "message": f"Failed to update {self.file_path}: {str(e)}"}

        reload_status = self.reconfigure_squid()
        return {
            "success": True,
            "message": f"Domain '{domain}' unblocked successfully. {reload_status.get('message', '')}",
            "domain": domain,
            "reconfigure": reload_status
        }

    def reconfigure_squid(self) -> dict:
        """Executes 'squid -k reconfigure' to reload ACL rules without restarting"""
        cmd = config.SQUID_RECONFIGURE_CMD
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return {"success": True, "message": "Squid reconfigured successfully."}
            else:
                err_msg = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
                return {"success": False, "message": f"Squid reconfigure warning: {err_msg}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Squid reconfigure timed out."}
        except Exception as e:
            return {"success": False, "message": f"Squid reload skipped ({str(e)})."}

domain_blocker = DomainBlocker()
