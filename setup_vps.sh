#!/bin/bash

# AI Digest VPS Setup Script
# This script sets up the AI digest application on an Ubuntu VPS

set -e  # Exit on any error

echo "Setting up AI Digest on Ubuntu VPS..."

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Install timezone data and set timezone to Paris
echo "Setting timezone to Paris..."
sudo apt install -y tzdata
sudo timedatectl set-timezone Europe/Paris

# Navigate to project directory (assuming script is run from project root)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p logs outputs data

# Make run script executable
echo "Making run script executable..."
chmod +x run_digest.sh

# Copy systemd files to the correct location
echo "Setting up systemd service and timer..."
sudo cp ai-digest.service /etc/systemd/system/
sudo cp ai-digest.timer /etc/systemd/system/

# Update the service file with the correct project path
sudo sed -i "s|/home/ubuntu/c4|$PROJECT_DIR|g" /etc/systemd/system/ai-digest.service

# Reload systemd and enable the timer
echo "Enabling systemd timer..."
sudo systemctl daemon-reload
sudo systemctl enable ai-digest.timer
sudo systemctl start ai-digest.timer

# Show timer status
echo "Checking timer status..."
sudo systemctl status ai-digest.timer --no-pager

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "The AI digest is now scheduled to run daily at 6:00 AM Paris time."
echo ""
echo "Useful commands:"
echo "  - Check timer status:     sudo systemctl status ai-digest.timer"
echo "  - Check service logs:     sudo journalctl -u ai-digest.service -f"
echo "  - Run digest manually:    ./run_digest.sh"
echo "  - Stop timer:             sudo systemctl stop ai-digest.timer"
echo "  - Disable timer:          sudo systemctl disable ai-digest.timer"
echo ""
echo "Next scheduled run:"
sudo systemctl list-timers ai-digest.timer --no-pager
echo ""
echo "Make sure your .env file contains all necessary API keys and configuration!"
echo "You can test the setup by running: ./run_digest.sh" 