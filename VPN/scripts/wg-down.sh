#!/usr/bin/env bash
set -euo pipefail

WG_NAME="wg0"

sudo wg-quick down "$WG_NAME" || true

echo "已停止 $WG_NAME"

