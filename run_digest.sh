#!/bin/bash

# AI Digest Runner Script
# This script runs the AI digest application with proper environment setup

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables (properly handle comments, empty lines, and complex values)
if [ -f .env ]; then
    # Use a more robust method to load .env file
    while IFS= read -r line; do
        # Skip empty lines and comments
        if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*# ]]; then
            # Check if line contains =
            if [[ "$line" =~ = ]]; then
                # Export the line as-is (this preserves quotes and complex values)
                export "$line"
            fi
        fi
    done < .env
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set timezone to Paris
export TZ=Europe/Paris

# Run the digest application
echo "$(date): Starting AI digest application..." >> logs/cron.log
python3 main.py --run-once >> logs/cron.log 2>&1
echo "$(date): AI digest application completed with exit code $?" >> logs/cron.log 