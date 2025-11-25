#!/bin/bash
# Parallel Connect 4 Bot Launcher
# Runs multiple accounts simultaneously with ULTRA-GODMODE AI

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_msg() {
    echo -e "${2}${1}${NC}"
}

# Configuration
BOT_DIR="${BOT_DIR:-/home/ubuntu/bots/connect4-oppenent}"
VENV_PATH="${VENV_PATH:-/home/ubuntu/venvs/bots}"
CONFIG_FILE="${CONFIG_FILE:-accounts.json}"
LOG_DIR="${BOT_DIR}/logs"

# Create directories if they don't exist
mkdir -p "${BOT_DIR}"
mkdir -p "${LOG_DIR}"

print_msg "╔═══════════════════════════════════════════════════════════════╗" "${BLUE}"
print_msg "║        Connect 4 Parallel Bot - ULTRA-GODMODE AI             ║" "${BLUE}"
print_msg "║        Starting at $(date '+%Y-%m-%d %H:%M:%S')                         ║" "${BLUE}"
print_msg "╚═══════════════════════════════════════════════════════════════╝" "${BLUE}"

# Activate virtual environment
if [ -f "${VENV_PATH}/bin/activate" ]; then
    print_msg "✓ Activating virtual environment..." "${GREEN}"
    source "${VENV_PATH}/bin/activate"
else
    print_msg "✗ Virtual environment not found at ${VENV_PATH}" "${RED}"
    print_msg "Creating virtual environment..." "${YELLOW}"
    python3 -m venv "${VENV_PATH}"
    source "${VENV_PATH}/bin/activate"
    
    print_msg "Installing required packages..." "${YELLOW}"
    pip install --upgrade pip
    pip install selenium
fi

# Set environment variables
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export DISPLAY="${DISPLAY:-:99}"
export LOG_DIR="${LOG_DIR}"

# Check for Xvfb (virtual display) if running headless
if [ "${HEADLESS:-true}" = "true" ]; then
    if ! pgrep -x "Xvfb" > /dev/null; then
        print_msg "Starting Xvfb virtual display..." "${YELLOW}"
        Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
        sleep 2
        print_msg "✓ Virtual display started" "${GREEN}"
    else
        print_msg "✓ Virtual display already running" "${GREEN}"
    fi
fi

# Change to bot directory
cd "${BOT_DIR}"

# Check if bot.py exists
if [ ! -f "connect4-bot.py" ]; then
    print_msg "✗ bot.py not found in ${BOT_DIR}" "${RED}"
    exit 1
fi

# Check if config exists
if [ ! -f "${CONFIG_FILE}" ]; then
    print_msg "✗ ${CONFIG_FILE} not found!" "${RED}"
    print_msg "Creating example configuration..." "${YELLOW}"
    
    cat > "${CONFIG_FILE}" << 'EOF'
{
  "accounts": [
    {
      "email": "account1@example.com",
      "password": "password1",
      "games_per_run": 3,
      "bet_increase_clicks": 0,
      "enabled": true
    },
    {
      "email": "account2@example.com",
      "password": "password2",
      "games_per_run": 5,
      "bet_increase_clicks": 0,
      "enabled": true
    }
  ],
  "settings": {
    "headless": true,
    "challenge_wait_timeout": 300,
    "wait_between_games": 10,
    "max_parallel_accounts": 5,
    "stagger_start_delay": 2
  }
}
EOF
    
    print_msg "✓ Created ${CONFIG_FILE} - Please edit with your account details" "${GREEN}"
    print_msg "Run this script again after updating the config file" "${YELLOW}"
    exit 0
fi

# Validate Python and Selenium
print_msg "Checking dependencies..." "${YELLOW}"

if ! python -c "import selenium" 2>/dev/null; then
    print_msg "Installing Selenium..." "${YELLOW}"
    pip install selenium
fi

print_msg "✓ All dependencies installed" "${GREEN}"

# Display configuration summary
print_msg "\n═══ Configuration ═══" "${BLUE}"
ACCOUNT_COUNT=$(python -c "import json; print(len([a for a in json.load(open('${CONFIG_FILE}'))['accounts'] if a.get('enabled', True)]))" 2>/dev/null || echo "0")
print_msg "Enabled accounts: ${ACCOUNT_COUNT}" "${BLUE}"
print_msg "Log directory: ${LOG_DIR}" "${BLUE}"
print_msg "Config file: ${CONFIG_FILE}" "${BLUE}"
print_msg "" "${NC}"

# Run the bot
print_msg "╔═══════════════════════════════════════════════════════════════╗" "${GREEN}"
print_msg "║                    STARTING BOT EXECUTION                     ║" "${GREEN}"
print_msg "╚═══════════════════════════════════════════════════════════════╝" "${GREEN}"

# Execute with error handling
if python connect4-bot.py; then
    EXIT_CODE=0
    print_msg "\n✓ Bot execution completed successfully" "${GREEN}"
else
    EXIT_CODE=$?
    print_msg "\n✗ Bot execution failed with exit code ${EXIT_CODE}" "${RED}"
fi

# Clean old logs (keep last 30 days)
print_msg "\nCleaning old logs (keeping last 30 days)..." "${YELLOW}"
find "${LOG_DIR}" -name "*.log" -mtime +30 -delete 2>/dev/null || true
find "${LOG_DIR}" -name "*.png" -mtime +30 -delete 2>/dev/null || true

LOG_COUNT=$(find "${LOG_DIR}" -name "*.log" | wc -l)
print_msg "✓ Current log files: ${LOG_COUNT}" "${GREEN}"

# Deactivate virtual environment
deactivate

# Summary
print_msg "\n╔═══════════════════════════════════════════════════════════════╗" "${BLUE}"
print_msg "║                    EXECUTION COMPLETED                        ║" "${BLUE}"
print_msg "╠═══════════════════════════════════════════════════════════════╣" "${BLUE}"
print_msg "║ Exit code: ${EXIT_CODE}                                                   ║" "${BLUE}"
print_msg "║ Completed at: $(date '+%Y-%m-%d %H:%M:%S')                       ║" "${BLUE}"
print_msg "║ Logs saved to: ${LOG_DIR}                    ║" "${BLUE}"
print_msg "╚═══════════════════════════════════════════════════════════════╝" "${BLUE}"

exit ${EXIT_CODE}
