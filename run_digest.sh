#!/bin/bash

# AI Digest Runner Script
# This script runs the AI digest application with proper environment setup

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
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