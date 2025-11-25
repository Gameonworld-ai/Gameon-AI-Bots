#!/bin/bash
# Unified Smart Cron Wrapper - PARALLEL EXECUTION
# Runs Connect4, Checkers, and Tic Tac Toe simultaneously for faster completion

set -e

SCRIPT_DIR="/home/ubuntu/bots"
LOCK_FILE="/tmp/gameon_bot.lock"
PID_FILE="/tmp/gameon_bot.pid"
LOG_FILE="$SCRIPT_DIR/logs/cron_wrapper.log"
CONFIG_FILE="$SCRIPT_DIR/accounts.json"

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Logging functions
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_color() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Change to bot directory
cd "$SCRIPT_DIR" || exit 1

log_color "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
log_color "${BLUE}║     Smart Cron Execution - PARALLEL Game Manager             ║${NC}"
log_color "${BLUE}║   Connect 4 + Checkers + Tic Tac Toe Simultaneously          ║${NC}"
log_color "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_color "${RED}✗ ERROR: accounts.json not found!${NC}"
    log_color "${RED}  Please create accounts.json with your configuration${NC}"
    exit 1
fi

# Function to check if games are enabled in config
check_game_enabled() {
    local game_type=$1
    local count=$(python3 -c "
import json
import sys
try:
    with open('$CONFIG_FILE') as f:
        config = json.load(f)
    count = 0
    for acc in config.get('accounts', []):
        if acc.get('enabled', True):
            game_config = acc.get('games', {}).get('$game_type', {})
            if game_config.get('enabled', False):
                count += 1
    print(count)
except Exception as e:
    print(0, file=sys.stderr)
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(0)
" 2>/dev/null || echo "0")
    echo "$count"
}

# Function to check for active processes
check_active_processes() {
    local game_name=$1
    local script_pattern=$2
    
    if pgrep -f "$script_pattern" > /dev/null; then
        local pid=$(pgrep -f "$script_pattern" | head -1)
        local runtime=$(($(date +%s) - $(stat -c %Y /proc/$pid 2>/dev/null || echo $(date +%s))))
        local runtime_min=$((runtime / 60))
        
        log_color "${YELLOW}⚠ $game_name bot still running (PID: $pid, Runtime: ${runtime_min}m)${NC}"
        
        # If running more than 2 hours, kill it
        if [ "$runtime" -gt 7200 ]; then
            log_color "${RED}⚠ Process stuck for ${runtime_min} minutes - killing${NC}"
            kill -9 "$pid" 2>/dev/null || true
            pkill -9 -f "$script_pattern" 2>/dev/null || true
            sleep 2
            return 1
        fi
        return 0
    fi
    return 1
}

# Function to cleanup Chrome and temp files
cleanup_chrome() {
    log_color "${BLUE}➤ Cleaning up Chrome processes and temp files...${NC}"
    
    # Kill Chrome
    local chrome_count=$(pgrep chrome 2>/dev/null | wc -l)
    if [ "$chrome_count" -gt 0 ]; then
        log_color "${YELLOW}  Killing $chrome_count Chrome processes${NC}"
        pkill -9 chrome 2>/dev/null || true
        sleep 2
    fi
    
    # Remove temp profiles
    local profile_count=$(find /tmp -name "chrome_profile_*" -type d 2>/dev/null | wc -l)
    if [ "$profile_count" -gt 0 ]; then
        log_color "${YELLOW}  Removing $profile_count temp profiles${NC}"
        rm -rf /tmp/chrome_profile_* 2>/dev/null || true
    fi
    
    log_color "${GREEN}✓ Cleanup complete${NC}"
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

# Check 1: Global lock file
log_color "${BLUE}➤ Checking for existing instances...${NC}"

if [ -f "$LOCK_FILE" ]; then
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            RUNTIME_SECONDS=$(ps -p "$OLD_PID" -o etimes= 2>/dev/null | tr -d ' ' || echo "0")
            RUNTIME_MINUTES=$((RUNTIME_SECONDS / 60))
            
            log_color "${YELLOW}⚠ Previous instance running (PID: $OLD_PID, ${RUNTIME_MINUTES}m)${NC}"
            
            if [ "$RUNTIME_SECONDS" -gt 7200 ]; then
                log_color "${RED}⚠ Process stuck for ${RUNTIME_MINUTES} minutes - killing${NC}"
                kill -9 "$OLD_PID" 2>/dev/null || true
                pkill -9 -f "multiple-connect4.py" 2>/dev/null || true
                pkill -9 -f "multiple-checkers.py" 2>/dev/null || true
                pkill -9 -f "multiple-tictactoe.py" 2>/dev/null || true
                cleanup_chrome
                rm -f "$LOCK_FILE" "$PID_FILE"
                log_color "${GREEN}✓ Cleaned up stuck process${NC}"
            else
                log_color "${YELLOW}⊘ SKIPPING - Previous run still active${NC}"
                log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
                exit 0
            fi
        else
            log_color "${YELLOW}⚠ Stale lock file - cleaning up${NC}"
            rm -f "$LOCK_FILE" "$PID_FILE"
        fi
    else
        log_color "${YELLOW}⚠ Lock file without PID - cleaning up${NC}"
        rm -f "$LOCK_FILE"
    fi
fi

log_color "${GREEN}✓ No conflicting instances${NC}"

# Check 2: Chrome processes
log_color "${BLUE}➤ Checking Chrome processes...${NC}"

CHROME_COUNT=$(ps aux | grep -c "[c]hrome" || echo "0")
if [ "$CHROME_COUNT" -gt 15 ]; then
    log_color "${YELLOW}⚠ Found $CHROME_COUNT Chrome processes${NC}"
    
    if pgrep -f "multiple-connect4.py\|multiple-checkers.py\|multiple-tictactoe.py" > /dev/null; then
        log_color "${YELLOW}⊘ SKIPPING - Bot processes active${NC}"
        log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
        exit 0
    else
        log_color "${YELLOW}  Cleaning up orphaned Chrome processes${NC}"
        cleanup_chrome
    fi
else
    log_color "${GREEN}✓ Chrome processes OK ($CHROME_COUNT)${NC}"
fi

# Check 3: System resources
log_color "${BLUE}➤ Checking system resources...${NC}"

AVAILABLE_MEM=$(free -m | awk '/^Mem:/{print $7}')
REQUIRED_MEM=3000  # 3GB minimum for parallel execution

if [ "$AVAILABLE_MEM" -lt "$REQUIRED_MEM" ]; then
    log_color "${YELLOW}⚠ Low memory: ${AVAILABLE_MEM}MB (recommended: ${REQUIRED_MEM}MB)${NC}"
    log_color "${YELLOW}  Cleaning up...${NC}"
    
    rm -rf /tmp/chrome_profile_* 2>/dev/null || true
    sleep 5
    
    AVAILABLE_MEM=$(free -m | awk '/^Mem:/{print $7}')
    if [ "$AVAILABLE_MEM" -lt 1500 ]; then
        log_color "${RED}⊘ SKIPPING - Insufficient memory: ${AVAILABLE_MEM}MB${NC}"
        log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
        exit 0
    fi
    log_color "${YELLOW}  Proceeding with ${AVAILABLE_MEM}MB (may run sequentially)${NC}"
fi

log_color "${GREEN}✓ Memory OK: ${AVAILABLE_MEM}MB available${NC}"

# CPU load check
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
CPU_CORES=$(nproc)
LOAD_THRESHOLD=$(echo "$CPU_CORES * 0.8" | bc)

if ! [[ "$LOAD_AVG" =~ ^[0-9]+\.?[0-9]*$ ]]; then
    LOAD_AVG="0.0"
fi

if (( $(echo "$LOAD_AVG > $LOAD_THRESHOLD" | bc -l 2>/dev/null || echo 0) )); then
    log_color "${YELLOW}⚠ High CPU load: $LOAD_AVG (threshold: $LOAD_THRESHOLD)${NC}"
    log_color "${YELLOW}⊘ SKIPPING - System under load${NC}"
    log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
    exit 0
fi

log_color "${GREEN}✓ CPU load OK: $LOAD_AVG (cores: $CPU_CORES)${NC}"

# Check 4: Cleanup old temp files
log_color "${BLUE}➤ Cleaning up old temporary files...${NC}"
CLEANED=$(find /tmp -name "chrome_profile_*" -type d -mmin +60 -delete -print 2>/dev/null | wc -l)
if [ "$CLEANED" -gt 0 ]; then
    log_color "${GREEN}✓ Cleaned $CLEANED old profiles${NC}"
else
    log_color "${GREEN}✓ No old profiles to clean${NC}"
fi

# Check which games are enabled
log_color "${BLUE}➤ Checking game configuration...${NC}"

CONNECT4_ENABLED=$(check_game_enabled "connect4")
CHECKERS_ENABLED=$(check_game_enabled "checkers")
TICTACTOE_ENABLED=$(check_game_enabled "tictactoe")

log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
log_color "${CYAN}Configuration Status:${NC}"
log_color "${CYAN}  Connect 4:   ${CONNECT4_ENABLED} accounts enabled${NC}"
log_color "${CYAN}  Checkers:    ${CHECKERS_ENABLED} accounts enabled${NC}"
log_color "${CYAN}  Tic Tac Toe: ${TICTACTOE_ENABLED} accounts enabled${NC}"
log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"

if [ "$CONNECT4_ENABLED" -eq 0 ] && [ "$CHECKERS_ENABLED" -eq 0 ] && [ "$TICTACTOE_ENABLED" -eq 0 ]; then
    log_color "${YELLOW}⊘ No games enabled in configuration${NC}"
    log_color "${BLUE}───────────────────────────────────────────────────────────────${NC}"
    exit 0
fi

# Count enabled games
ENABLED_GAMES=0
[ "$CONNECT4_ENABLED" -gt 0 ] && ENABLED_GAMES=$((ENABLED_GAMES + 1))
[ "$CHECKERS_ENABLED" -gt 0 ] && ENABLED_GAMES=$((ENABLED_GAMES + 1))
[ "$TICTACTOE_ENABLED" -gt 0 ] && ENABLED_GAMES=$((ENABLED_GAMES + 1))

# Determine execution mode
RUN_PARALLEL=1
if [ "$AVAILABLE_MEM" -lt "$REQUIRED_MEM" ]; then
    log_color "${YELLOW}⚠ Memory below threshold - will run sequentially${NC}"
    RUN_PARALLEL=0
elif [ "$ENABLED_GAMES" -le 1 ]; then
    log_color "${BLUE}ℹ Only one game enabled - sequential mode${NC}"
    RUN_PARALLEL=0
else
    log_color "${GREEN}✓ Running in PARALLEL mode${NC}"
fi

# All checks passed
log_color "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
log_color "${GREEN}✓ All checks passed - starting bot execution${NC}"
if [ $RUN_PARALLEL -eq 1 ]; then
    log_color "${GREEN}⚡ PARALLEL MODE: All games will run simultaneously${NC}"
else
    log_color "${YELLOW}⚡ SEQUENTIAL MODE: Games will run one after another${NC}"
fi
log_color "${GREEN}═══════════════════════════════════════════════════════════════${NC}"

# Create lock
echo $$ > "$PID_FILE"
touch "$LOCK_FILE"

# Ensure Xvfb
if ! pgrep -x "Xvfb" > /dev/null; then
    log_color "${BLUE}➤ Starting Xvfb virtual display...${NC}"
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    sleep 2
    log_color "${GREEN}✓ Xvfb started${NC}"
else
    log_color "${GREEN}✓ Xvfb already running${NC}"
fi

# Activate venv
log_color "${BLUE}➤ Activating virtual environment...${NC}"
source /home/ubuntu/venvs/bots/bin/activate
export DISPLAY=:99
log_color "${GREEN}✓ Virtual environment activated${NC}"

TOTAL_START=$(date +%s)
CONNECT4_SUCCESS=0
CHECKERS_SUCCESS=0
TICTACTOE_SUCCESS=0
CONNECT4_PID=""
CHECKERS_PID=""
TICTACTOE_PID=""

# ============================================================================
# PARALLEL EXECUTION FUNCTIONS
# ============================================================================

run_connect4() {
    log_color "${MAGENTA}╔═══════════════════════════════════════════════════════════════╗${NC}"
    log_color "${MAGENTA}║                   STARTING CONNECT 4 BOT                      ║${NC}"
    log_color "${MAGENTA}║                 Accounts: ${CONNECT4_ENABLED}                                         ║${NC}"
    log_color "${MAGENTA}╚═══════════════════════════════════════════════════════════════╝${NC}"
    
    # Check for active processes
    if check_active_processes "Connect4" "multiple-connect4.py"; then
        log_color "${YELLOW}⊘ SKIPPING Connect4 - already running${NC}"
        return 1
    fi
    
    C4_START=$(date +%s)
    log_color "${CYAN}➤ Executing Connect4 bot...${NC}"
    
    set +e
    python multiple-connect4.py
    C4_EXIT=$?
    set -e
    
    C4_END=$(date +%s)
    C4_DURATION=$((C4_END - C4_START))
    C4_MIN=$((C4_DURATION / 60))
    C4_SEC=$((C4_DURATION % 60))
    
    if [ $C4_EXIT -eq 0 ]; then
        log_color "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${GREEN}║          CONNECT 4 COMPLETED SUCCESSFULLY                     ║${NC}"
        log_color "${GREEN}║          Duration: ${C4_MIN}m ${C4_SEC}s                                         ║${NC}"
        log_color "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 0
    else
        log_color "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${RED}║          CONNECT 4 FAILED                                     ║${NC}"
        log_color "${RED}║          Exit Code: $C4_EXIT                                        ║${NC}"
        log_color "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 1
    fi
}

run_checkers() {
    log_color "${MAGENTA}╔═══════════════════════════════════════════════════════════════╗${NC}"
    log_color "${MAGENTA}║                   STARTING CHECKERS BOT                       ║${NC}"
    log_color "${MAGENTA}║                 Accounts: ${CHECKERS_ENABLED}                                         ║${NC}"
    log_color "${MAGENTA}╚═══════════════════════════════════════════════════════════════╝${NC}"
    
    # Check for active processes
    if check_active_processes "Checkers" "multiple-checkers.py"; then
        log_color "${YELLOW}⊘ SKIPPING Checkers - already running${NC}"
        return 1
    fi
    
    CH_START=$(date +%s)
    log_color "${CYAN}➤ Executing Checkers bot...${NC}"
    
    set +e
    python multiple-checkers.py
    CH_EXIT=$?
    set -e
    
    CH_END=$(date +%s)
    CH_DURATION=$((CH_END - CH_START))
    CH_MIN=$((CH_DURATION / 60))
    CH_SEC=$((CH_DURATION % 60))
    
    if [ $CH_EXIT -eq 0 ]; then
        log_color "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${GREEN}║          CHECKERS COMPLETED SUCCESSFULLY                      ║${NC}"
        log_color "${GREEN}║          Duration: ${CH_MIN}m ${CH_SEC}s                                         ║${NC}"
        log_color "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 0
    else
        log_color "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${RED}║          CHECKERS FAILED                                      ║${NC}"
        log_color "${RED}║          Exit Code: $CH_EXIT                                        ║${NC}"
        log_color "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 1
    fi
}

run_tictactoe() {
    log_color "${MAGENTA}╔═══════════════════════════════════════════════════════════════╗${NC}"
    log_color "${MAGENTA}║                  STARTING TIC TAC TOE BOT                     ║${NC}"
    log_color "${MAGENTA}║                 Accounts: ${TICTACTOE_ENABLED}                                         ║${NC}"
    log_color "${MAGENTA}╚═══════════════════════════════════════════════════════════════╝${NC}"
    
    # Check for active processes
    if check_active_processes "TicTacToe" "multiple-tictactoe.py"; then
        log_color "${YELLOW}⊘ SKIPPING Tic Tac Toe - already running${NC}"
        return 1
    fi
    
    TT_START=$(date +%s)
    log_color "${CYAN}➤ Executing Tic Tac Toe bot...${NC}"
    
    set +e
    python multiple-tictactoe.py
    TT_EXIT=$?
    set -e
    
    TT_END=$(date +%s)
    TT_DURATION=$((TT_END - TT_START))
    TT_MIN=$((TT_DURATION / 60))
    TT_SEC=$((TT_DURATION % 60))
    
    if [ $TT_EXIT -eq 0 ]; then
        log_color "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${GREEN}║          TIC TAC TOE COMPLETED SUCCESSFULLY                   ║${NC}"
        log_color "${GREEN}║          Duration: ${TT_MIN}m ${TT_SEC}s                                         ║${NC}"
        log_color "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 0
    else
        log_color "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
        log_color "${RED}║          TIC TAC TOE FAILED                                   ║${NC}"
        log_color "${RED}║          Exit Code: $TT_EXIT                                        ║${NC}"
        log_color "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 1
    fi
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if [ $RUN_PARALLEL -eq 1 ]; then
    # ========================================================================
    # PARALLEL MODE - All games run simultaneously
    # ========================================================================
    
    log_color "${MAGENTA}⚡⚡⚡ STARTING PARALLEL EXECUTION ⚡⚡⚡${NC}"
    
    # Start Connect4 in background
    if [ "$CONNECT4_ENABLED" -gt 0 ]; then
        (
            if run_connect4; then
                echo "1" > /tmp/connect4_success.flag
            else
                echo "0" > /tmp/connect4_success.flag
            fi
        ) &
        CONNECT4_PID=$!
        log_color "${CYAN}➤ Connect4 started in background (PID: $CONNECT4_PID)${NC}"
    fi
    
    # Small delay to stagger startup
    sleep 3
    
    # Start Checkers in background
    if [ "$CHECKERS_ENABLED" -gt 0 ]; then
        (
            if run_checkers; then
                echo "1" > /tmp/checkers_success.flag
            else
                echo "0" > /tmp/checkers_success.flag
            fi
        ) &
        CHECKERS_PID=$!
        log_color "${CYAN}➤ Checkers started in background (PID: $CHECKERS_PID)${NC}"
    fi
    
    # Small delay to stagger startup
    sleep 3
    
    # Start Tic Tac Toe in background
    if [ "$TICTACTOE_ENABLED" -gt 0 ]; then
        (
            if run_tictactoe; then
                echo "1" > /tmp/tictactoe_success.flag
            else
                echo "0" > /tmp/tictactoe_success.flag
            fi
        ) &
        TICTACTOE_PID=$!
        log_color "${CYAN}➤ Tic Tac Toe started in background (PID: $TICTACTOE_PID)${NC}"
    fi
    
    # Monitor all processes
    log_color "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    log_color "${BLUE}⏳ Waiting for all games to complete...${NC}"
    log_color "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    
    # Wait for Connect4
    if [ -n "$CONNECT4_PID" ]; then
        log_color "${YELLOW}⏳ Waiting for Connect4 (PID: $CONNECT4_PID)...${NC}"
        wait $CONNECT4_PID
        if [ -f /tmp/connect4_success.flag ]; then
            CONNECT4_SUCCESS=$(cat /tmp/connect4_success.flag)
            rm -f /tmp/connect4_success.flag
        fi
        log_color "${GREEN}✓ Connect4 completed${NC}"
    fi
    
    # Wait for Checkers
    if [ -n "$CHECKERS_PID" ]; then
        log_color "${YELLOW}⏳ Waiting for Checkers (PID: $CHECKERS_PID)...${NC}"
        wait $CHECKERS_PID
        if [ -f /tmp/checkers_success.flag ]; then
            CHECKERS_SUCCESS=$(cat /tmp/checkers_success.flag)
            rm -f /tmp/checkers_success.flag
        fi
        log_color "${GREEN}✓ Checkers completed${NC}"
    fi
    
    # Wait for Tic Tac Toe
    if [ -n "$TICTACTOE_PID" ]; then
        log_color "${YELLOW}⏳ Waiting for Tic Tac Toe (PID: $TICTACTOE_PID)...${NC}"
        wait $TICTACTOE_PID
        if [ -f /tmp/tictactoe_success.flag ]; then
            TICTACTOE_SUCCESS=$(cat /tmp/tictactoe_success.flag)
            rm -f /tmp/tictactoe_success.flag
        fi
        log_color "${GREEN}✓ Tic Tac Toe completed${NC}"
    fi
    
    log_color "${GREEN}✓ All parallel processes completed${NC}"
    
else
    # ========================================================================
    # SEQUENTIAL MODE - Games run one after another
    # ========================================================================
    
    log_color "${YELLOW}⚡ SEQUENTIAL EXECUTION MODE ⚡${NC}"
    
    # Run Connect4 first
    if [ "$CONNECT4_ENABLED" -gt 0 ]; then
        if run_connect4; then
            CONNECT4_SUCCESS=1
        fi
        
        # Cleanup between games
        log_color "${BLUE}➤ Cleaning up after Connect 4...${NC}"
        cleanup_chrome
        sleep 3
    fi
    
    # Run Checkers second
    if [ "$CHECKERS_ENABLED" -gt 0 ]; then
        # Add delay if previous game ran
        if [ "$CONNECT4_ENABLED" -gt 0 ] && [ $CONNECT4_SUCCESS -eq 1 ]; then
            log_color "${BLUE}➤ Waiting 30 seconds before starting Checkers...${NC}"
            for i in {30..1}; do
                echo -ne "\r  Countdown: ${i}s remaining...  "
                sleep 1
            done
            echo -e "\r${GREEN}✓ Ready to start Checkers${NC}                    "
        fi
        
        if run_checkers; then
            CHECKERS_SUCCESS=1
        fi
        
        # Cleanup between games
        log_color "${BLUE}➤ Cleaning up after Checkers...${NC}"
        cleanup_chrome
        sleep 3
    fi
    
    # Run Tic Tac Toe third
    if [ "$TICTACTOE_ENABLED" -gt 0 ]; then
        # Add delay if previous games ran
        if [ $CONNECT4_SUCCESS -eq 1 ] || [ $CHECKERS_SUCCESS -eq 1 ]; then
            log_color "${BLUE}➤ Waiting 30 seconds before starting Tic Tac Toe...${NC}"
            for i in {30..1}; do
                echo -ne "\r  Countdown: ${i}s remaining...  "
                sleep 1
            done
            echo -e "\r${GREEN}✓ Ready to start Tic Tac Toe${NC}                    "
        fi
        
        if run_tictactoe; then
            TICTACTOE_SUCCESS=1
        fi
    fi
fi

# Final cleanup
log_color "${BLUE}➤ Final cleanup...${NC}"
cleanup_chrome
sleep 2

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))
TOTAL_MIN=$((TOTAL_DURATION / 60))
TOTAL_SEC=$((TOTAL_DURATION % 60))

# Remove locks
rm -f "$LOCK_FILE" "$PID_FILE"

# Deactivate venv
deactivate

# ============================================================================
# FINAL SUMMARY
# ============================================================================

log_color "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
log_color "${BLUE}║                   EXECUTION SUMMARY                           ║${NC}"
log_color "${BLUE}╠═══════════════════════════════════════════════════════════════╣${NC}"

if [ "$CONNECT4_ENABLED" -gt 0 ]; then
    if [ $CONNECT4_SUCCESS -eq 1 ]; then
        log_color "${BLUE}║  Connect 4:    ${GREEN}✓ SUCCESS${BLUE}                                       ║${NC}"
    else
        log_color "${BLUE}║  Connect 4:    ${RED}✗ FAILED/SKIPPED${BLUE}                              ║${NC}"
    fi
fi

if [ "$CHECKERS_ENABLED" -gt 0 ]; then
    if [ $CHECKERS_SUCCESS -eq 1 ]; then
        log_color "${BLUE}║  Checkers:     ${GREEN}✓ SUCCESS${BLUE}                                       ║${NC}"
    else
        log_color "${BLUE}║  Checkers:     ${RED}✗ FAILED/SKIPPED${BLUE}                              ║${NC}"
    fi
fi

if [ "$TICTACTOE_ENABLED" -gt 0 ]; then
    if [ $TICTACTOE_SUCCESS -eq 1 ]; then
        log_color "${BLUE}║  Tic Tac Toe:  ${GREEN}✓ SUCCESS${BLUE}                                       ║${NC}"
    else
        log_color "${BLUE}║  Tic Tac Toe:  ${RED}✗ FAILED/SKIPPED${BLUE}                              ║${NC}"
    fi
fi

log_color "${BLUE}╠═══════════════════════════════════════════════════════════════╣${NC}"

if [ $RUN_PARALLEL -eq 1 ]; then
    log_color "${BLUE}║  Mode:         ${MAGENTA}⚡ PARALLEL${BLUE}                                       ║${NC}"
else
    log_color "${BLUE}║  Mode:         ${YELLOW}→ SEQUENTIAL${BLUE}                                    ║${NC}"
fi

log_color "${BLUE}║  Total Time:   ${TOTAL_MIN}m ${TOTAL_SEC}s                                         ║${NC}"
log_color "${BLUE}║  Completed:    $(date '+%Y-%m-%d %H:%M:%S')                            ║${NC}"
log_color "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"

# Cleanup old logs (keep 30 days)
log_color "${BLUE}➤ Cleaning old log files...${NC}"
DELETED_LOGS=$(find logs -name "*.log" -mtime +30 -delete -print 2>/dev/null | wc -l)
if [ "$DELETED_LOGS" -gt 0 ]; then
    log_color "${GREEN}✓ Deleted $DELETED_LOGS old log files${NC}"
else
    log_color "${GREEN}✓ No old logs to clean${NC}"
fi

# Exit with success if at least one game succeeded
if [ $CONNECT4_SUCCESS -eq 1 ] || [ $CHECKERS_SUCCESS -eq 1 ] || [ $TICTACTOE_SUCCESS -eq 1 ]; then
    log_color "${GREEN}✓ Execution completed successfully${NC}"
    exit 0
else
    log_color "${YELLOW}⊘ No games were executed${NC}"
    exit 1
fi
