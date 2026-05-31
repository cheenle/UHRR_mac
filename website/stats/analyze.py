#!/usr/bin/env python3
"""MRRC Website Statistics Analyzer — parse Apache logs, store in SQLite, generate HTML dashboard."""

import sqlite3
import os
import re
import json
import gzip
import subprocess
import time
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

# --- Constants ---
STATS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(STATS_DIR, "stats.db")
HTML_PATH = os.path.join(STATS_DIR, "index.html")
MMDB_PATH = os.path.join(STATS_DIR, "GeoLite2-Country.mmdb")
LOG_FILE = "/var/log/apache2/other_vhosts_access.log"
LOG_GLOB = "/var/log/apache2/other_vhosts_access.log*"
CST = timezone(timedelta(hours=8))
HITS_RETENTION_DAYS = 30
VLSC_HOST_PATTERN = re.compile(r"^www\.vlsc\.net")

# UA parsing — bot tokens (lowercase)
BOT_TOKENS = [
    "googlebot", "bingbot", "baiduspider", "yandexbot", "slurp", "duckduckbot",
    "ahrefsbot", "semrushbot", "petalbot", "bytespider", "facebookexternalhit",
    "twitterbot", "libredtail-http", "nuclei", "nikto", "nmap", "zgrab", "masscan",
    "go-http-client", "python-requests", "curl", "wget", "censys", "shodan",
    "netcraft", "gobuster", "dirbuster", "nessus", "burp", "sqlmap",
]

# Scanner paths (heuristic — flag regardless of UA)
SCANNER_PATH_TOKENS = [
    "cgi-bin", ".env", "wp-admin", "admin.php", "config.php", ".git/",
    "phpmyadmin", "wp-login", "xmlrpc", ".asp", "phpunit", "actuator",
    "geoserver", "web/config", "sdk/weblanguage", "hello.world",
]

# Apache combined vhost log regex
LOG_RE = re.compile(
    r'^(\S+)\s+'                          # vhost:port
    r'(\S+)\s+'                           # IP
    r'(\S+)\s+'                           # ident
    r'(\S+)\s+'                           # auth
    r'\[([^\]]+)\]\s+'                    # [timestamp]
    r'"(\S+)\s+(\S+)\s+(\S+)"\s+'        # "METHOD /path PROTO"
    r'(\d{3})\s+'                         # status
    r'(\S+)\s+'                           # bytes (- or number)
    r'"([^"]*)"\s+'                       # "referer"
    r'"([^"]*)"$'                         # "user-agent"
)


_MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

def parse_timestamp(ts_str):
    """Parse Apache [DD/Mon/YYYY:HH:MM:SS +TZ] to ISO 8601 in CST.
    Uses manual month map to avoid locale-dependent strptime %b."""
    # Format: DD/Mon/YYYY:HH:MM:SS +TZ
    date_part, time_part = ts_str.split(":", 1)  # DD/Mon/YYYY, HH:MM:SS +TZ
    day, mon, year = date_part.split("/")
    month = _MONTH_MAP[mon]

    # Parse time and timezone
    time_rest = time_part.rsplit(" ", 1)  # ["HH:MM:SS", "+TZ"]
    h, m, s = time_rest[0].split(":")
    tz_str = time_rest[1]

    # Parse timezone offset
    tz_sign = 1 if tz_str[0] == "+" else -1
    tz_h = int(tz_str[1:3])
    tz_m = int(tz_str[3:5])
    tz_offset = timezone(timedelta(hours=tz_sign * tz_h, minutes=tz_sign * tz_m))

    t = datetime(int(year), month, int(day), int(h), int(m), int(s), tzinfo=tz_offset)
    local = t.astimezone(CST)
    return local.strftime("%Y-%m-%dT%H:%M:%S"), local.strftime("%Y-%m-%d")


def read_log_lines(filepath):
    """Read all lines from a log file (plain text or gzip).
    Uses sudo cat via subprocess since logs are root:adm 640."""
    try:
        result = subprocess.run(
            ["sudo", "cat", filepath],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  WARNING: sudo cat {filepath} failed: {result.stderr.strip()}")
            return []
        raw = result.stdout
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return []

    if raw[:2] == b"\x1f\x8b":
        import io
        return gzip.open(io.BytesIO(raw), "rt", errors="replace").readlines()

    return raw.decode("utf-8", errors="replace").splitlines()


def parse_log_line(line):
    """Parse one Apache combined vhost log line. Returns dict or None if no match."""
    m = LOG_RE.match(line)
    if not m:
        return None
    vhost, ip, ident, auth, ts_raw, method, path, proto, status, bytes_str, referer, ua = m.groups()

    if not VLSC_HOST_PATTERN.match(vhost):
        return None

    ts_iso, ts_date = parse_timestamp(ts_raw)
    try:
        status = int(status)
    except ValueError:
        status = 0
    try:
        b = int(bytes_str)
    except ValueError:
        b = 0

    return {
        "ts": ts_iso,
        "date": ts_date,
        "vhost": vhost,
        "ip": ip,
        "method": method,
        "path": path,
        "status": status,
        "bytes": b,
        "referer": referer,
        "ua": ua,
    }


def parse_ua(ua_str):
    """Extract browser and OS from UA string. Returns (browser, os_name, is_bot)."""
    ua_lower = ua_str.lower() if ua_str else ""

    # Bot detection
    is_bot = 0
    for token in BOT_TOKENS:
        if token in ua_lower:
            is_bot = 1
            break

    # Browser
    browser = "Other"
    if "edg/" in ua_lower:
        browser = "Edge"
    elif "chrome/" in ua_lower and "samsungbrowser" not in ua_lower:
        browser = "Chrome"
    elif "safari/" in ua_lower and "chrome/" not in ua_lower:
        browser = "Safari"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "opera" in ua_lower or "opr/" in ua_lower:
        browser = "Opera"
    elif "samsungbrowser" in ua_lower:
        browser = "Samsung Internet"
    elif "qqbrowser" in ua_lower:
        browser = "QQ Browser"
    elif is_bot:
        browser = "Bot"

    # OS
    os_name = "Other"
    if "windows nt" in ua_lower:
        os_name = "Windows"
    elif "mac os x" in ua_lower:
        os_name = "macOS"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    elif "linux" in ua_lower and "android" not in ua_lower:
        os_name = "Linux"
    elif "cros" in ua_lower:
        os_name = "ChromeOS"

    return browser, os_name, is_bot


def is_scanner_path(path):
    """Check if path matches known scanner/exploit patterns."""
    path_lower = path.lower() if path else ""
    for token in SCANNER_PATH_TOKENS:
        if token in path_lower:
            return True
    # Also flag suspicious encoding patterns
    if "%2e%2e" in path_lower or "%%32%%65" in path_lower or "%ADd+" in path_lower:
        return True
    return False


_geoip_reader = None


def init_geoip():
    """Lazily load the MaxMind GeoIP database."""
    global _geoip_reader
    if _geoip_reader is not None:
        return _geoip_reader
    if not os.path.exists(MMDB_PATH):
        print("  WARNING: GeoIP database not found at", MMDB_PATH)
        return None
    try:
        import maxminddb
        _geoip_reader = maxminddb.open_database(MMDB_PATH)
        return _geoip_reader
    except ImportError:
        print("  WARNING: maxminddb not installed. Run: pip3 install maxminddb")
        return None
    except Exception as e:
        print(f"  WARNING: Failed to open GeoIP database: {e}")
        return None


def lookup_country(ip):
    """Look up country name for an IP. Returns 'Unknown' on failure."""
    reader = init_geoip()
    if reader is None:
        return "Unknown"
    try:
        result = reader.get(ip)
        if result and "country" in result:
            return result["country"]["names"].get("en", "Unknown")
    except Exception:
        pass
    return "Unknown"


def country_flag(country_name):
    """Return emoji flag + country name for known countries."""
    country_to_code = {
        "United States": "\U0001f1fa\U0001f1f8", "China": "\U0001f1e8\U0001f1f3", "Japan": "\U0001f1ef\U0001f1f5",
        "Germany": "\U0001f1e9\U0001f1ea", "United Kingdom": "\U0001f1ec\U0001f1e7", "France": "\U0001f1eb\U0001f1f7",
        "Canada": "\U0001f1e8\U0001f1e6", "Australia": "\U0001f1e6\U0001f1fa", "South Korea": "\U0001f1f0\U0001f1f7",
        "Russia": "\U0001f1f7\U0001f1fa", "Brazil": "\U0001f1e7\U0001f1f7", "India": "\U0001f1ee\U0001f1f3",
        "Singapore": "\U0001f1f8\U0001f1ec", "Netherlands": "\U0001f1f3\U0001f1f1", "Sweden": "\U0001f1f8\U0001f1ea",
        "Switzerland": "\U0001f1e8\U0001f1ed", "Taiwan": "\U0001f1f9\U0001f1fc", "Hong Kong": "\U0001f1ed\U0001f1f0",
        "Italy": "\U0001f1ee\U0001f1f9", "Spain": "\U0001f1ea\U0001f1f8", "Poland": "\U0001f1f5\U0001f1f1", "Ukraine": "\U0001f1fa\U0001f1e6",
        "Thailand": "\U0001f1f9\U0001f1ed", "Vietnam": "\U0001f1fb\U0001f1f3", "Indonesia": "\U0001f1ee\U0001f1e9",
        "Malaysia": "\U0001f1f2\U0001f1fe", "Philippines": "\U0001f1f5\U0001f1ed", "Finland": "\U0001f1eb\U0001f1ee",
        "Norway": "\U0001f1f3\U0001f1f4", "Denmark": "\U0001f1e9\U0001f1f0", "Belgium": "\U0001f1e7\U0001f1ea",
        "Austria": "\U0001f1e6\U0001f1f9", "Czechia": "\U0001f1e8\U0001f1ff", "Ireland": "\U0001f1ee\U0001f1ea",
        "New Zealand": "\U0001f1f3\U0001f1ff", "Mexico": "\U0001f1f2\U0001f1fd", "Argentina": "\U0001f1e6\U0001f1f7",
        "Turkey": "\U0001f1f9\U0001f1f7", "Israel": "\U0001f1ee\U0001f1f1", "United Arab Emirates": "\U0001f1e6\U0001f1ea",
    }
    code = country_to_code.get(country_name, "\U0001f310")
    return f"{code} {country_name}"


def init_db():
    """Create tables and indexes if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS hits (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT NOT NULL,
            vhost      TEXT,
            ip         TEXT,
            method     TEXT,
            path       TEXT,
            status     INTEGER,
            bytes      INTEGER,
            referer    TEXT,
            ua         TEXT,
            ua_browser TEXT,
            ua_os      TEXT,
            is_bot     INTEGER DEFAULT 0,
            is_404     INTEGER DEFAULT 0,
            country    TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hits_ts ON hits(ts);
        CREATE INDEX IF NOT EXISTS idx_hits_path ON hits(path);
        CREATE TABLE IF NOT EXISTS daily_summary (
            date          TEXT PRIMARY KEY,
            pv            INTEGER DEFAULT 0,
            uv            INTEGER DEFAULT 0,
            bytes_total   INTEGER DEFAULT 0,
            status_2xx    INTEGER DEFAULT 0,
            status_3xx    INTEGER DEFAULT 0,
            status_4xx    INTEGER DEFAULT 0,
            status_5xx    INTEGER DEFAULT 0,
            top_pages     TEXT,
            top_refs      TEXT,
            top_countries TEXT,
            bots_pct      REAL
        );
    """)
    conn.commit()
    return conn


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
