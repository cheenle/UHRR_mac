#!/bin/bash
# Simple deployment script for MRRC website
# Usage: ./deploy_website.sh [user@host] [remote_path]

set -e

REMOTE_HOST="${1:-cheenle@www.vlsc.net}"
REMOTE_PATH="${2:-/var/www/vlsc.net/mrrc}"
LOCAL_DIR="/Users/cheenle/UHRR/MRRC/website"

# The production tree is owned by www-data. Use sudo on the remote rsync side so
# deployments are repeatable without temporarily changing ownership to the SSH user.
RSYNC_REMOTE_PATH="sudo rsync"

# Keep server/runtime artifacts out of static website deploys. Excluded paths are
# also protected from --delete unless --delete-excluded is used, which we do not use.
RSYNC_EXCLUDES=(
    '.DS_Store'
    '*.log'
    'README.md'
    'deploy.sh'
    '.claude/'
    '.iflow_logs/'
    'logs/'
    'stats/'
    'vlsc.net.conf'
)

echo "=========================================="
echo "MRRC Website Quick Deploy"
echo "=========================================="
echo ""
echo "Local:  $LOCAL_DIR"
echo "Remote: $REMOTE_HOST:$REMOTE_PATH"
echo ""

# Check local directory exists
if [ ! -d "$LOCAL_DIR" ]; then
    echo "Error: Local directory not found: $LOCAL_DIR"
    exit 1
fi

# Check required files
echo "Checking website files..."
for file in index.html css/style.css js/main.js; do
    if [ ! -f "$LOCAL_DIR/$file" ]; then
        echo "Error: Missing file: $file"
        exit 1
    fi
    echo "  ✓ $file"
done
echo ""

# Create remote directory and deploy
echo "Deploying to remote server..."
echo ""

# Create remote directory
ssh "$REMOTE_HOST" "sudo mkdir -p '$REMOTE_PATH'"

# Sync files using rsync
RSYNC_ARGS=(-avz --delete --no-owner --no-group --rsync-path="$RSYNC_REMOTE_PATH")
for pattern in "${RSYNC_EXCLUDES[@]}"; do
    RSYNC_ARGS+=(--exclude="$pattern")
done

rsync "${RSYNC_ARGS[@]}" \
    "$LOCAL_DIR/" \
    "$REMOTE_HOST:$REMOTE_PATH/"

# Fix permissions
ssh "$REMOTE_HOST" "sudo chown -R www-data:www-data $REMOTE_PATH && sudo chmod -R 755 $REMOTE_PATH"

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Website URL: https://www.vlsc.net/mrrc/"
echo ""
echo "Test the deployment:"
echo "  curl -k -I https://www.vlsc.net/mrrc/"
echo ""
