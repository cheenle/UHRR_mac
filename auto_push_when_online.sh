#!/bin/bash
# Auto-push script that keeps trying until network is available

echo "🔄 Auto-push script started. Will keep trying until network is available..."
echo "Press Ctrl+C to stop."

while true; do
    echo "📡 Attempting to push to remote repository..."
    
    # Try to fetch first to test connectivity
    if git fetch origin; then
        echo "✅ Network connectivity established!"
        
        # Try to push
        if git push origin main; then
            echo "🎉 SUCCESS: All commits pushed to remote repository!"
            echo "Current status:"
            git status
            break
        else
            echo "❌ Push failed. Retrying in 30 seconds..."
        fi
    else
        echo "📡 Network unavailable. Retrying in 30 seconds..."
    fi
    
    sleep 30
done