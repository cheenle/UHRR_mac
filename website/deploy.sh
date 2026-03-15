#!/bin/bash
# MRRC Website Deployment Script
# Deploy to www.vlsc.net Apache server

set -e

# Configuration
LOCAL_WEBSITE_DIR="/Users/cheenle/UHRR/MRRC/website"
REMOTE_HOST="www.vlsc.net"
REMOTE_USER="cheenle"  # Adjust if different
REMOTE_WEBROOT="/var/www/html/mrrc"  # Adjust path as needed
BACKUP_DIR="/var/www/backups/mrrc_$(date +%Y%m%d_%H%M%S)"

echo "=========================================="
echo "MRRC Website Deployment"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if local directory exists
if [ ! -d "$LOCAL_WEBSITE_DIR" ]; then
    echo -e "${RED}Error: Local website directory not found: $LOCAL_WEBSITE_DIR${NC}"
    exit 1
fi

echo "Local directory: $LOCAL_WEBSITE_DIR"
echo "Remote host: $REMOTE_HOST"
echo "Remote path: $REMOTE_WEBROOT"
echo ""

# Build website (if needed)
echo "Building website..."
cd "$LOCAL_WEBSITE_DIR"

# Verify all required files exist
echo "Checking required files..."
REQUIRED_FILES=(
    "index.html"
    "css/style.css"
    "js/main.js"
    "js/i18n.js"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: Required file missing: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} $file"
done

echo ""
echo "All files present."
echo ""

# Create deployment package
echo "Creating deployment package..."
DEPLOY_PACKAGE="/tmp/mrrc_website_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$DEPLOY_PACKAGE" -C "$LOCAL_WEBSITE_DIR" .
echo -e "${GREEN}✓${NC} Package created: $DEPLOY_PACKAGE"
echo ""

# Deploy to remote server
echo "Deploying to remote server..."
echo "This will:"
echo "  1. Create backup of current site"
echo "  2. Upload new files"
echo "  3. Set correct permissions"
echo ""

read -p "Continue with deployment? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    echo "Deployment cancelled."
    rm "$DEPLOY_PACKAGE"
    exit 0
fi

# SSH commands for deployment
ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
    set -e
    
    echo "Creating backup..."
    if [ -d "$REMOTE_WEBROOT" ]; then
        sudo mkdir -p /var/www/backups
        sudo cp -r "$REMOTE_WEBROOT" "$BACKUP_DIR"
        echo "Backup created: $BACKUP_DIR"
    fi
    
    echo "Creating webroot directory..."
    sudo mkdir -p "$REMOTE_WEBROOT"
    
    echo "Setting permissions..."
    sudo chown -R www-data:www-data "$REMOTE_WEBROOT"
    sudo chmod -R 755 "$REMOTE_WEBROOT"
EOF

# Upload files
echo "Uploading files..."
scp "$DEPLOY_PACKAGE" "$REMOTE_USER@$REMOTE_HOST:/tmp/"

# Extract on remote server
ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
    set -e
    
    echo "Extracting files..."
    cd "$REMOTE_WEBROOT"
    sudo tar -xzf "$DEPLOY_PACKAGE" --overwrite
    
    echo "Setting ownership..."
    sudo chown -R www-data:www-data "$REMOTE_WEBROOT"
    sudo chmod -R 755 "$REMOTE_WEBROOT"
    
    # Set correct permissions for sensitive files
    sudo chmod 644 "$REMOTE_WEBROOT"/*.html
    sudo chmod 644 "$REMOTE_WEBROOT"/*.css 2>/dev/null || true
    sudo chmod 644 "$REMOTE_WEBROOT"/*.js 2>/dev/null || true
    
    # Clean up
    rm -f "$DEPLOY_PACKAGE"
    
    echo "Testing Apache configuration..."
    sudo apache2ctl configtest || true
    
    echo "Reloading Apache..."
    sudo systemctl reload apache2 || sudo service apache2 reload || true
    
    echo ""
    echo "Deployment completed successfully!"
    echo "Website URL: https://$REMOTE_HOST/mrrc/"
    echo "Backup location: $BACKUP_DIR"
EOF

# Clean up local package
rm -f "$DEPLOY_PACKAGE"

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Website deployed to: https://$REMOTE_HOST/mrrc/"
echo ""
echo "To verify:"
echo "  1. Visit https://$REMOTE_HOST/mrrc/"
echo "  2. Check all pages load correctly"
echo "  3. Test language switching"
echo ""
echo "If you need to rollback:"
echo "  ssh $REMOTE_USER@$REMOTE_HOST"
echo "  sudo rm -rf $REMOTE_WEBROOT"
echo "  sudo cp -r $BACKUP_DIR $REMOTE_WEBROOT"
echo ""
