#!/bin/bash
# Parallel Checkers Bot Launcher
# Runs multiple accounts simultaneously

# Activate venv
source /home/user/Gameon-AI-Bots/venv/bin/activate

# Set environment
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export DISPLAY=:99

# Start virtual display if needed
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "Starting Xvfb virtual display..."
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    sleep 2
fi

# Change to bot directory
cd /home/user/Gameon-AI-Bots

# Check if config exists
if [ ! -f "accounts.json" ]; then
    echo "ERROR: checkers_accounts.json not found!"
    echo "Please create checkers_accounts.json with your accounts configuration"
    exit 1
fi

# Run the parallel bot
echo "=================================================="
echo "Starting Parallel Checkers Bot - ULTRA EXPERT AI"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

python multiple-checkers.py

# Capture exit code
EXIT_CODE=$?

# Clean old logs (keep last 30 days)
find /home/user/Gameon-AI-Bots/logs -name "checkers_*.log" -mtime +30 -delete 2>/dev/null

# Deactivate venv
deactivate

echo "=================================================="
echo "Bot execution completed"
echo "Exit code: $EXIT_CODE"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

exit $EXIT_CODE
