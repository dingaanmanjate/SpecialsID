#!/bin/bash
# Script to run the Antigravity Streamlit Dashboard with AWS Vault

PROFILE="capaciti"

# Allow overriding the profile via argument
if [ -n "$1" ]; then
    PROFILE="$1"
fi

echo "🔐 Using AWS Vault profile: $PROFILE"
echo "🚀 Starting Antigravity Dashboard..."

aws-vault exec "$PROFILE" -- streamlit run dashboard/app.py
