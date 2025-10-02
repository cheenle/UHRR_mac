#!/bin/bash
# Script to push all local commits to remote repository
# Run this when network connectivity is restored

echo "Pushing all local commits to remote repository..."
echo "Current branch status:"
git status
echo ""
echo "Recent commits:"
git log --oneline -5
echo ""
echo "Attempting to push to origin main..."
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed all commits to remote repository!"
else
    echo "❌ Failed to push commits. Please check network connectivity and try again."
fi