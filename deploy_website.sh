#!/bin/bash
# Simple deployment script for MRRC website
# Usage: ./deploy_website.sh [user@host] [remote_path]

set -e

REMOTE_HOST="${1:-vlsc@www.vlsc.net}"
REMOTE_PATH="${2:-/var/www/html/mrrc}"
LOCAL_DIR="/Users/cheenle/UHRR/MRRC/website"

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
ssh "$REMOTE_HOST" "sudo mkdir -p $REMOTE_PATH && sudo chown \$(whoami) $REMOTE_PATH"

# Sync files using rsync
rsync -avz --delete \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    --exclude='README.md' \
    --exclude='deploy.sh' \
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
echo "  curl -I https://www.vlsc.net/mrrc/"
echo ""