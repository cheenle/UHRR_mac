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
