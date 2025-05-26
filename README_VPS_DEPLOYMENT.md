# AI Digest VPS Deployment Guide

This guide explains how to deploy the AI Digest application on an Ubuntu VPS to run automatically at 6 AM Paris time with minimal resource usage.

## Overview

The deployment uses:
- **systemd timer**: For scheduling (more reliable than cron for this use case)
- **systemd service**: For running the application as a one-shot service
- **Virtual environment**: For Python dependency isolation
- **Minimal resource usage**: The application only runs when scheduled, using no resources otherwise

## Quick Setup

1. **Upload your project to the VPS** (via git, scp, or rsync)
2. **Ensure your `.env` file is present** with all necessary API keys and configuration
3. **Run the setup script**:
   ```bash
   chmod +x setup_vps.sh
   ./setup_vps.sh
   ```

That's it! The application will now run daily at 6 AM Paris time.

## What's New

### ✅ **Fixed OpenAI RSS Feed**
The OpenAI RSS feed (`https://openai.com/blog/rss.xml`) has been **fixed and is now working properly**. It was previously in the skip list but is now active and includes recent content like:
- [OpenAI o3 and o4-mini System Card](https://openai.com/index/o3-o4-mini-system-card)
- [Introducing Codex](https://openai.com/index/introducing-codex)
- [New tools and features in the Responses API](https://openai.com/index/new-tools-and-features-in-the-responses-api)

### 📡 **Comprehensive RSS Feeds Added**
The application now includes **25+ high-quality AI/tech RSS feeds**:

**AI Research Labs:**
- OpenAI Blog
- Google Research
- DeepMind Blog
- Anthropic News
- Hugging Face Blog

**Tech News & AI Coverage:**
- TechCrunch AI
- VentureBeat AI
- The Verge AI
- MIT Technology Review
- Wired AI
- Ars Technica AI

**Academic & Research:**
- Distill.pub
- arXiv AI/ML/CL feeds

**Industry & Business:**
- LangChain Blog
- Weights & Biases
- KDnuggets
- Machine Learning Mastery

**YouTube Channels:**
- DeepMind
- Google AI
- AI/ML educational channels

### 🔧 **Enhanced Configuration**
- **Hybrid configuration system**: YAML config for feeds/settings, `.env` for secrets
- **Smart feed limits**: Different limits for high-volume vs. low-volume feeds
- **Improved keyword filtering**: Extended keyword list for better content matching
- **Automatic skip handling**: Problematic feeds are automatically skipped

## Manual Setup (if you prefer step-by-step)

### 1. System Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git curl tzdata

# Set timezone to Paris
sudo timedatectl set-timezone Europe/Paris
```

### 2. Project Setup

```bash
# Navigate to your project directory
cd /path/to/your/project

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (now includes PyYAML)
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs outputs data

# Make run script executable
chmod +x run_digest.sh
```

### 3. Configure Systemd Service

```bash
# Copy service files
sudo cp ai-digest.service /etc/systemd/system/
sudo cp ai-digest.timer /etc/systemd/system/

# Update the service file with your project path
sudo sed -i "s|/home/ubuntu/c4|$(pwd)|g" /etc/systemd/system/ai-digest.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable ai-digest.timer
sudo systemctl start ai-digest.timer
```

### 4. Verify Setup

```bash
# Check timer status
sudo systemctl status ai-digest.timer

# List next scheduled runs
sudo systemctl list-timers ai-digest.timer

# Test manual run
./run_digest.sh
```

## Configuration Files

### `.env` File Requirements

Your `.env` file needs **only the essential sensitive data**. See `env_example.txt` for a template:

```env
# Essential Configuration
GEMINI_API_KEY=your_gemini_api_key_here
RECIPIENT_EMAIL=your_email@example.com
SENDER_EMAIL=your_sender_email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_sender_email@example.com
SMTP_PASSWORD=your_app_password_here
```

### config.yaml Features

The `config.yaml` now handles most configuration:
- **25+ RSS feeds** automatically configured
- **Smart feed limits** (20 for OpenAI, 15 for TechCrunch, etc.)
- **Enhanced keyword filtering** with ML/AI terms
- **Automatic problematic feed skipping**
- **Model configuration** with pricing estimates

## Managing the Service

### Useful Commands

```bash
# Check timer status
sudo systemctl status ai-digest.timer

# Check service logs (real-time)
sudo journalctl -u ai-digest.service -f

# Check recent service logs
sudo journalctl -u ai-digest.service -n 50

# Run manually for testing
./run_digest.sh

# Stop the timer
sudo systemctl stop ai-digest.timer

# Disable the timer (prevents auto-start on boot)
sudo systemctl disable ai-digest.timer

# Re-enable the timer
sudo systemctl enable ai-digest.timer
sudo systemctl start ai-digest.timer
```

### Viewing Logs

The application logs to multiple places:

1. **Application logs**: `logs/` directory in your project
2. **Cron logs**: `logs/cron.log` (from the run script)
3. **System logs**: `sudo journalctl -u ai-digest.service`

## Resource Usage

This setup is designed for minimal resource usage:

- **When not running**: 0% CPU, minimal memory (just systemd timer)
- **When running**: Temporary CPU/memory usage during execution (~5-10 minutes)
- **Storage**: Logs and outputs are stored in project directories

## Troubleshooting

### Timer Not Running

```bash
# Check if timer is active
sudo systemctl is-active ai-digest.timer

# Check timer configuration
sudo systemctl cat ai-digest.timer

# Check for errors
sudo journalctl -u ai-digest.timer
```

### Service Errors

```bash
# Check service status
sudo systemctl status ai-digest.service

# View detailed logs
sudo journalctl -u ai-digest.service -n 100

# Test manual execution
cd /path/to/project && ./run_digest.sh
```

### Environment Issues

```bash
# Verify .env file exists and has correct permissions
ls -la .env

# Test virtual environment and new dependencies
source venv/bin/activate && python3 -c "import feedparser, google.generativeai, yaml; print('Dependencies OK')"

# Verify timezone
timedatectl
```

### RSS Feed Issues

```bash
# Test feed connectivity
source venv/bin/activate
python3 -c "
import feedparser
feed = feedparser.parse('https://openai.com/blog/rss.xml')
print(f'OpenAI feed status: {feed.status}')
print(f'Items found: {len(feed.entries)}')
if feed.entries:
    print(f'Latest: {feed.entries[0].title}')
"
```

### API Issues

```bash
# Test Gemini API connectivity
source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
print('API configured successfully')
"
```

## Security Considerations

1. **File Permissions**: Ensure `.env` file has restrictive permissions:
   ```bash
   chmod 600 .env
   ```

2. **User Permissions**: The service runs as the `ubuntu` user (configurable in `ai-digest.service`)

3. **API Keys**: Keep your `.env` file secure and never commit it to version control

## Updating the Application

To update the application:

```bash
# Stop the timer
sudo systemctl stop ai-digest.timer

# Update your code (git pull, copy new files, etc.)
git pull

# Update dependencies if needed (PyYAML now included)
source venv/bin/activate
pip install -r requirements.txt

# Restart the timer
sudo systemctl start ai-digest.timer
```

## Feed Quality & Performance

### Current Feed Status
- ✅ **OpenAI Blog**: Fixed and working with recent content
- ✅ **Google Research**: High-quality research posts
- ✅ **Hugging Face**: Regular model and tutorial updates
- ✅ **TechCrunch AI**: Breaking AI industry news
- ✅ **arXiv feeds**: Latest academic papers
- ⚠️ **Auto-skipped**: Facebook Research, SyncedReview (technical issues)

### Performance Optimizations
- **Smart limits**: High-volume feeds limited to prevent spam
- **Keyword filtering**: 25+ AI/ML keywords for relevance
- **Date filtering**: Only content from last 48 hours
- **Duplicate prevention**: URL-based deduplication across runs

## Monitoring

### Set up Log Rotation (Optional)

```bash
# Create logrotate configuration
sudo tee /etc/logrotate.d/ai-digest << EOF
/path/to/your/project/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
```

### Monitor Feed Quality

```bash
# Check what feeds are working
grep "Successfully fetched" logs/ai_digest_agent_*.log | tail -20

# Check what's being filtered out
grep "Skipped.*items" logs/ai_digest_agent_*.log | tail -10

# Check digest content quality
cat outputs/last_digest.html | grep -E "<h[2-3]>" | head -10
```

The setup is now complete with **comprehensive RSS feed coverage** and the **OpenAI feed working properly**! Your AI digest will run automatically every day at 6 AM Paris time with minimal resource usage when not active. 🚀 