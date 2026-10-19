import os
import sqlite3
import gzip
import tarfile
import json
import shutil
from datetime import datetime, timezone, timedelta
from config import config

class RetentionManager:
    def __init__(self):
        self.data_dir = config.DATA_DIR
        self.db_path = os.path.join(self.data_dir, "squid_history.db")
        self.daily_archive_dir = os.path.join(self.data_dir, "archives", "daily")
        self.monthly_archive_dir = os.path.join(self.data_dir, "archives", "monthly")
        
        self._ensure_directories()
        self._init_database()

    def _ensure_directories(self):
        """Creates necessary directory tree for database and compressed archives"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.daily_archive_dir, exist_ok=True)
        os.makedirs(self.monthly_archive_dir, exist_ok=True)

    def _get_connection(self):
        """Returns SQLite database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initializes tables for 365-day metrics and Graylog-style index lifecycle tracking"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Daily summarized metrics table (preserved up to 365 days)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    date TEXT PRIMARY KEY,
                    total_requests INTEGER DEFAULT 0,
                    hit_requests INTEGER DEFAULT 0,
                    miss_requests INTEGER DEFAULT 0,
                    denied_requests INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    saved_bytes INTEGER DEFAULT 0,
                    hit_ratio REAL DEFAULT 0.0,
                    byte_hit_ratio REAL DEFAULT 0.0,
                    top_clients_json TEXT,
                    top_domains_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Graylog-style archive index registry
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS archive_indices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    index_name TEXT UNIQUE,
                    period_type TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    record_count INTEGER DEFAULT 0,
                    file_path TEXT,
                    file_size_bytes INTEGER DEFAULT 0,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    purged_at TIMESTAMP
                )
            """)
            conn.commit()

    def save_daily_metrics(self, stats: dict):
        """Persists or updates today's aggregated metrics snapshot into SQLite"""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        kpi = stats.get("kpi", {})
        top_clients = stats.get("top_clients", [])[:10]
        top_domains = stats.get("top_domains", [])[:10]

        total_req = kpi.get("total_requests", 0)
        hit_req = kpi.get("hit_requests", 0)
        miss_req = kpi.get("miss_requests", 0)
        denied_req = kpi.get("denied_requests", 0)
        total_bytes = kpi.get("total_bytes", 0)
        saved_bytes = kpi.get("saved_bytes", 0)
        req_hit_pct = kpi.get("req_hit_pct", 0.0)
        byte_hit_pct = kpi.get("byte_hit_pct", 0.0)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO daily_metrics (
                    date, total_requests, hit_requests, miss_requests, denied_requests,
                    total_bytes, saved_bytes, hit_ratio, byte_hit_ratio,
                    top_clients_json, top_domains_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(date) DO UPDATE SET
                    total_requests = excluded.total_requests,
                    hit_requests = excluded.hit_requests,
                    miss_requests = excluded.miss_requests,
                    denied_requests = excluded.denied_requests,
                    total_bytes = excluded.total_bytes,
                    saved_bytes = excluded.saved_bytes,
                    hit_ratio = excluded.hit_ratio,
                    byte_hit_ratio = excluded.byte_hit_ratio,
                    top_clients_json = excluded.top_clients_json,
                    top_domains_json = excluded.top_domains_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                today_str, total_req, hit_req, miss_req, denied_req,
                total_bytes, saved_bytes, req_hit_pct, byte_hit_pct,
                json.dumps(top_clients), json.dumps(top_domains)
            ))
            conn.commit()

    def get_historical_metrics(self, days: int = 30) -> dict:
        """Retrieves aggregated history for trend charts up to 365 days"""
        days = min(max(1, days), config.METRICS_RETENTION_DAYS)
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daily_metrics
                WHERE date >= ?
                ORDER BY date ASC
            """, (start_date,))
            rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "date": r["date"],
                "total_requests": r["total_requests"],
                "hit_requests": r["hit_requests"],
                "miss_requests": r["miss_requests"],
                "denied_requests": r["denied_requests"],
                "total_bytes": r["total_bytes"],
                "saved_bytes": r["saved_bytes"],
                "hit_ratio": r["hit_ratio"],
                "byte_hit_ratio": r["byte_hit_ratio"],
                "top_clients": json.loads(r["top_clients_json"]) if r["top_clients_json"] else [],
                "top_domains": json.loads(r["top_domains_json"]) if r["top_domains_json"] else []
            })

        return {
            "requested_days": days,
            "data_points": len(results),
            "history": results
        }

    def archive_daily_logs(self, recent_logs: list) -> dict:
        """
        Step 1: When log entries age exceeds 1 day (or on rotation),
        slices and compresses logs into daily gzip archives (access-YYYY-MM-DD.gz)
        """
        if not recent_logs:
            return {"archived_files": 0, "message": "No log records to archive."}

        # Group logs by date
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        by_date = {}
        for l in recent_logs:
            date_key = l.get("datetime", "").split(" ")[0]
            if date_key and date_key < today_str: # Only archive closed days (> 1 day old)
                if date_key not in by_date:
                    by_date[date_key] = []
                by_date[date_key].append(l)

        archived_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for date_key, log_list in by_date.items():
                archive_filename = f"access-{date_key}.log.gz"
                archive_path = os.path.join(self.daily_archive_dir, archive_filename)
                index_name = f"idx_daily_{date_key}"

                # Append or write compressed gzip
                try:
                    with gzip.open(archive_path, "wt", encoding="utf-8") as gz:
                        for entry in log_list:
                            gz.write(json.dumps(entry) + "\n")

                    file_size = os.path.getsize(archive_path)

                    cursor.execute("""
                        INSERT INTO archive_indices (
                            index_name, period_type, start_date, end_date,
                            record_count, file_path, file_size_bytes, status, created_at
                        ) VALUES (?, 'daily', ?, ?, ?, ?, ?, 'archived', CURRENT_TIMESTAMP)
                        ON CONFLICT(index_name) DO UPDATE SET
                            record_count = excluded.record_count,
                            file_size_bytes = excluded.file_size_bytes,
                            status = 'archived'
                    """, (index_name, date_key, date_key, len(log_list), archive_path, file_size))
                    archived_count += 1
                except Exception as e:
                    print(f"Error archiving log for {date_key}: {e}")

            conn.commit()

        return {"archived_files": archived_count, "message": f"Archived {archived_count} daily log sets."}

    def consolidate_monthly_archives(self) -> dict:
        """
        Step 2: When daily archives reach 30 days old, consolidates them
        into unified monthly tar.gz bundles (access-YYYY-MM.tar.gz), similar to Graylog index deflector merging
        """
        now = datetime.now(timezone.utc)
        threshold_date = (now - timedelta(days=config.LOG_CONSOLIDATION_DAYS)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM archive_indices
                WHERE period_type = 'daily'
                  AND status = 'archived'
                  AND end_date <= ?
                ORDER BY start_date ASC
            """, (threshold_date,))
            eligible_rows = cursor.fetchall()

        if not eligible_rows:
            return {"consolidated_months": 0, "message": "No archives eligible for 30-day consolidation."}

        # Group by month (YYYY-MM)
        by_month = {}
        for r in eligible_rows:
            month_key = r["start_date"][:7] # e.g. 2026-09
            if month_key not in by_month:
                by_month[month_key] = []
            by_month[month_key].append(r)

        consolidated_months = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for month_key, rows in by_month.items():
                tar_filename = f"access-{month_key}.tar.gz"
                tar_path = os.path.join(self.monthly_archive_dir, tar_filename)
                monthly_index = f"idx_monthly_{month_key}"

                try:
                    total_records = 0
                    with tarfile.open(tar_path, "w:gz") as tar:
                        for row in rows:
                            file_path = row["file_path"]
                            if os.path.exists(file_path):
                                tar.add(file_path, arcname=os.path.basename(file_path))
                                total_records += row["record_count"]

                    tar_size = os.path.getsize(tar_path)
                    start_date = min(r["start_date"] for r in rows)
                    end_date = max(r["end_date"] for r in rows)

                    # Register monthly bundle in index catalog
                    cursor.execute("""
                        INSERT INTO archive_indices (
                            index_name, period_type, start_date, end_date,
                            record_count, file_path, file_size_bytes, status, created_at
                        ) VALUES (?, 'monthly_consolidated', ?, ?, ?, ?, ?, 'consolidated', CURRENT_TIMESTAMP)
                        ON CONFLICT(index_name) DO UPDATE SET
                            record_count = excluded.record_count,
                            file_size_bytes = excluded.file_size_bytes,
                            status = 'consolidated'
                    """, (monthly_index, start_date, end_date, total_records, tar_path, tar_size))

                    # Remove individual daily files now bundled into tar.gz
                    for row in rows:
                        file_path = row["file_path"]
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass
                        cursor.execute("""
                            UPDATE archive_indices
                            SET status = 'consolidated', file_path = ?
                            WHERE id = ?
                        """, (f"bundled_in:{monthly_index}", row["id"]))

                    consolidated_months += 1
                except Exception as e:
                    print(f"Error consolidating month {month_key}: {e}")

            conn.commit()

        return {
            "consolidated_months": consolidated_months,
            "message": f"Consolidated {consolidated_months} monthly archive sets."
        }

    def purge_expired_archives(self) -> dict:
        """
        Step 3: Rotates and deletes raw log archives older than 91 days
        to prevent disk exhaustion, matching the Graylog rotation lifecycle
        """
        now = datetime.now(timezone.utc)
        purge_threshold = (now - timedelta(days=config.LOG_PURGE_DAYS)).strftime("%Y-%m-%d")

        purged_files = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM archive_indices
                WHERE status IN ('archived', 'consolidated')
                  AND end_date < ?
            """, (purge_threshold,))
            expired_rows = cursor.fetchall()

            for r in expired_rows:
                file_path = r["file_path"]
                if file_path and os.path.exists(file_path) and not file_path.startswith("bundled_in:"):
                    try:
                        os.remove(file_path)
                        purged_files += 1
                    except Exception as e:
                        print(f"Error deleting expired archive {file_path}: {e}")

                cursor.execute("""
                    UPDATE archive_indices
                    SET status = 'purged', purged_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (r["id"],))

            conn.commit()

        return {
            "purged_files": purged_files,
            "threshold_date": purge_threshold,
            "message": f"Purged {purged_files} raw log archives older than {config.LOG_PURGE_DAYS} days."
        }

    def purge_expired_metrics(self) -> dict:
        """
        Step 4: Prunes aggregated summary metrics exceeding 365 days retention
        """
        now = datetime.now(timezone.utc)
        cutoff_date = (now - timedelta(days=config.METRICS_RETENTION_DAYS)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM daily_metrics WHERE date < ?", (cutoff_date,))
            deleted_rows = cursor.rowcount
            conn.commit()

        return {
            "deleted_rows": deleted_rows,
            "cutoff_date": cutoff_date,
            "message": f"Pruned {deleted_rows} daily metric records older than {config.METRICS_RETENTION_DAYS} days."
        }

    def run_full_lifecycle(self, recent_logs: list = None) -> dict:
        """Executes full Graylog-style retention pipeline: Archive > Consolidate > Purge > Prune"""
        res_archive = self.archive_daily_logs(recent_logs or [])
        res_consolidate = self.consolidate_monthly_archives()
        res_purge = self.purge_expired_archives()
        res_prune = self.purge_expired_metrics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "archive": res_archive,
            "consolidation": res_consolidate,
            "purge": res_purge,
            "metrics_prune": res_prune
        }

    def get_retention_overview(self) -> dict:
        """Returns comprehensive retention metrics, disk usage, and index catalog for the UI"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_days FROM daily_metrics")
            metrics_days_count = cursor.fetchone()["total_days"]

            cursor.execute("SELECT MIN(date) as oldest_metric, MAX(date) as newest_metric FROM daily_metrics")
            metric_range = cursor.fetchone()

            cursor.execute("""
                SELECT 
                    COUNT(*) as total_indices,
                    SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) as active_daily_count,
                    SUM(CASE WHEN status = 'consolidated' THEN 1 ELSE 0 END) as consolidated_count,
                    SUM(CASE WHEN status = 'purged' THEN 1 ELSE 0 END) as purged_count,
                    SUM(CASE WHEN status IN ('archived', 'consolidated') THEN file_size_bytes ELSE 0 END) as total_archive_bytes
                FROM archive_indices
            """)
            stats = cursor.fetchone()

            cursor.execute("""
                SELECT * FROM archive_indices
                ORDER BY id DESC
                LIMIT 30
            """)
            recent_indices = [dict(r) for r in cursor.fetchall()]

        return {
            "policy": {
                "metrics_retention_days": config.METRICS_RETENTION_DAYS,
                "daily_archive_days": config.LOG_ARCHIVE_DAYS,
                "monthly_consolidation_days": config.LOG_CONSOLIDATION_DAYS,
                "log_purge_days": config.LOG_PURGE_DAYS
            },
            "metrics_storage": {
                "recorded_days": metrics_days_count,
                "oldest_metric_date": metric_range["oldest_metric"] or "-",
                "newest_metric_date": metric_range["newest_metric"] or "-",
                "retention_cap_days": config.METRICS_RETENTION_DAYS
            },
            "archive_lifecycle": {
                "total_indices": stats["total_indices"] or 0,
                "daily_active_archives": stats["active_daily_count"] or 0,
                "consolidated_bundles": stats["consolidated_count"] or 0,
                "purged_indices": stats["purged_count"] or 0,
                "disk_usage_bytes": stats["total_archive_bytes"] or 0,
                "storage_path": self.data_dir
            },
            "recent_indices": recent_indices
        }

retention_manager = RetentionManager()
