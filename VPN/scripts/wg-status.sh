#!/usr/bin/env bash
set -euo pipefail

echo "=== wg ==="
sudo wg show || true

echo "=== routes (top20) ==="
netstat -rn | head -n 20 || true

