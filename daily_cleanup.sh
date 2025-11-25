#!/bin/bash
# Daily Cleanup Script for GameOn Bots
# Cleans lock files, temp files, and orphaned processes
# Run via cron: 0 2 * * * /home/ubuntu/bots/daily_cleanup.sh

set -e

LOG_DIR="/home/ubuntu/bots/logs"
LOG_FILE="$LOG_DIR/cleanup.log"

# Colors for logging
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
log "${BLUE}         Daily Cleanup - GameOn Bot Maintenance${NC}"
log "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# ============================================================================
# 1. CLEAN STALE LOCK FILES (ONLY IF BOT NOT RUNNING)
# ============================================================================

log "${BLUE}➤ Checking for stale lock files...${NC}"

LOCK_FILES_CLEANED=0

# CRITICAL: Check if bot wrapper is actively running
BOT_WRAPPER_RUNNING=0
if pgrep -f "smart_cron_wrapper.sh" > /dev/null; then
    BOT_WRAPPER_RUNNING=1
    log "${YELLOW}⚠ Bot wrapper is running - SKIPPING lock cleanup${NC}"
fi

# CRITICAL: Check if Python bot scripts are running
BOT_SCRIPTS_RUNNING=0
if pgrep -f "multiple-connect4.py\|multiple-checkers.py" > /dev/null; then
    BOT_SCRIPTS_RUNNING=1
    log "${YELLOW}⚠ Bot scripts are running - SKIPPING lock cleanup${NC}"
fi

# Only clean if NOTHING is running
if [ $BOT_WRAPPER_RUNNING -eq 0 ] && [ $BOT_SCRIPTS_RUNNING -eq 0 ]; then
    
    # Check if lock file exists and is old
    if [ -f /tmp/gameon_bot.lock ]; then
        LOCK_AGE=$(( $(date +%s) - $(stat -c %Y /tmp/gameon_bot.lock 2>/dev/null || echo 0) ))
        LOCK_AGE_HOURS=$(( LOCK_AGE / 3600 ))
        
        if [ $LOCK_AGE -gt 14400 ]; then  # 4 hours = 14400 seconds
            log "${YELLOW}  Found stale lock file (${LOCK_AGE_HOURS}h old) - removing${NC}"
            rm -f /tmp/gameon_bot.lock
            LOCK_FILES_CLEANED=$((LOCK_FILES_CLEANED + 1))
        else
            log "${GREEN}  Lock file is recent (${LOCK_AGE_HOURS}h) - keeping${NC}"
        fi
    fi

    # Check PID file
    if [ -f /tmp/gameon_bot.pid ]; then
        PID_AGE=$(( $(date +%s) - $(stat -c %Y /tmp/gameon_bot.pid 2>/dev/null || echo 0) ))
        PID_AGE_HOURS=$(( PID_AGE / 3600 ))
        
        if [ $PID_AGE -gt 14400 ]; then
            OLD_PID=$(cat /tmp/gameon_bot.pid 2>/dev/null || echo "")
            
            # Check if process is still running
            if [ -n "$OLD_PID" ]; then
                if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
                    log "${YELLOW}  Found stale PID file (process $OLD_PID not running) - removing${NC}"
                    rm -f /tmp/gameon_bot.pid
                    LOCK_FILES_CLEANED=$((LOCK_FILES_CLEANED + 1))
                else
                    log "${GREEN}  PID $OLD_PID still running - keeping${NC}"
                fi
            else
                log "${YELLOW}  Empty PID file - removing${NC}"
                rm -f /tmp/gameon_bot.pid
                LOCK_FILES_CLEANED=$((LOCK_FILES_CLEANED + 1))
            fi
        fi
    fi

    # Clean success flags ONLY if no bot processes
    FLAG_COUNT=0
    for flag in /tmp/connect4_success.flag /tmp/checkers_success.flag; do
        if [ -f "$flag" ]; then
            rm -f "$flag"
            FLAG_COUNT=$((FLAG_COUNT + 1))
        fi
    done

    if [ $FLAG_COUNT -gt 0 ]; then
        log "${GREEN}  Removed $FLAG_COUNT success flag files${NC}"
    fi

    log "${GREEN}✓ Lock files cleaned: $LOCK_FILES_CLEANED${NC}"
else
    log "${BLUE}ℹ SKIPPED lock cleanup - bot processes active${NC}"
fi

# ============================================================================
# 2. CLEAN CHROME TEMP PROFILES
# ============================================================================

log "${BLUE}➤ Cleaning Chrome temp profiles...${NC}"

PROFILE_COUNT=$(find /tmp -maxdepth 1 -name "chrome_profile_*" -type d 2>/dev/null | wc -l)

if [ $PROFILE_COUNT -gt 0 ]; then
    log "${YELLOW}  Found $PROFILE_COUNT Chrome profiles${NC}"
    rm -rf /tmp/chrome_profile_* 2>/dev/null || true
    log "${GREEN}✓ Removed $PROFILE_COUNT Chrome profiles${NC}"
else
    log "${GREEN}✓ No Chrome profiles to clean${NC}"
fi

# ============================================================================
# 3. CLEAN OLD SCREENSHOTS
# ============================================================================

log "${BLUE}➤ Cleaning old screenshots (>7 days)...${NC}"

SCREENSHOT_COUNT=$(find "$LOG_DIR" -name "login_error_*.png" -mtime +7 2>/dev/null | wc -l)

if [ $SCREENSHOT_COUNT -gt 0 ]; then
    find "$LOG_DIR" -name "login_error_*.png" -mtime +7 -delete 2>/dev/null
    log "${GREEN}✓ Deleted $SCREENSHOT_COUNT old screenshots${NC}"
else
    log "${GREEN}✓ No old screenshots to clean${NC}"
fi

# ============================================================================
# 4. KILL ZOMBIE CHROME PROCESSES
# ============================================================================

log "${BLUE}➤ Checking for orphaned Chrome processes...${NC}"

# Check if bot scripts are running
BOT_RUNNING=0
if pgrep -f "multiple-connect4.py\|multiple-checkers.py" > /dev/null; then
    BOT_RUNNING=1
    log "${GREEN}  Bot processes active - skipping Chrome cleanup${NC}"
fi

if [ $BOT_RUNNING -eq 0 ]; then
    CHROME_COUNT=$(pgrep chrome 2>/dev/null | wc -l)
    
    if [ $CHROME_COUNT -gt 0 ]; then
        log "${YELLOW}  Found $CHROME_COUNT orphaned Chrome processes${NC}"
        pkill -9 chrome 2>/dev/null || true
        sleep 1
        log "${GREEN}✓ Killed orphaned Chrome processes${NC}"
    else
        log "${GREEN}✓ No orphaned Chrome processes${NC}"
    fi
else
    log "${BLUE}  Skipped Chrome cleanup (bots running)${NC}"
fi

# ============================================================================
# 5. CLEAN OLD LOG FILES (>30 days)
# ============================================================================

log "${BLUE}➤ Cleaning old log files (>30 days)...${NC}"

OLD_LOGS=$(find "$LOG_DIR" -name "*.log" -mtime +30 2>/dev/null | wc -l)

if [ $OLD_LOGS -gt 0 ]; then
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null
    log "${GREEN}✓ Deleted $OLD_LOGS old log files${NC}"
else
    log "${GREEN}✓ No old logs to clean${NC}"
fi

# ============================================================================
# 6. DISK SPACE CHECK
# ============================================================================

log "${BLUE}➤ Checking disk space...${NC}"

# Check /tmp usage
TMP_USAGE=$(df /tmp | awk 'NR==2 {print substr($5,1,length($5)-1)}')
if [ "$TMP_USAGE" -gt 80 ]; then
    log "${RED}⚠ WARNING: /tmp is ${TMP_USAGE}% full!${NC}"
else
    log "${GREEN}✓ /tmp usage: ${TMP_USAGE}%${NC}"
fi

# Check home directory
HOME_USAGE=$(df /home | awk 'NR==2 {print substr($5,1,length($5)-1)}')
if [ "$HOME_USAGE" -gt 80 ]; then
    log "${RED}⚠ WARNING: /home is ${HOME_USAGE}% full!${NC}"
else
    log "${GREEN}✓ /home usage: ${HOME_USAGE}%${NC}"
fi

# ============================================================================
# 7. CLEAN OLD SELENIUM TEMP FILES
# ============================================================================

log "${BLUE}➤ Cleaning Selenium temp files...${NC}"

SELENIUM_COUNT=$(find /tmp -name "rust_mozprofile*" -o -name "tmp*mozilla*" -o -name "scoped_dir*" 2>/dev/null | wc -l)

if [ $SELENIUM_COUNT -gt 0 ]; then
    find /tmp -name "rust_mozprofile*" -delete 2>/dev/null || true
    find /tmp -name "tmp*mozilla*" -delete 2>/dev/null || true
    find /tmp -name "scoped_dir*" -delete 2>/dev/null || true
    log "${GREEN}✓ Cleaned $SELENIUM_COUNT Selenium temp items${NC}"
else
    log "${GREEN}✓ No Selenium temp files to clean${NC}"
fi

# ============================================================================
# SUMMARY
# ============================================================================

log "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
log "${GREEN}✓ Daily cleanup completed successfully${NC}"
log "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Keep only last 100 lines of cleanup log
if [ -f "$LOG_FILE" ]; then
    tail -100 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

exit 0
