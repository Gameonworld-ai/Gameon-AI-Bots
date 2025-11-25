#!/bin/bash
# Auto Chrome Cache Cleanup for Cron Jobs
# Safe for multiple concurrent bot processes
# Add to crontab: */30 * * * * /path/to/cron_cache_cleanup.sh

LOG_FILE="/home/ubuntu/bots/logs/cache_cleanup.log"
LOCK_FILE="/tmp/chrome_cleanup.lock"
PROFILE_DIR="/tmp"
AGE_HOURS=2
MAX_PROFILES=50  # Alert if more than this

# Ensure log directory exists
mkdir -p "$(dirname $LOG_FILE)"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Prevent multiple instances
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if ps -p "$LOCK_PID" > /dev/null 2>&1; then
        log "Cleanup already running (PID: $LOCK_PID), skipping"
        exit 0
    else
        log "Removing stale lock file"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "═══════════════════════════════════════════════════════"
log "Starting automatic cache cleanup"

# Get active profiles
ACTIVE_PROFILES=$(ps aux | grep chrome | grep user-data-dir | grep -oP 'user-data-dir=\K[^ ]+' | sort -u)
ACTIVE_COUNT=$(echo "$ACTIVE_PROFILES" | grep -v '^$' | wc -l)
log "Active Chrome profiles: $ACTIVE_COUNT"

# Find all profiles
ALL_PROFILES=$(find "$PROFILE_DIR" -maxdepth 1 -type d -name "chrome_profile_*" 2>/dev/null)
TOTAL_COUNT=$(echo "$ALL_PROFILES" | grep -v '^$' | wc -l)
log "Total Chrome profiles: $TOTAL_COUNT"

# Alert if too many profiles
if [ $TOTAL_COUNT -gt $MAX_PROFILES ]; then
    log "⚠️  WARNING: Too many profiles ($TOTAL_COUNT > $MAX_PROFILES)"
    log "⚠️  Possible profile leak or cleanup not running properly"
fi

# Cleanup old profiles
DELETED=0
SKIPPED=0
TOTAL_SIZE=0

while IFS= read -r profile_path; do
    [ -z "$profile_path" ] && continue
    
    profile_name=$(basename "$profile_path")
    
    # Check if in use
    IS_ACTIVE=false
    while IFS= read -r active; do
        [ -z "$active" ] && continue
        if [[ "$active" == *"$profile_name"* ]]; then
            IS_ACTIVE=true
            break
        fi
    done <<< "$ACTIVE_PROFILES"
    
    if [ "$IS_ACTIVE" = true ]; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    # Check age
    AGE_MINUTES=$(( AGE_HOURS * 60 ))
    if [ $(find "$profile_path" -maxdepth 0 -type d -mmin +$AGE_MINUTES 2>/dev/null | wc -l) -eq 1 ]; then
        # Get size before deleting
        SIZE=$(du -sb "$profile_path" 2>/dev/null | cut -f1 || echo 0)
        
        # Double-check not in use (process might have started)
        STILL_ACTIVE=$(ps aux | grep chrome | grep "$profile_name" | grep -v grep | wc -l)
        
        if [ $STILL_ACTIVE -eq 0 ]; then
            if rm -rf "$profile_path" 2>/dev/null; then
                TOTAL_SIZE=$((TOTAL_SIZE + SIZE))
                DELETED=$((DELETED + 1))
            fi
        else
            SKIPPED=$((SKIPPED + 1))
        fi
    else
        SKIPPED=$((SKIPPED + 1))
    fi
done <<< "$ALL_PROFILES"

TOTAL_SIZE_MB=$((TOTAL_SIZE / 1024 / 1024))

log "Cleanup results: Deleted=$DELETED, Protected=$SKIPPED, Freed=${TOTAL_SIZE_MB}MB"

# Clean Chromium temp files (older than AGE_HOURS)
CHROMIUM_DELETED=0
OLD_CHROMIUM=$(find /tmp -maxdepth 1 -name '.org.chromium.*' -type d -mmin +$((AGE_HOURS * 60)) 2>/dev/null)

while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    if rm -rf "$dir" 2>/dev/null; then
        CHROMIUM_DELETED=$((CHROMIUM_DELETED + 1))
    fi
done <<< "$OLD_CHROMIUM"

if [ $CHROMIUM_DELETED -gt 0 ]; then
    log "Cleaned $CHROMIUM_DELETED Chromium temp directories"
fi

# Check disk space
DISK_USAGE=$(df -h /tmp | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    log "⚠️  WARNING: /tmp disk usage is ${DISK_USAGE}%"
fi

# Memory check
MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
if [ $MEM_AVAILABLE -lt 2000 ]; then
    log "⚠️  WARNING: Low memory - only ${MEM_AVAILABLE}MB available"
fi

# Count zombie Chrome processes
CHROME_PROCS=$(ps aux | grep -E 'chrome|chromedriver' | grep -v grep | wc -l)
if [ $CHROME_PROCS -gt 30 ]; then
    log "⚠️  WARNING: High Chrome process count: $CHROME_PROCS"
fi

log "Cleanup complete ✓"
log "═══════════════════════════════════════════════════════"

# Trim log file if too large (keep last 1000 lines)
if [ -f "$LOG_FILE" ]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE")
    if [ $LINE_COUNT -gt 1000 ]; then
        tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp"
        mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi

exit 0
