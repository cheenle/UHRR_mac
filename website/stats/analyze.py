#!/usr/bin/env python3
"""MRRC Website Statistics Analyzer — parse Apache logs, store in SQLite, generate HTML dashboard."""

import sqlite3
import os
import re
import json
import gzip
import subprocess
import hashlib
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
    """Lazily load the MaxMind GeoIP database. Returns reader or None (warns once)."""
    global _geoip_reader
    if _geoip_reader is not None:
        return _geoip_reader if _geoip_reader is not False else None
    if not os.path.exists(MMDB_PATH):
        print("  WARNING: GeoIP database not found at", MMDB_PATH)
        _geoip_reader = False
        return None
    try:
        import maxminddb
        _geoip_reader = maxminddb.open_database(MMDB_PATH)
        return _geoip_reader
    except ImportError:
        print("  WARNING: maxminddb not installed. Run: pip3 install maxminddb")
        _geoip_reader = False
        return None
    except Exception as e:
        print(f"  WARNING: Failed to open GeoIP database: {e}")
        _geoip_reader = False
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


def get_parse_state(conn):
    """Get the last parse position and inode from meta table."""
    cur = conn.execute("SELECT key, value FROM meta WHERE key IN ('log_file', 'position', 'inode')")
    state = dict(cur.fetchall())
    return {
        "log_file": state.get("log_file", LOG_FILE),
        "position": int(state.get("position", 0)),
        "inode": int(state.get("inode", 0)),
    }


def save_parse_state(conn, log_file, position, inode):
    """Save current parse state to meta table."""
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('log_file', ?)", (log_file,))
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('position', ?)", (str(position),))
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('inode', ?)", (str(inode),))
    conn.commit()


def ingest_logs(conn):
    """Incrementally parse logs and insert new hits. Returns count of new hits inserted."""
    # Check current log file state
    try:
        result = subprocess.run(
            ["sudo", "stat", "-c", "%i %s", LOG_FILE],
            capture_output=True, text=True, timeout=5
        )
        current_inode, current_size = map(int, result.stdout.strip().split())
    except Exception as e:
        print(f"  ERROR: Cannot stat log file: {e}")
        return 0

    state = get_parse_state(conn)
    prev_inode = state["inode"]
    prev_position = state["position"]

    # Log rotation detected
    if prev_inode != 0 and prev_inode != current_inode:
        # Process old file from prev_position to end
        old_log = state["log_file"]
        print(f"  Log rotated. Processing remaining data from {old_log}")
        old_lines = read_log_lines(old_log)
        new_from_old = _insert_from_lines(conn, old_lines[prev_position:])
        print(f"  Got {new_from_old} hits from rotated log tail")

        # Now process all historical rotated files
        _ingest_historical_logs(conn)

        # Reset for current log
        prev_position = 0

    # No new data
    if prev_position >= current_size and prev_inode == current_inode:
        print(f"  No new data (position={prev_position}, size={current_size})")
        return 0

    # Read new content from current log
    lines = read_log_lines(LOG_FILE)
    new_lines = lines[prev_position:] if prev_position < len(lines) else []
    new_count = _insert_from_lines(conn, new_lines)

    save_parse_state(conn, LOG_FILE, current_size, current_inode)
    print(f"  Inserted {new_count} new hits (position now {current_size})")
    return new_count


def _insert_from_lines(conn, lines):
    """Parse lines and insert into hits table. Returns count."""
    count = 0
    cur = conn.cursor()
    for line in lines:
        parsed = parse_log_line(line.strip())
        if parsed is None:
            continue
        browser, os_name, is_bot = parse_ua(parsed["ua"])
        if not is_bot and is_scanner_path(parsed["path"]):
            is_bot = 1
        country = lookup_country(parsed["ip"])
        is_404 = 1 if parsed["status"] == 404 else 0
        cur.execute(
            """INSERT INTO hits (ts, vhost, ip, method, path, status, bytes, referer, ua,
               ua_browser, ua_os, is_bot, is_404, country)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (parsed["ts"], parsed["vhost"], parsed["ip"], parsed["method"],
             parsed["path"], parsed["status"], parsed["bytes"], parsed["referer"],
             parsed["ua"], browser, os_name, is_bot, is_404, country)
        )
        count += 1
    conn.commit()
    return count


def _ingest_historical_logs(conn):
    """Process all rotated log files we haven't seen before."""
    import glob
    seen_key = "historical_processed"
    cur = conn.execute("SELECT value FROM meta WHERE key=?", (seen_key,))
    row = cur.fetchone()
    processed = set(row[0].split(",")) if row else set()

    for fpath in sorted(glob.glob(LOG_GLOB)):
        if fpath == LOG_FILE:
            continue
        if fpath in processed:
            continue
        print(f"  Processing historical log: {fpath}")
        lines = read_log_lines(fpath)
        n = _insert_from_lines(conn, lines)
        print(f"    Inserted {n} hits from {fpath}")
        processed.add(fpath)

    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (seen_key, ",".join(processed)))
    conn.commit()


def cleanup_old_hits(conn):
    """Delete hits older than retention period."""
    cutoff = datetime.now(CST) - timedelta(days=HITS_RETENTION_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%dT00:00:00")
    cur = conn.execute("DELETE FROM hits WHERE ts < ?", (cutoff_str,))
    deleted = cur.rowcount
    if deleted:
        print(f"  Cleaned up {deleted} old hits (before {cutoff_str})")
    conn.commit()


def update_daily_summary(conn):
    """Update daily_summary table for today based on current hits data."""
    today = datetime.now(CST).strftime("%Y-%m-%d")

    cur = conn.execute("""
        SELECT
            COUNT(*) AS pv,
            COUNT(DISTINCT ip || '|' || ua) AS uv,
            SUM(bytes) AS bytes_total,
            SUM(CASE WHEN status BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS s2xx,
            SUM(CASE WHEN status BETWEEN 300 AND 399 THEN 1 ELSE 0 END) AS s3xx,
            SUM(CASE WHEN status BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS s4xx,
            SUM(CASE WHEN status BETWEEN 500 AND 599 THEN 1 ELSE 0 END) AS s5xx,
            ROUND(100.0 * SUM(is_bot) / MAX(COUNT(*), 1), 1) AS bots_pct
        FROM hits WHERE ts >= ? AND ts < ?
    """, (today + "T00:00:00", today + "T23:59:59"))
    row = cur.fetchone()

    # Top pages
    cur = conn.execute("""
        SELECT path, COUNT(*) AS c FROM hits
        WHERE ts >= ? AND ts < ? AND is_bot = 0 AND status < 400
        GROUP BY path ORDER BY c DESC LIMIT 10
    """, (today + "T00:00:00", today + "T23:59:59"))
    top_pages = json.dumps([{"path": r[0], "count": r[1]} for r in cur.fetchall()])

    # Top referrers (excluding direct/bookmark)
    cur = conn.execute("""
        SELECT referer, COUNT(*) AS c FROM hits
        WHERE ts >= ? AND ts < ? AND is_bot = 0 AND referer != '' AND referer != '-'
        GROUP BY referer ORDER BY c DESC LIMIT 10
    """, (today + "T00:00:00", today + "T23:59:59"))
    top_refs = json.dumps([{"ref": r[0], "count": r[1]} for r in cur.fetchall()])

    # Top countries
    cur = conn.execute("""
        SELECT country, COUNT(*) AS c FROM hits
        WHERE ts >= ? AND ts < ? AND is_bot = 0
        GROUP BY country ORDER BY c DESC LIMIT 10
    """, (today + "T00:00:00", today + "T23:59:59"))
    top_countries = json.dumps([{"country": r[0], "count": r[1]} for r in cur.fetchall()])

    conn.execute("""
        INSERT OR REPLACE INTO daily_summary
        (date, pv, uv, bytes_total, status_2xx, status_3xx, status_4xx, status_5xx,
         top_pages, top_refs, top_countries, bots_pct)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (today, row[0], row[1], row[2] or 0, row[3], row[4], row[5], row[6],
          top_pages, top_refs, top_countries, row[7] or 0.0))
    conn.commit()
    print(f"  Updated daily_summary for {today}: PV={row[0]}, UV={row[1]}")


def query_stats(conn):
    """Collect all statistics needed for the dashboard. Returns a dict."""
    today = datetime.now(CST).strftime("%Y-%m-%d")
    month_start = datetime.now(CST).strftime("%Y-%m-01")

    def q(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return row[0]

    def qall(sql, params=()):
        return conn.execute(sql, params).fetchall()

    stats = {}

    # Overview cards
    stats["today_pv"] = q("SELECT COALESCE(SUM(pv),0) FROM daily_summary WHERE date=?", (today,))
    stats["today_uv"] = q(
        "SELECT COUNT(DISTINCT ip||'|'||ua) FROM hits WHERE ts>=? AND ts<?",
        (today+"T00:00:00", today+"T23:59:59")
    )
    stats["month_pv"] = q("SELECT COALESCE(SUM(pv),0) FROM daily_summary WHERE date>=?", (month_start,))
    stats["total_pv"] = q("SELECT COALESCE(SUM(pv),0) FROM daily_summary")

    # 24h hourly breakdown
    hourly = qall("""
        SELECT SUBSTR(ts,12,2) AS h, COUNT(*) FROM hits
        WHERE ts>=? AND ts<? AND is_bot=0
        GROUP BY h ORDER BY h
    """, (today+"T00:00:00", today+"T23:59:59"))
    stats["hourly"] = [(int(h), c) for h, c in hourly]
    stats["hourly_max"] = max([c for _, c in hourly]) if hourly else 0

    # 30-day trend
    daily = qall("""
        SELECT date, pv, uv FROM daily_summary
        WHERE date >= ? ORDER BY date
    """, ((datetime.now(CST) - timedelta(days=29)).strftime("%Y-%m-%d"),))
    stats["daily"] = [(d, pv, uv) for d, pv, uv in daily]
    daily_max = max([pv for _, pv, _ in daily]) if daily else 1
    stats["daily_max"] = daily_max

    # Top pages (today)
    stats["top_pages"] = json.loads(q(
        "SELECT top_pages FROM daily_summary WHERE date=?", (today,)
    ) or "[]")

    # Top referrers (today)
    stats["top_refs"] = json.loads(q(
        "SELECT top_refs FROM daily_summary WHERE date=?", (today,)
    ) or "[]")

    # Top countries (today)
    stats["top_countries"] = json.loads(q(
        "SELECT top_countries FROM daily_summary WHERE date=?", (today,)
    ) or "[]")

    # Browser distribution (today)
    browser_rows = qall("""
        SELECT ua_browser, COUNT(*) AS c FROM hits
        WHERE ts>=? AND ts<? AND is_bot=0
        GROUP BY ua_browser ORDER BY c DESC
    """, (today+"T00:00:00", today+"T23:59:59"))
    total_browser = sum(c for _, c in browser_rows) or 1
    stats["browsers"] = [(b, c, round(100*c/total_browser,1)) for b, c in browser_rows]

    # OS distribution (today)
    os_rows = qall("""
        SELECT ua_os, COUNT(*) AS c FROM hits
        WHERE ts>=? AND ts<? AND is_bot=0
        GROUP BY ua_os ORDER BY c DESC
    """, (today+"T00:00:00", today+"T23:59:59"))
    total_os = sum(c for _, c in os_rows) or 1
    stats["os_list"] = [(o, c, round(100*c/total_os,1)) for o, c in os_rows]

    # Anomaly footer
    stats["today_404"] = q(
        "SELECT COUNT(*) FROM hits WHERE ts>=? AND ts<? AND status=404",
        (today+"T00:00:00", today+"T23:59:59")
    )
    stats["bots_pct"] = q(
        "SELECT COALESCE(bots_pct,0) FROM daily_summary WHERE date=?", (today,)
    ) or 0.0
    stats["total_hits_today"] = q(
        "SELECT COUNT(*) FROM hits WHERE ts>=? AND ts<?",
        (today+"T00:00:00", today+"T23:59:59")
    )

    # Suspicious scanner IPs
    suspicious = qall("""
        SELECT ip, COUNT(*) AS c, GROUP_CONCAT(DISTINCT SUBSTR(path,1,80)) AS paths FROM hits
        WHERE ts>=? AND ts<? AND is_bot=1
        GROUP BY ip HAVING c >= 3 ORDER BY c DESC LIMIT 5
    """, (today+"T00:00:00", today+"T23:59:59"))
    stats["suspicious"] = [(ip, c, paths) for ip, c, paths in suspicious]

    # Last update timestamp
    stats["last_update"] = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S CST")
    stats["next_update"] = (datetime.now(CST) + timedelta(hours=1)).strftime("%Y-%m-%d %H:00:00 CST")

    return stats


def _pct_bar(pct, color="#00d4ff"):
    """Render a percentage bar for distribution lists."""
    return f'<div class="pct-bar-bg"><div class="pct-bar-fill" style="width:{pct}%;background:{color}"></div></div>'


# --- Per-Page Analytics ---

PAGES_DIR = os.path.join(STATS_DIR, "pages")
TOP_PAGES_LIMIT = 100


def _path_slug(path):
    """Stable short identifier for a URL path."""
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _slug_for_path(conn, path):
    """Ensure a slug exists for a path and return it."""
    slug = _path_slug(path)
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                 (f"page_slug:{slug}", path))
    conn.commit()
    return slug


def _path_for_slug(conn, slug):
    """Reverse-lookup a path from its slug."""
    row = conn.execute("SELECT value FROM meta WHERE key=?",
                       (f"page_slug:{slug}",)).fetchone()
    return row[0] if row else None


def query_page_stats(conn, path):
    """Collect all statistics for a single page path. Returns a dict."""
    today = datetime.now(CST).strftime("%Y-%m-%d")

    def q(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    def qall(sql, params=()):
        return conn.execute(sql, params).fetchall()

    s = {}
    s["path"] = path

    # Overview
    s["total_pv"] = q("SELECT COUNT(*) FROM hits WHERE path=? AND is_bot=0", (path,))
    s["total_pv_raw"] = q("SELECT COUNT(*) FROM hits WHERE path=?", (path,))
    uv = q("SELECT COUNT(DISTINCT ip||'|'||ua) FROM hits WHERE path=? AND is_bot=0", (path,))
    s["total_uv"] = uv
    s["bot_pct"] = round(100 * (s["total_pv_raw"] - s["total_pv"]) / max(s["total_pv_raw"], 1), 1)
    s["count_404"] = q("SELECT COUNT(*) FROM hits WHERE path=? AND status=404", (path,))

    # 30-day trend
    daily = qall("""
        SELECT SUBSTR(ts,1,10) AS d, COUNT(*) AS c,
               COUNT(DISTINCT ip||'|'||ua) AS u
        FROM hits WHERE path=? AND is_bot=0
          AND ts >= ?
        GROUP BY d ORDER BY d
    """, (path, (datetime.now(CST) - timedelta(days=29)).strftime("%Y-%m-%d")))
    s["daily"] = [(d, c, u) for d, c, u in daily]
    s["daily_max"] = max([c for _, c, _ in daily]) if daily else 1

    # 24h hourly (today)
    hourly = qall("""
        SELECT SUBSTR(ts,12,2) AS h, COUNT(*) FROM hits
        WHERE path=? AND is_bot=0 AND ts>=? AND ts<?
        GROUP BY h ORDER BY h
    """, (path, today + "T00:00:00", today + "T23:59:59"))
    s["hourly"] = [(int(h), c) for h, c in hourly]
    s["hourly_max"] = max([c for _, c in hourly]) if hourly else 0

    # Top referrers
    refs = qall("""
        SELECT referer, COUNT(*) AS c FROM hits
        WHERE path=? AND is_bot=0 AND referer != '' AND referer != '-'
        GROUP BY referer ORDER BY c DESC LIMIT 10
    """, (path,))
    s["top_refs"] = [{"ref": r[0], "count": r[1]} for r in refs]

    # Top countries
    countries = qall("""
        SELECT country, COUNT(*) AS c FROM hits
        WHERE path=? AND is_bot=0
        GROUP BY country ORDER BY c DESC LIMIT 10
    """, (path,))
    s["top_countries"] = [{"country": r[0], "count": r[1]} for r in countries]

    # Browsers
    browsers = qall("""
        SELECT ua_browser, COUNT(*) AS c FROM hits
        WHERE path=? AND is_bot=0
        GROUP BY ua_browser ORDER BY c DESC LIMIT 5
    """, (path,))
    total_b = sum(c for _, c in browsers) or 1
    s["browsers"] = [(b, c, round(100 * c / total_b, 1)) for b, c in browsers]

    # OS
    os_list = qall("""
        SELECT ua_os, COUNT(*) AS c FROM hits
        WHERE path=? AND is_bot=0
        GROUP BY ua_os ORDER BY c DESC LIMIT 5
    """, (path,))
    total_o = sum(c for _, c in os_list) or 1
    s["os_list"] = [(o, c, round(100 * c / total_o, 1)) for o, c in os_list]

    return s


def render_page_html(stats, all_pages):
    """Generate HTML for a single page detail dashboard."""
    path = stats["path"]

    # 24h hourly bars
    hour_bars = ""
    for h in range(24):
        height_pct = 0
        count = 0
        for hh, c in stats["hourly"]:
            if hh == h:
                count = c
                height_pct = int(c / max(stats["hourly_max"], 1) * 100)
                break
        peak_class = 'peak' if count == stats["hourly_max"] and count > 0 else ''
        hour_bars += f'<div class="hour-col"><div class="hour-bar {peak_class}" style="height:{height_pct}%"></div><span class="hour-label">{h:02d}</span></div>'

    # 30-day SVG
    svg_points_pv = ""
    svg_points_uv = ""
    if stats["daily"]:
        max_val = stats["daily_max"]
        w_step = 780.0 / max(len(stats["daily"]) - 1, 1)
        for i, (d, pv, uv) in enumerate(stats["daily"]):
            x = i * w_step + 40
            y_pv = 200 - (pv / max_val * 180) if max_val > 0 else 200
            y_uv = 200 - (uv / max_val * 180) if max_val > 0 else 200
            svg_points_pv += f"{x:.1f},{y_pv:.1f} "
            svg_points_uv += f"{x:.1f},{y_uv:.1f} "

    # Referrers table
    refs_html = ""
    for item in stats["top_refs"]:
        ref = item["ref"][:60]
        refs_html += f'<tr><td class="mono">{ref}</td><td>{item["count"]}</td></tr>'
    if not refs_html:
        refs_html = '<tr><td colspan="2" class="empty">No referrer data</td></tr>'

    # Countries
    countries_html = ""
    for item in stats["top_countries"]:
        name = country_flag(item["country"])
        countries_html += f'<tr><td>{name}</td><td>{item["count"]}</td></tr>'
    if not countries_html:
        countries_html = '<tr><td colspan="2" class="empty">No GeoIP data</td></tr>'

    # Browsers
    browser_html = ""
    for name, count, pct in stats["browsers"]:
        browser_html += f'<div class="dist-row"><span class="dist-label">{name}</span><span class="dist-value">{pct}%</span>{_pct_bar(pct)}</div>'
    if not browser_html:
        browser_html = '<div class="empty">No data</div>'

    # OS
    os_html = ""
    for name, count, pct in stats["os_list"]:
        os_html += f'<div class="dist-row"><span class="dist-label">{name}</span><span class="dist-value">{pct}%</span>{_pct_bar(pct, "#7c3aed")}</div>'
    if not os_html:
        os_html = '<div class="empty">No data</div>'

    # Breadcrumb snippet
    breadcrumb = '<a href=".">All Pages</a> &rsaquo; <span>' + path[:80] + '</span>'

    # Footer nav: prev/next among all_pages
    idx = next((i for i, p in enumerate(all_pages) if p[0] == path), -1)
    prev_link = ""
    next_link = ""
    if idx > 0:
        prev_link = f'<a href="{_path_slug(all_pages[idx-1][0])}.html">&larr; Prev</a>'
    if idx >= 0 and idx < len(all_pages) - 1:
        next_link = f'<a href="{_path_slug(all_pages[idx+1][0])}.html">Next &rarr;</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>{path[:60]} — MRRC Page Analytics</title>
<style>
:root {{
    --primary: #00d4ff;
    --primary-dark: #0099cc;
    --purple: #7c3aed;
    --bg-dark: #0a0a0f;
    --bg-card: #13131f;
    --bg-light: #1e1e2e;
    --text: #ffffff;
    --text-secondary: #a0a0b0;
    --text-muted: #6b7280;
    --border: #2d2d3d;
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-dark); color: var(--text);
    line-height: 1.6; min-height: 100vh;
}}
.mono {{ font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.85rem; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

/* Header */
.header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 24px 0; border-bottom: 1px solid var(--border); margin-bottom: 32px;
    flex-wrap: wrap; gap: 12px;
}}
.header h1 {{ font-size: 1.3rem; color: var(--primary); word-break: break-all; }}
.header-meta {{ color: var(--text-muted); font-size: 0.85rem; }}
.breadcrumb {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; }}
.breadcrumb a {{ color: var(--primary); text-decoration: none; }}
.breadcrumb a:hover {{ text-decoration: underline; }}

/* Page nav */
.page-nav {{ display: flex; justify-content: space-between; margin-bottom: 24px; }}
.page-nav a {{ color: var(--primary); text-decoration: none; font-size: 0.9rem; }}
.page-nav a:hover {{ text-decoration: underline; }}

/* Overview cards */
.cards {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 32px; }}
.card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; text-align: center;
}}
.card-number {{ font-size: 2rem; font-weight: 700; color: var(--primary);
    font-family: 'JetBrains Mono', monospace; }}
.card-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px; }}

/* Section */
.section {{ margin-bottom: 32px; }}
.section-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; color: var(--text); }}

/* 24h chart */
.hour-chart {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px;
    display: flex; align-items: flex-end; gap: 4px; height: 180px;
}}
.hour-col {{ flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end; }}
.hour-bar {{
    width: 100%; max-width: 32px; background: var(--bg-light);
    border-radius: 4px 4px 0 0; min-height: 2px; transition: height 0.3s;
}}
.hour-bar.peak {{ background: var(--primary); box-shadow: 0 0 12px rgba(0,212,255,0.5); }}
.hour-label {{ font-size: 0.65rem; color: var(--text-muted); margin-top: 6px; }}

/* 30-day SVG */
.trend-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; overflow-x: auto;
}}
.legend {{ display: flex; gap: 24px; margin-bottom: 8px; font-size: 0.85rem; }}
.legend-pv {{ color: var(--primary); }}
.legend-uv {{ color: var(--purple); }}

/* Grid */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}

/* Tables */
.table-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid rgba(45,45,61,0.5); font-size: 0.9rem; }}
.empty {{ color: var(--text-muted); font-style: italic; padding: 16px; text-align: center; }}
.small {{ font-size: 0.75rem; }}

/* Distribution bars */
.dist-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.dist-label {{ width: 100px; font-size: 0.85rem; flex-shrink: 0; }}
.dist-value {{ width: 45px; font-size: 0.85rem; color: var(--text-secondary); text-align: right; }}
.pct-bar-bg {{ flex:1; height: 8px; background: var(--bg-light); border-radius: 4px; overflow: hidden; }}
.pct-bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}

/* Back link */
.back-link {{ display: inline-block; margin-top: 32px; color: var(--primary);
    text-decoration: none; font-size: 0.9rem; }}
.back-link:hover {{ text-decoration: underline; }}

/* Responsive */
@media (max-width: 768px) {{
    .cards {{ grid-template-columns: repeat(2,1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
    .hour-chart {{ height: 120px; }}
}}
@media (max-width: 480px) {{
    .cards {{ grid-template-columns: 1fr; }}
    .header {{ flex-direction: column; text-align: center; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="breadcrumb">{breadcrumb}</div>

<div class="header">
    <div><h1 class="mono">{path[:100]}</h1></div>
    <div class="header-meta">MRRC Page Analytics</div>
</div>

<div class="page-nav">{prev_link}{next_link}</div>

<!-- Overview Cards -->
<div class="cards">
    <div class="card"><div class="card-number">{stats["total_pv"]:,}</div><div class="card-label">Total PV</div></div>
    <div class="card"><div class="card-number">{stats["total_uv"]:,}</div><div class="card-label">Total UV</div></div>
    <div class="card"><div class="card-number">{stats["bot_pct"]}%</div><div class="card-label">Bot Traffic</div></div>
    <div class="card"><div class="card-number">{stats["count_404"]:,}</div><div class="card-label">404 Errors</div></div>
</div>

<!-- 24h Hourly -->
<div class="section">
    <div class="section-title">\U0001f4c8 24-Hour Traffic (Today, CST)</div>
    <div class="hour-chart">{hour_bars}</div>
</div>

<!-- 30-Day Trend -->
<div class="section">
    <div class="section-title">\U0001f4c9 30-Day Trend for This Page</div>
    <div class="trend-box">
        <div class="legend"><span class="legend-pv">━ PV</span><span class="legend-uv">┅ UV</span></div>
        <svg viewBox="0 0 860 240" width="100%" height="240">
            <line x1="40" y1="20" x2="820" y2="20" stroke="#2d2d3d" stroke-dasharray="4,4"/>
            <line x1="40" y1="200" x2="820" y2="200" stroke="#2d2d3d"/>
            <line x1="40" y1="20" x2="40" y2="210" stroke="#2d2d3d"/>
            <line x1="35" y1="200" x2="820" y2="200" stroke="#2d2d3d"/>
            <polyline fill="none" stroke="#00d4ff" stroke-width="2" points="{svg_points_pv.strip()}"/>
            <polyline fill="none" stroke="#7c3aed" stroke-width="1.5" stroke-dasharray="6,4" points="{svg_points_uv.strip()}"/>
        </svg>
    </div>
</div>

<!-- Referrers + Countries -->
<div class="grid-2">
    <div class="table-box">
        <div class="section-title">\U0001f517 Referrers</div>
        <table><thead><tr><th>Source</th><th>Count</th></tr></thead><tbody>{refs_html}</tbody></table>
    </div>
    <div class="table-box">
        <div class="section-title">\U0001f30d Countries</div>
        <table><thead><tr><th>Country</th><th>Visitors</th></tr></thead><tbody>{countries_html}</tbody></table>
    </div>
</div>

<!-- Browsers + OS -->
<div class="grid-2">
    <div class="table-box">
        <div class="section-title">\U0001f5a5 Browsers</div>
        {browser_html}
    </div>
    <div class="table-box">
        <div class="section-title">\U0001f4f1 Operating Systems</div>
        {os_html}
    </div>
</div>

<a href="." class="back-link">&larr; Back to All Pages</a>

</div>
</body>
</html>"""


def render_pages_index(pages_list, conn):
    """Generate the pages directory listing HTML."""
    rows = ""
    for i, (path, pv, uv) in enumerate(pages_list):
        slug = _path_slug(path)
        rows += f'<tr><td>{i+1}</td><td><a href="{slug}.html" class="mono">{path[:80]}</a></td><td>{pv:,}</td><td>{uv:,}</td></tr>'

    total_pv = sum(p[1] for p in pages_list)
    total_uv = sum(p[2] for p in pages_list)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>MRRC Page Analytics — All Pages</title>
<style>
:root {{
    --primary: #00d4ff;
    --bg-dark: #0a0a0f;
    --bg-card: #13131f;
    --bg-light: #1e1e2e;
    --text: #ffffff;
    --text-secondary: #a0a0b0;
    --text-muted: #6b7280;
    --border: #2d2d3d;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-dark); color: var(--text);
    line-height: 1.6; min-height: 100vh;
}}
.mono {{ font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.85rem; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
.header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 24px 0; border-bottom: 1px solid var(--border); margin-bottom: 32px;
    flex-wrap: wrap; gap: 12px;
}}
.header h1 {{ font-size: 1.5rem; color: var(--primary); }}
.header-meta {{ color: var(--text-muted); font-size: 0.85rem; text-align: right; }}
.header-meta span {{ display: block; }}
.cards {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 32px; }}
.card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; text-align: center;
}}
.card-number {{ font-size: 2rem; font-weight: 700; color: var(--primary);
    font-family: 'JetBrains Mono', monospace; }}
.card-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px; }}
.table-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid rgba(45,45,61,0.5); font-size: 0.9rem; }}
td a {{ color: var(--primary); text-decoration: none; }}
td a:hover {{ text-decoration: underline; }}
.back-link {{ display: inline-block; margin-top: 32px; color: var(--primary);
    text-decoration: none; font-size: 0.9rem; }}
.back-link:hover {{ text-decoration: underline; }}
@media (max-width: 768px) {{
    .cards {{ grid-template-columns: repeat(2,1fr); }}
}}
@media (max-width: 480px) {{
    .cards {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <div><h1>\U0001f4c4 MRRC Page Analytics</h1></div>
    <div class="header-meta">
        <span>Top {len(pages_list)} pages by all-time PV</span>
    </div>
</div>

<div class="cards">
    <div class="card"><div class="card-number">{total_pv:,}</div><div class="card-label">Combined PV</div></div>
    <div class="card"><div class="card-number">{total_uv:,}</div><div class="card-label">Combined UV</div></div>
    <div class="card"><div class="card-number">{len(pages_list)}</div><div class="card-label">Pages Tracked</div></div>
</div>

<div class="table-box">
<table>
<thead><tr><th>#</th><th>Page Path</th><th>PV</th><th>UV</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>

<a href="../index.html" class="back-link">&larr; Back to Dashboard</a>

</div>
</body>
</html>"""


def generate_page_details(conn):
    """Generate per-page detail HTML files for top pages."""
    os.makedirs(PAGES_DIR, exist_ok=True)

    # Get top pages by all-time PV (excluding bots and errors)
    pages = conn.execute("""
        SELECT path, COUNT(*) AS pv,
               COUNT(DISTINCT ip||'|'||ua) AS uv
        FROM hits
        WHERE is_bot = 0 AND status < 400
        GROUP BY path
        ORDER BY pv DESC
        LIMIT ?
    """, (TOP_PAGES_LIMIT,)).fetchall()

    if not pages:
        print("  No pages found for per-page analysis")
        return

    # Build slug map
    for path, pv, uv in pages:
        _slug_for_path(conn, path)

    # Collect known slugs for cleanup
    known_slugs = {_path_slug(p[0]) for p in pages}

    print(f"  Generating detail pages for {len(pages)} pages...")

    # Generate each page detail
    for path, pv, uv in pages:
        slug = _path_slug(path)
        stats = query_page_stats(conn, path)
        all_tuples = [(p[0], p[1], p[2]) for p in pages]
        html = render_page_html(stats, all_tuples)
        fpath = os.path.join(PAGES_DIR, f"{slug}.html")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(html)

    # Generate directory listing
    pages_list = [(p[0], p[1], p[2]) for p in pages]
    index_html = render_pages_index(pages_list, conn)
    with open(os.path.join(PAGES_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # Clean up stale page files
    for fname in os.listdir(PAGES_DIR):
        if fname.endswith(".html") and fname != "index.html":
            slug = fname[:-5]  # remove .html
            if slug not in known_slugs:
                os.remove(os.path.join(PAGES_DIR, fname))
                print(f"  Removed stale page: {fname}")

    print(f"  Page analytics written to {PAGES_DIR}/")


def render_html(stats):
    """Generate complete dashboard HTML."""
    # ------- 24h hourly bars -------
    hour_bars = ""
    for h in range(24):
        height_pct = 0
        count = 0
        for hh, c in stats["hourly"]:
            if hh == h:
                count = c
                height_pct = int(c / max(stats["hourly_max"], 1) * 100)
                break
        peak_class = 'peak' if count == stats["hourly_max"] and count > 0 else ''
        hour_bars += f'<div class="hour-col"><div class="hour-bar {peak_class}" style="height:{height_pct}%"></div><span class="hour-label">{h:02d}</span></div>'

    # ------- 30-day SVG trend -------
    svg_points_pv = ""
    svg_points_uv = ""
    if stats["daily"]:
        max_val = stats["daily_max"]
        w_step = 780.0 / max(len(stats["daily"]) - 1, 1)
        for i, (d, pv, uv) in enumerate(stats["daily"]):
            x = i * w_step + 40
            y_pv = 200 - (pv / max_val * 180) if max_val > 0 else 200
            y_uv = 200 - (uv / max_val * 180) if max_val > 0 else 200
            svg_points_pv += f"{x:.1f},{y_pv:.1f} "
            svg_points_uv += f"{x:.1f},{y_uv:.1f} "

    # ------- Top pages table -------
    pages_html = ""
    for item in stats["top_pages"]:
        path = item["path"][:60]
        count = item["count"]
        pct = round(count / max(stats["today_pv"], 1) * 100)
        slug = _path_slug(item["path"])
        pages_html += f'<tr><td class="mono"><a href="pages/{slug}.html">{path}</a></td><td>{count}</td><td>{pct}%</td></tr>'
    if not pages_html:
        pages_html = '<tr><td colspan="3" class="empty">No data yet</td></tr>'

    # ------- Top referrers table -------
    refs_html = ""
    for item in stats["top_refs"]:
        ref = item["ref"][:60]
        refs_html += f'<tr><td class="mono">{ref}</td><td>{item["count"]}</td></tr>'
    if not refs_html:
        refs_html = '<tr><td colspan="2" class="empty">No referrer data yet</td></tr>'

    # ------- Top countries -------
    countries_html = ""
    for item in stats["top_countries"]:
        name = country_flag(item["country"])
        countries_html += f'<tr><td>{name}</td><td>{item["count"]}</td></tr>'
    if not countries_html:
        countries_html = '<tr><td colspan="2" class="empty">No GeoIP data</td></tr>'

    # ------- Browser & OS distributions -------
    browser_html = ""
    for name, count, pct in stats["browsers"][:8]:
        browser_html += f'<div class="dist-row"><span class="dist-label">{name}</span><span class="dist-value">{pct}%</span>{_pct_bar(pct)}</div>'
    if not browser_html:
        browser_html = '<div class="empty">No data</div>'

    os_html = ""
    for name, count, pct in stats["os_list"][:8]:
        os_html += f'<div class="dist-row"><span class="dist-label">{name}</span><span class="dist-value">{pct}%</span>{_pct_bar(pct, "#7c3aed")}</div>'
    if not os_html:
        os_html = '<div class="empty">No data</div>'

    # ------- Suspicious IPs -------
    suspicious_html = ""
    for ip, count, paths in stats["suspicious"]:
        suspicious_html += f'<tr><td class="mono">{ip}</td><td>{count}</td><td class="mono small">{paths[:80]}</td></tr>'
    if not suspicious_html:
        suspicious_html = '<tr><td colspan="3" class="empty">No suspicious activity detected</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>MRRC Website Statistics</title>
<style>
:root {{
    --primary: #00d4ff;
    --primary-dark: #0099cc;
    --purple: #7c3aed;
    --bg-dark: #0a0a0f;
    --bg-card: #13131f;
    --bg-light: #1e1e2e;
    --text: #ffffff;
    --text-secondary: #a0a0b0;
    --text-muted: #6b7280;
    --border: #2d2d3d;
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-dark); color: var(--text);
    line-height: 1.6; min-height: 100vh;
}}
.mono {{ font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.85rem; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

/* Header */
.header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 24px 0; border-bottom: 1px solid var(--border); margin-bottom: 32px;
    flex-wrap: wrap; gap: 12px;
}}
.header h1 {{ font-size: 1.5rem; color: var(--primary); }}
.header-meta {{ color: var(--text-muted); font-size: 0.85rem; text-align: right; }}
.header-meta span {{ display: block; }}

/* Overview cards */
.cards {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 32px; }}
.card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; text-align: center;
}}
.card-number {{ font-size: 2rem; font-weight: 700; color: var(--primary);
    font-family: 'JetBrains Mono', monospace; }}
.card-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px; }}

/* Section headers */
.section {{ margin-bottom: 32px; }}
.section-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; color: var(--text); }}

/* 24h chart */
.hour-chart {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px;
    display: flex; align-items: flex-end; gap: 4px; height: 180px;
}}
.hour-col {{ flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end; }}
.hour-bar {{
    width: 100%; max-width: 32px; background: var(--bg-light);
    border-radius: 4px 4px 0 0; min-height: 2px; transition: height 0.3s;
}}
.hour-bar.peak {{ background: var(--primary); box-shadow: 0 0 12px rgba(0,212,255,0.5); }}
.hour-label {{ font-size: 0.65rem; color: var(--text-muted); margin-top: 6px; }}

/* 30-day SVG */
.trend-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; overflow-x: auto;
}}
.legend {{ display: flex; gap: 24px; margin-bottom: 8px; font-size: 0.85rem; }}
.legend-pv {{ color: var(--primary); }}
.legend-uv {{ color: var(--purple); }}

/* Two-column grid */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}

/* Tables */
.table-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid rgba(45,45,61,0.5); font-size: 0.9rem; }}
.empty {{ color: var(--text-muted); font-style: italic; padding: 16px; text-align: center; }}
.small {{ font-size: 0.75rem; }}
td a {{ color: var(--primary); text-decoration: none; }}
td a:hover {{ text-decoration: underline; }}

/* Distribution bars */
.dist-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.dist-label {{ width: 100px; font-size: 0.85rem; flex-shrink: 0; }}
.dist-value {{ width: 45px; font-size: 0.85rem; color: var(--text-secondary); text-align: right; }}
.pct-bar-bg {{ flex:1; height: 8px; background: var(--bg-light); border-radius: 4px; overflow: hidden; }}
.pct-bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}

/* Anomaly footer */
.anomaly {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; margin-bottom: 32px;
}}
.anomaly-title {{ color: var(--warning); font-weight: 600; margin-bottom: 12px; }}
.anomaly-stats {{ display: flex; gap: 32px; flex-wrap: wrap; margin-bottom: 16px; }}
.anomaly-stat {{ font-size: 0.9rem; }}
.anomaly-stat strong {{ color: var(--warning); }}

/* Responsive */
@media (max-width: 768px) {{
    .cards {{ grid-template-columns: repeat(2,1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
    .hour-chart {{ height: 120px; }}
    .anomaly-stats {{ flex-direction: column; gap: 8px; }}
}}
@media (max-width: 480px) {{
    .cards {{ grid-template-columns: 1fr; }}
    .header {{ flex-direction: column; text-align: center; }}
    .header-meta {{ text-align: center; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
    <div><h1>\U0001f4ca MRRC Website Statistics</h1></div>
    <div class="header-meta">
        <span>Last update: {stats["last_update"]}</span>
        <span>Next update: {stats["next_update"]}</span>
    </div>
</div>

<!-- Overview Cards -->
<div class="cards">
    <div class="card"><div class="card-number">{stats["today_pv"]:,}</div><div class="card-label">Today PV</div></div>
    <div class="card"><div class="card-number">{stats["today_uv"]:,}</div><div class="card-label">Today UV</div></div>
    <div class="card"><div class="card-number">{stats["month_pv"]:,}</div><div class="card-label">Month PV</div></div>
    <div class="card"><div class="card-number">{stats["total_pv"]:,}</div><div class="card-label">Total PV (All-time)</div></div>
</div>

<!-- 24h Hourly Chart -->
<div class="section">
    <div class="section-title">\U0001f4c8 24-Hour Traffic (Today, CST)</div>
    <div class="hour-chart">{hour_bars}</div>
</div>

<!-- 30-Day Trend -->
<div class="section">
    <div class="section-title">\U0001f4c9 30-Day Trend</div>
    <div class="trend-box">
        <div class="legend"><span class="legend-pv">━ PV</span><span class="legend-uv">┅ UV</span></div>
        <svg viewBox="0 0 860 240" width="100%" height="240">
            <!-- Grid lines -->
            <line x1="40" y1="20" x2="820" y2="20" stroke="#2d2d3d" stroke-dasharray="4,4"/>
            <line x1="40" y1="200" x2="820" y2="200" stroke="#2d2d3d"/>
            <!-- Axes -->
            <line x1="40" y1="20" x2="40" y2="210" stroke="#2d2d3d"/>
            <line x1="35" y1="200" x2="820" y2="200" stroke="#2d2d3d"/>
            <!-- PV line -->
            <polyline fill="none" stroke="#00d4ff" stroke-width="2" points="{svg_points_pv.strip()}"/>
            <!-- UV line -->
            <polyline fill="none" stroke="#7c3aed" stroke-width="1.5" stroke-dasharray="6,4" points="{svg_points_uv.strip()}"/>
        </svg>
    </div>
</div>

<!-- Top Pages + Referrers -->
<div class="grid-2">
    <div class="table-box">
        <div class="section-title">\U0001f4c4 Top Pages</div>
        <table><thead><tr><th>Path</th><th>Hits</th><th>%</th></tr></thead><tbody>{pages_html}</tbody></table>
    </div>
    <div class="table-box">
        <div class="section-title">\U0001f517 Top Referrers</div>
        <table><thead><tr><th>Source</th><th>Count</th></tr></thead><tbody>{refs_html}</tbody></table>
    </div>
</div>

<!-- Countries + Browser/OS -->
<div class="grid-2">
    <div class="table-box">
        <div class="section-title">\U0001f30d Countries / Regions</div>
        <table><thead><tr><th>Country</th><th>Visitors</th></tr></thead><tbody>{countries_html}</tbody></table>
    </div>
    <div class="table-box">
        <div class="section-title">\U0001f5a5 Browsers</div>
        {browser_html}
        <div class="section-title" style="margin-top:16px;">\U0001f4f1 Operating Systems</div>
        {os_html}
    </div>
</div>

<!-- Anomaly Footer -->
<div class="anomaly">
    <div class="anomaly-title">⚠️ Anomaly Monitoring (Today)</div>
    <div class="anomaly-stats">
        <div class="anomaly-stat">404 Errors: <strong>{stats["today_404"]}</strong></div>
        <div class="anomaly-stat">Bot Traffic: <strong>{stats["bots_pct"]}%</strong></div>
        <div class="anomaly-stat">Total Requests: <strong>{stats["total_hits_today"]:,}</strong></div>
    </div>
    <table style="margin-top:12px;"><thead><tr><th>Suspicious IP</th><th>Requests</th><th>Paths Attempted</th></tr></thead><tbody>{suspicious_html}</tbody></table>
</div>

</div>
</body>
</html>"""


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
    import sys

    start_time = time.time()
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}] Starting stats analysis...")

    conn = init_db()

    # Step 1: Ingest new log data
    print("1. Ingesting logs...")
    new_count = ingest_logs(conn)
    print(f"   {new_count} new hits ingested")

    # Step 2: Clean up old data
    print("2. Cleaning up old hits...")
    cleanup_old_hits(conn)

    # Step 3: Update daily summary
    print("3. Updating daily summary...")
    update_daily_summary(conn)

    # Step 4: Query stats and render HTML
    print("4. Rendering dashboard...")
    stats = query_stats(conn)
    html = render_html(stats)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    # Step 5: Generate per-page analytics
    print("5. Generating per-page analytics...")
    generate_page_details(conn)

    conn.close()

    elapsed = time.time() - start_time
    print(f"Done in {elapsed:.1f}s. Dashboard written to {HTML_PATH}")
