#!/bin/bash
# Apply fix for mobile interface wsRX connection status issue

echo "Applying mobile interface WebSocket connection fix..."

# Backup original file
cp /Users/cheenle/UHRR/UHRR_mac/www/mobile.js /Users/cheenle/UHRR/UHRR_mac/www/mobile.js.backup

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
' /Users/cheenle/UHRR/UHRR_mac/www/mobile.js

sed -i '' '/wsAudioRX.onopen = function() {/a\
        // Force immediate status update\
        setTimeout(() => {\
            if (document.getElementById("status-rx")) {\
                document.getElementById("status-rx").classList.add("connected");\
            }\
        }, 100);
' /Users/cheenle/UHRR/UHRR_mac/www/mobile.js

sed -i '' '/wsAudioTX.onopen = function() {/a\
        // Force immediate status update\
        setTimeout(() => {\
            if (document.getElementById("status-tx")) {\
                document.getElementById("status-tx").classList.add("connected");\
            }\
        }, 100);
' /Users/cheenle/UHRR/UHRR_mac/www/mobile.js

echo "Fix applied successfully!"
echo "Please refresh your mobile interface to see the changes."