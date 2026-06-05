# MRRC Website Statistics Dashboard Design

**Date**: 2026-05-31
**Status**: Approved

## Overview

Python + SQLite pipeline that parses Apache access logs hourly, stores structured data, and generates a static HTML dashboard at `www.vlsc.net/mrrc/stats/` protected by Apache Basic Auth.

## Architecture

```
Cron (hourly)
  → analyze.py (sudo python3, reads Apache logs)
    → SQLite: incremental log parsing (meta.position)
    → SQLite: daily_summary upsert
    → Generate index.html from template + query results
    → Write /var/www/vlsc.net/mrrc/stats/index.html

Apache
  → /mrrc/stats/ → Basic Auth → serves static index.html
```

### Server file layout

```
/var/www/vlsc.net/mrrc/stats/
  .htaccess              # Basic Auth
  index.html             # Generated dashboard (overwritten hourly)
  stats.db               # SQLite database
  analyze.py             # Single script: parse + query + render
  GeoLite2-Country.mmdb  # MaxMind free GeoIP database
```

### Source file layout

```
website/stats/
  analyze.py             # Main script (deployed to server as-is)
  README.md              # Deployment notes
```

`analyze.py` is a single self-contained file to minimize deployment complexity. It contains:
- Log parsing (Apache combined vhost format, gzip detection via magic bytes 1f 8b, not file extension — rotated logs may be plaintext or gzip)
- SQLite schema creation and incremental tracking
- GeoIP lookup (MaxMind mmdb)
- UA parsing (browser, OS, bot detection via regex)
- Daily summary aggregation
- HTML rendering (CSS inline, SVG charts inline)

## Data Schema

### Table: meta

```sql
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

Keys: `log_file`, `position`, `inode` — tracks incremental parse state. When log rotation is detected (inode change), resets position to 0.

### Table: hits

```sql
CREATE TABLE hits (
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
CREATE INDEX idx_hits_ts ON hits(ts);
CREATE INDEX idx_hits_path ON hits(path);
```

Retention: DELETE rows older than 30 days on each run.

### Table: daily_summary

```sql
CREATE TABLE daily_summary (
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
```

`top_pages`, `top_refs`, `top_countries` store JSON arrays. Retained permanently for long-term trend charts.

## Dashboard Sections

### 1. Header bar
- Title: "MRRC Website Statistics"
- Last update timestamp, next update countdown (text-based, no JS)

### 2. Overview cards (4-across, 2-across on mobile)
- Today PV, Today UV, Month PV, Total All-time PV

### 3. 24h hourly chart
- CSS bar chart: one `<div>` per hour, height proportional to PV
- Max bar highlighted in primary cyan

### 4. 30-day trend chart
- Inline SVG with `<polyline>` for PV (solid) and UV (dashed)
- X-axis: dates, Y-axis: count

### 5. Two-column grid
- Left: Top 10 pages (path + PV + % bar)
- Right: Top 10 referrers (source + count)

### 6. Two-column grid
- Left: Top 10 countries (emoji flag + name + count)
- Right: Browser/OS distribution (% bars)

### 7. Anomaly footer
- Today 404 count, bot traffic %, suspicious IPs (cgi-bin probes, .env scans, etc.)

## Visual Design

- Dark theme matching MRRC website: `--bg-dark: #0a0a0f`, `--primary-color: #00d4ff`, `--bg-card: #13131f`
- Fonts: Inter (headings), JetBrains Mono (numbers/monospace), system sans-serif fallback
- All CSS inlined in `<style>` — zero external dependencies
- No JavaScript — all charts are CSS bars or inline SVG
- Responsive breakpoints: 768px (tablet), 480px (mobile)
- Print stylesheet: hide header, show data-only layout

Time display in China Standard Time (UTC+8, server local).

## Authentication

Apache Basic Auth via `.htaccess`:

```
AuthType Basic
AuthName "MRRC Statistics"
AuthUserFile /var/www/vlsc.net/mrrc/stats/.htpasswd
Require valid-user
```

Password file created with `htpasswd -c`. Deployed once, not regenerated.

## GeoIP

Uses free MaxMind GeoLite2 Country database (`.mmdb` format). Downloaded once, placed at `/var/www/vlsc.net/mrrc/stats/GeoLite2-Country.mmdb`. Requires `pip3 install maxminddb` (pure Python, no C deps) on the server. IP lookup: identifies country for each hit. Unknown IPs map to "Unknown".

## Cron Setup

```
0 * * * * cd /var/www/vlsc.net/mrrc/stats && python3 analyze.py >> /var/log/mrrc-stats.log 2>&1
```

The Python script runs as the normal user (`cheenle`). To read Apache logs (owned by `root:adm`, mode `640`), the script internally uses `subprocess.run(['sudo', 'cat', logfile_path])` — only `cat` is elevated, not the entire Python runtime. Requires one sudoers entry:

```
cheenle ALL=(root) NOPASSWD: /usr/bin/cat /var/log/apache2/*
```

## UA Parsing & Bot Detection

Regex-based, no external library needed:

**Browsers**: Chrome, Safari, Firefox, Edge, Opera, Samsung Internet, QQ Browser  
**OS**: Windows, macOS, Linux, Android, iOS, iPadOS, ChromeOS  
**Bots**: googlebot, bingbot, baiduspider, yandexbot, slurp, duckduckbot, ahrefsbot, semrushbot, petalbot, Bytespider, facebookexternalhit, twitterbot, libredtail-http, nuclei, nikto, nmap, zgrab, masscan, go-http-client, python-requests, curl, wget

Detection scans UA string case-insensitively for known bot tokens. Also heuristically flags paths containing `cgi-bin`, `.env`, `wp-admin`, `admin.php`, `config.php` as scanner traffic regardless of UA.

## Status Code Classification

- 2xx: 200-299 (success)
- 3xx: 300-399 (redirects, including 301/302)
- 4xx: 400-499 (client errors, 404 tracked separately)
- 5xx: 500-599 (server errors)

## Dependencies (server)

- Python 3.12 (already installed)
- `pip3 install maxminddb` (pure Python, reads .mmdb files)
- No other pip packages required

## Security Notes

- Dashboard is password-protected, never indexed (add `<meta name="robots" content="noindex">`)
- IP addresses stored in SQLite — acceptable for private stats, but `.htaccess` blocks public access
- Script runs as normal user — only `sudo cat` subprocess for reading Apache logs, not full script elevation

## Out of Scope

- Real-time streaming analytics
- Interactive filtering / date range picker
- Database for raw hits beyond 30 days (daily summaries are permanent)
- Email alerts or notifications
- TLS/SSL per-page stats (aggregate only)
