#!/bin/bash
# Apply fix for mobile interface wsRX connection status issue

echo "Applying mobile interface WebSocket connection fix..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_JS="$SCRIPT_DIR/www/mobile.js"

# Backup original file
cp "$MOBILE_JS" "$MOBILE_JS.backup"

# Apply the fix by adding forced status updates
echo "Adding forced status updates to mobile.js..."

# Add forced status check after WebSocket connections
sed -i '' '/wsControlTRX.onopen = function() {/a\
        // Force immediate status update\
        setTimeout(() => {\
            if (document.getElementById("status-ctrl")) {\
                document.getElementById("status-ctrl").classList.add("connected");\
            }\
        }, 100);
' "$MOBILE_JS"

sed -i '' '/wsAudioRX.onopen = function() {/a\
        // Force immediate status update\
        setTimeout(() => {\
            if (document.getElementById("status-rx")) {\
                document.getElementById("status-rx").classList.add("connected");\
            }\
        }, 100);
' "$MOBILE_JS"

sed -i '' '/wsAudioTX.onopen = function() {/a\
        // Force immediate status update\
        setTimeout(() => {\
            if (document.getElementById("status-tx")) {\
                document.getElementById("status-tx").classList.add("connected");\
            }\
        }, 100);
' "$MOBILE_JS"

echo "Fix applied successfully!"
echo "Please refresh your mobile interface to see the changes."
