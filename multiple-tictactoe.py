#!/home/ubuntu/venvs/bots/bin/python3
"""
Tic Tac Toe Multi-Account PARALLEL Bot - FIXED VERSION
Correctly handles the 8x8 checkerboard layout with 3x3 tic-tac-toe positions
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import random
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import threading
from copy import deepcopy
import concurrent.futures

# Configure logging
LOG_DIR = Path("/home/ubuntu/bots/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'tictactoe_parallel_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Thread-safe progress tracker
class ProgressTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.accounts_completed = 0
        self.games_completed = 0
        self.games_succeeded = 0
        
    def account_done(self):
        with self.lock:
            self.accounts_completed += 1
            
    def game_done(self, succeeded=True):
        with self.lock:
            self.games_completed += 1
            if succeeded:
                self.games_succeeded += 1
    
    def get_stats(self):
        with self.lock:
            return self.accounts_completed, self.games_completed, self.games_succeeded

tracker = ProgressTracker()


# ============================================================================
# AI LOGIC - Minimax with Alpha-Beta Pruning
# ============================================================================

def get_lines():
    """Get all winning lines on the board"""
    lines = []
    # Rows
    for r in range(3):
        lines.append([(r, 0), (r, 1), (r, 2)])
    # Columns
    for c in range(3):
        lines.append([(0, c), (1, c), (2, c)])
    # Diagonals
    lines.append([(0, 0), (1, 1), (2, 2)])
    lines.append([(0, 2), (1, 1), (2, 0)])
    return lines

def check_winner(board):
    """Check if there's a winner. Returns 'X', 'O', or None"""
    for line in get_lines():
        values = [board[r][c] for r, c in line]
        if values[0] == values[1] == values[2] and values[0] is not None:
            return values[0]
    return None

def is_board_full(board):
    """Check if board is full"""
    return all(board[r][c] is not None for r in range(3) for c in range(3))

def get_valid_moves(board):
    """Get all valid (empty) positions"""
    return [(r, c) for r in range(3) for c in range(3) if board[r][c] is None]

def evaluate_board(board, player):
    """Evaluate board position"""
    winner = check_winner(board)
    if winner == player:
        return 100
    elif winner is not None:
        return -100
    return 0

def minimax(board, depth, is_maximizing, player, alpha, beta, start_time, max_time):
    """Minimax with alpha-beta pruning and time limit"""
    # Time check
    if time.time() - start_time > max_time:
        return 0
    
    opponent = 'O' if player == 'X' else 'X'
    
    winner = check_winner(board)
    if winner == player:
        return 100 - depth
    elif winner == opponent:
        return depth - 100
    elif is_board_full(board):
        return 0
    
    if depth >= 9:
        return 0
    
    valid_moves = get_valid_moves(board)
    
    if is_maximizing:
        max_eval = float('-inf')
        for r, c in valid_moves:
            board[r][c] = player
            eval_score = minimax(board, depth + 1, False, player, alpha, beta, start_time, max_time)
            board[r][c] = None
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for r, c in valid_moves:
            board[r][c] = opponent
            eval_score = minimax(board, depth + 1, True, player, alpha, beta, start_time, max_time)
            board[r][c] = None
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval

def get_best_move(board, player, max_time=6):
    """Get best move using minimax with time limit"""
    start_time = time.time()
    valid_moves = get_valid_moves(board)
    
    if not valid_moves:
        return None
    
    # Center preference for opening
    if board[1][1] is None:
        move_count = sum(1 for r in range(3) for c in range(3) if board[r][c] is not None)
        if move_count <= 1:
            return (1, 1)
    
    best_move = None
    best_score = float('-inf')
    
    for r, c in valid_moves:
        if time.time() - start_time > max_time:
            break
        
        board[r][c] = player
        score = minimax(board, 0, False, player, float('-inf'), float('inf'), start_time, max_time)
        board[r][c] = None
        
        if score > best_score:
            best_score = score
            best_move = (r, c)
    
    return best_move if best_move else random.choice(valid_moves)


class TicTacToeBot:
    def __init__(self, account_email, account_password, dashboard_url="https://app.gameonworld.ai/dashboard", 
                 bet_increase_clicks=0, headless=True, max_time_per_move=6, ai_depth=9):
        
        # Create unique user data directory for this account
        import hashlib
        account_hash = hashlib.md5(account_email.encode()).hexdigest()[:8]
        user_data_dir = f"/tmp/chrome_profile_{account_hash}_{int(time.time())}"
        
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--window-size=1920,1080')
        
        if headless:
            options.add_argument('--headless=new')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.dashboard_url = dashboard_url
        self.account_email = account_email
        self.account_password = account_password
        self.game_iframe = None
        self.bet_increase_clicks = bet_increase_clicks
        self.my_player = None
        self.max_time_per_move = max_time_per_move
        
        logger.info(f"[{self.account_email}] Bot initialized - Depth {ai_depth}, {max_time_per_move}s/move")
    
    def start(self):
        logger.info(f"[{self.account_email}] Opening login page...")
        self.driver.get("https://app.gameonworld.ai/auth/login")
        time.sleep(2)
    
    def close_popups(self):
        try:
            selectors = ["button.absolute.top-3.right-3", "button svg[viewBox='0 0 512 512']//ancestor::button",
                        "button[aria-label='Close']", "button[aria-label='close']", "button.close"]
            for sel in selectors:
                try:
                    for btn in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            time.sleep(0.5)
                            return True
                except: continue
            return False
        except: return False
    
    def login(self, email, password):
        try:
            logger.info(f"[{self.account_email}] Logging in...")
            email_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(0.5)
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for login
            time.sleep(5)
            
            # Close popups
            for _ in range(3):
                self.close_popups()
                time.sleep(0.5)
            
            logger.info(f"[{self.account_email}] ✓ Login successful")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Login error: {e}")
            return False
    
    def create_game(self):
        """Create a new Tic Tac Toe game"""
        try:
            logger.info(f"[{self.account_email}] Creating game...")
            
            # Navigate to dashboard
            self.driver.get(self.dashboard_url)
            time.sleep(3)
            
            # Find Tic Tac Toe game card
            game_cards = self.driver.find_elements(By.CSS_SELECTOR, "div[data-card='true'], div[class*='card']")
            
            for card in game_cards:
                card_text = card.text.lower()
                if 'tic' in card_text or 'tac' in card_text:
                    logger.info(f"[{self.account_email}] Found Tic Tac Toe card")
                    card.click()
                    time.sleep(2)
                    break
            
            # Click "Play Now" button
            play_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Play Now') or contains(text(), 'Play')]")
            
            for btn in play_buttons:
                if btn.is_displayed():
                    logger.info(f"[{self.account_email}] Clicking Play Now...")
                    btn.click()
                    time.sleep(2)
                    break
            
            # Increase bet if needed
            if self.bet_increase_clicks > 0:
                logger.info(f"[{self.account_email}] Increasing bet {self.bet_increase_clicks} times...")
                for _ in range(self.bet_increase_clicks):
                    try:
                        plus_btn = self.driver.find_element(By.CSS_SELECTOR, 
                            "button[aria-label='Increase bet'], button.plus, button[class*='plus']")
                        plus_btn.click()
                        time.sleep(0.3)
                    except:
                        break
            
            # Click "Play Game" button
            play_game_buttons = self.driver.find_elements(By.XPATH,
                "//button[contains(text(), 'Play Game') or contains(text(), 'Start')]")
            
            for btn in play_game_buttons:
                if btn.is_displayed():
                    logger.info(f"[{self.account_email}] Clicking Play Game...")
                    btn.click()
                    time.sleep(2)
                    break
            
            logger.info(f"[{self.account_email}] ✓ Game created")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Error creating game: {e}")
            return False
    
    def wait_for_opponent(self, timeout=900):
        """Wait for opponent to join"""
        logger.info(f"[{self.account_email}] Waiting for opponent...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe")
                
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if "tictac" in src.lower() or "tic-tac" in src.lower():
                        logger.info(f"[{self.account_email}] ✓ Game iframe found")
                        self.game_iframe = iframe
                        return True
                
                time.sleep(2)
                
            except Exception as e:
                time.sleep(2)
        
        logger.warning(f"[{self.account_email}] ✗ Opponent timeout")
        return False
    
    def switch_to_game_iframe(self):
        """Switch to game iframe"""
        try:
            if not self.game_iframe:
                logger.error(f"[{self.account_email}] No game iframe")
                return False
            
            self.driver.switch_to.frame(self.game_iframe)
            time.sleep(3)
            logger.info(f"[{self.account_email}] ✓ Switched to iframe")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Iframe switch error: {e}")
            return False
    
    def read_board_state(self):
        """
        Read the 3x3 tic-tac-toe board state.
        Based on the working tictactoe.py - uses div.cell selector.
        """
        try:
            board = [[None for _ in range(3)] for _ in range(3)]
            
            # Get all cells using the correct selector
            cells = self.driver.find_elements(By.CSS_SELECTOR, "div.cell")
            
            logger.info(f"[{self.account_email}] Found {len(cells)} cells")
            
            if len(cells) != 9:
                logger.warning(f"[{self.account_email}] Expected 9 cells, found {len(cells)}")
                # Try alternative selector
                cells = self.driver.find_elements(By.CSS_SELECTOR, 
                    "div[class*='aspect-square'], div[class*='cell']")
                logger.info(f"[{self.account_email}] Alternative selector found {len(cells)} cells")
                
                if len(cells) == 0:
                    logger.error(f"[{self.account_email}] No cells found!")
                    return None
            
            # Read each cell (use first 9 cells if more than 9)
            for i in range(min(9, len(cells))):
                cell = cells[i]
                row = i // 3
                col = i % 3
                
                try:
                    # Method 1: Check data-value attribute
                    data_value = cell.get_attribute('data-value')
                    if data_value:
                        try:
                            val = int(data_value)
                            board[row][col] = 'X' if val == 1 else 'O' if val == 2 else None
                            continue
                        except:
                            pass
                    
                    # Method 2: Check for images inside the cell
                    imgs = cell.find_elements(By.TAG_NAME, "img")
                    if imgs:
                        for img in imgs:
                            alt = img.get_attribute('alt') or ''
                            src = img.get_attribute('src') or ''
                            
                            # X player (Player 1)
                            if alt.upper() == 'X' or 'W-rTeAz-qe.png' in src:
                                board[row][col] = 'X'
                                break
                            # O player (Player 2)
                            elif alt.upper() == 'O' or 'B-4DvpsQW3.png' in src:
                                board[row][col] = 'O'
                                break
                    
                    # Method 3: Check cell class for disabled state with value
                    if board[row][col] is None:
                        cell_class = cell.get_attribute('class') or ''
                        if 'disabled' in cell_class:
                            # Check the innerHTML for images
                            html = cell.get_attribute('innerHTML') or ''
                            if 'W-rTeAz-qe.png' in html or 'alt="X"' in html:
                                board[row][col] = 'X'
                            elif 'B-4DvpsQW3.png' in html or 'alt="O"' in html:
                                board[row][col] = 'O'
                
                except Exception as e:
                    logger.debug(f"[{self.account_email}] Error reading cell {i}: {e}")
                    continue
            
            return board
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Error reading board: {e}")
            import traceback
            logger.error(f"[{self.account_email}] Traceback: {traceback.format_exc()}")
            return None
    
    def detect_my_player(self):
        """Detect if we are X or O"""
        try:
            logger.info(f"[{self.account_email}] Detecting player...")
            time.sleep(2)
            
            # Method 1: Check turn indicator divs
            turn_divs = self.driver.find_elements(By.CSS_SELECTOR, 
                "div.current-player-turn, div.my-turn, div.opponent-turn")
            
            for div in turn_divs:
                if div.is_displayed():
                    text = div.text.upper()
                    logger.info(f"[{self.account_email}] Turn indicator: '{text}'")
                    
                    if 'YOUR TURN' in text or 'MY TURN' in text:
                        classes = div.get_attribute('class') or ''
                        if 'my-turn-o' in classes:
                            self.my_player = 'O'
                            logger.info(f"[{self.account_email}] ✓ Bot is O - from class")
                            return True
                        elif 'my-turn-x' in classes:
                            self.my_player = 'X'
                            logger.info(f"[{self.account_email}] ✓ Bot is X - from class")
                            return True
            
            # Method 2: Check for turn indicator (fallback)
            your_turn = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Your Turn')]")
            if your_turn and any(el.is_displayed() for el in your_turn):
                self.my_player = 'X'
                logger.info(f"[{self.account_email}] ✓ Bot is X (goes first)")
                return True
            
            opponent_turn = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Opponent')]")
            if opponent_turn and any(el.is_displayed() for el in opponent_turn):
                self.my_player = 'O'
                logger.info(f"[{self.account_email}] ✓ Bot is O (goes second)")
                return True
            
            # Method 3: Check board state
            board = self.read_board_state()
            if board:
                filled = sum(1 for row in board for cell in row if cell is not None)
                logger.info(f"[{self.account_email}] Board has {filled} filled cells")
                if filled == 0:
                    self.my_player = 'X'
                    logger.info(f"[{self.account_email}] ✓ Bot is X (empty board)")
                    return True
                elif filled == 1:
                    self.my_player = 'O'
                    logger.info(f"[{self.account_email}] ✓ Bot is O (one piece)")
                    return True
            
            # Default
            self.my_player = 'O'
            logger.info(f"[{self.account_email}] ✓ Bot is O (default)")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Detection error: {e}")
            self.my_player = 'X'
            return True
    
    def is_my_turn(self):
        """Check if it's our turn - based on working tictactoe.py"""
        try:
            # Method 1: Check for my-turn class
            my_turn_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.my-turn")
            for div in my_turn_divs:
                if div.is_displayed():
                    text = div.text.upper()
                    if 'YOUR TURN' in text:
                        return True
            
            # Method 2: Check opponent-turn is NOT present
            opponent_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.opponent-turn")
            for div in opponent_divs:
                if div.is_displayed():
                    return False
            
            # Method 3: Check the board class
            boards = self.driver.find_elements(By.CSS_SELECTOR, "div.board")
            for board in boards:
                classes = board.get_attribute('class') or ''
                if 'my-turn-board' in classes:
                    return True
                if 'opponent-turn-board' in classes:
                    return False
            
            # Method 4: Fallback to XPath
            turn_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Your Turn')]")
            if turn_elements and any(el.is_displayed() for el in turn_elements):
                return True
            
            opponent_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Opponent')]")
            if opponent_elements and any(el.is_displayed() for el in opponent_elements):
                return False
            
            # If X and board is empty, it's our turn
            if self.my_player == 'X':
                board = self.read_board_state()
                if board:
                    filled = sum(1 for row in board for cell in row if cell is not None)
                    if filled == 0:
                        return True
            
            return False
            
        except:
            return False
    
    def make_move(self, row, col):
        """Make a move on the board - based on working tictactoe.py"""
        try:
            # Get cells using the correct selector
            cells = self.driver.find_elements(By.CSS_SELECTOR, 
                "div.cell, div[class*='aspect-square'], div[class*='cell']")
            
            logger.info(f"[{self.account_email}] Making move ({row},{col}) - {len(cells)} cells found")
            
            idx = row * 3 + col
            if idx < len(cells):
                cell = cells[idx]
                
                # Scroll into view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cell)
                time.sleep(0.3)
                
                # Try to click
                try:
                    cell.click()
                except:
                    # Fallback to JavaScript click
                    self.driver.execute_script("arguments[0].click();", cell)
                
                logger.info(f"[{self.account_email}] ✓ Moved to ({row},{col})")
                return True
            else:
                logger.error(f"[{self.account_email}] Cell index {idx} out of range (have {len(cells)} cells)")
                return False
                
        except Exception as e:
            logger.error(f"[{self.account_email}] Move error: {e}")
            import traceback
            logger.error(f"[{self.account_email}] Traceback: {traceback.format_exc()}")
            return False
    
    def play_game(self):
        """Play the game"""
        try:
            logger.info(f"[{self.account_email}] ═══ Starting Game ═══")
            time.sleep(3)
            
            if not self.detect_my_player():
                logger.error(f"[{self.account_email}] Could not detect player")
                return False
            
            move_count = 0
            max_moves = 50
            
            while move_count < max_moves:
                move_count += 1
                
                # Check if game ended
                try:
                    game_over = self.driver.find_elements(By.XPATH,
                        "//h1[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')] | " +
                        "//h2[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')]")
                    
                    if game_over and any(el.is_displayed() for el in game_over):
                        result = " ".join([el.text for el in game_over if el.is_displayed()])
                        logger.info(f"[{self.account_email}] ✓ Game ended - {result}")
                        return True
                except:
                    pass
                
                # Wait for our turn
                if not self.is_my_turn():
                    logger.info(f"[{self.account_email}] Waiting for opponent...")
                    time.sleep(2)
                    continue
                
                logger.info(f"[{self.account_email}] Our turn! Move #{move_count}")
                
                # Read board
                board = self.read_board_state()
                if board is None:
                    logger.error(f"[{self.account_email}] Could not read board")
                    time.sleep(2)
                    continue
                
                # Log board
                logger.info(f"[{self.account_email}] Board:")
                for i, row in enumerate(board):
                    row_str = " | ".join([cell if cell else "." for cell in row])
                    logger.info(f"[{self.account_email}]   {row_str}")
                
                # Calculate best move
                best_move = get_best_move(board, self.my_player, self.max_time_per_move)
                
                if best_move is None:
                    logger.warning(f"[{self.account_email}] No valid moves")
                    time.sleep(2)
                    continue
                
                row, col = best_move
                logger.info(f"[{self.account_email}] Best move: ({row},{col})")
                
                # Make the move
                if self.make_move(row, col):
                    logger.info(f"[{self.account_email}] ✓ Move successful")
                    time.sleep(2)
                else:
                    logger.warning(f"[{self.account_email}] ✗ Move failed")
                    time.sleep(1)
            
            logger.info(f"[{self.account_email}] ✓ Game complete")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Game error: {e}")
            return False
    
    def handle_post_game(self):
        """Handle post-game"""
        try:
            logger.info(f"[{self.account_email}] Post-game...")
            self.driver.switch_to.default_content()
            time.sleep(2)
            self.driver.get(self.dashboard_url)
            time.sleep(3)
            logger.info(f"[{self.account_email}] ✓ Post-game handled")
        except Exception as e:
            logger.error(f"[{self.account_email}] Post-game error: {e}")
    
    def quit(self):
        """Clean up"""
        try:
            self.driver.quit()
            logger.info(f"[{self.account_email}] Browser closed")
        except:
            pass


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_accounts_config(config_path='accounts.json'):
    """Load configuration"""
    try:
        with open(config_path, 'r') as f:
            full_config = json.load(f)
        
        tictactoe_accounts = []
        for acc in full_config.get('accounts', []):
            if not acc.get('enabled', True):
                continue
            
            games = acc.get('games', {})
            tictactoe_settings = games.get('tictactoe', {})
            
            if tictactoe_settings.get('enabled', False):
                tictactoe_accounts.append({
                    **acc,
                    'games_per_run': tictactoe_settings.get('games_per_run', 1),
                    'bet_increase_clicks': tictactoe_settings.get('bet_increase_clicks', 0)
                })
        
        tictactoe_config = {
            'accounts': tictactoe_accounts,
            'settings': {
                **full_config.get('settings', {}),
                'ai_settings': {
                    'max_time_per_move': tictactoe_settings.get('max_time_per_move', 6),
                    'ai_depth': tictactoe_settings.get('ai_depth', 9)
                }
            }
        }
        
        logger.info(f"Loaded {len(tictactoe_accounts)} accounts")
        return tictactoe_config
        
    except Exception as e:
        logger.error(f"Config error: {e}")
        sys.exit(1)


def run_bot_session(account, settings):
    """Run bot session"""
    email = account['email']
    password = account['password']
    games_to_play = account.get('games_per_run', 1)
    bet_clicks = account.get('bet_increase_clicks', 0)
    
    ai_settings = settings.get('ai_settings', {})
    max_time = ai_settings.get('max_time_per_move', 6)
    ai_depth = ai_settings.get('ai_depth', 9)
    
    logger.info(f"[{email}] Starting - {games_to_play} games, bet={bet_clicks}")
    
    bot = None
    try:
        bot = TicTacToeBot(
            account_email=email,
            account_password=password,
            bet_increase_clicks=bet_clicks,
            headless=settings.get('headless', True),
            max_time_per_move=max_time,
            ai_depth=ai_depth
        )
    except Exception as e:
        logger.error(f"[{email}] Bot creation failed: {e}")
        return {"email": email, "games_played": 0, "games_succeeded": 0, "success": False}
    
    games_played = 0
    games_succeeded = 0
    
    try:
        bot.start()
        
        if not bot.login(email, password):
            logger.error(f"[{email}] Login failed")
            return {"email": email, "games_played": 0, "games_succeeded": 0, "success": False}
        
        for game_num in range(1, games_to_play + 1):
            logger.info(f"[{email}] ─── Game {game_num}/{games_to_play} ───")
            
            try:
                if bot.create_game():
                    if bot.wait_for_opponent(timeout=settings.get('opponent_wait_timeout', 900)):
                        if bot.switch_to_game_iframe():
                            if bot.play_game():
                                games_succeeded += 1
                            games_played += 1
                            tracker.game_done(True)
                            bot.handle_post_game()
                        else:
                            logger.error(f"[{email}] Iframe switch failed")
                    else:
                        logger.warning(f"[{email}] No opponent")
                else:
                    logger.error(f"[{email}] Game creation failed")
                
                time.sleep(settings.get('wait_between_games', 10))
                
            except Exception as e:
                logger.error(f"[{email}] Game {game_num} error: {e}")
                continue
        
        tracker.account_done()
        return {"email": email, "games_played": games_played, "games_succeeded": games_succeeded, "success": True}
        
    except Exception as e:
        logger.error(f"[{email}] Session error: {e}")
        return {"email": email, "games_played": games_played, "games_succeeded": games_succeeded, "success": False}
    finally:
        if bot:
            bot.quit()


def main():
    """Main entry point"""
    config = load_accounts_config()
    accounts = config['accounts']
    settings = config['settings']
    
    logger.info("=" * 70)
    logger.info("TIC TAC TOE BOT - PARALLEL MULTI-ACCOUNT")
    logger.info("=" * 70)
    logger.info(f"Accounts: {len(accounts)}")
    logger.info(f"Parallel: {settings.get('max_parallel_accounts', 3)}")
    logger.info("=" * 70)
    
    max_workers = settings.get('max_parallel_accounts', 3)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, account in enumerate(accounts):
            account['_start_delay'] = i * settings.get('stagger_delay', 10)
            future = executor.submit(run_bot_session, account, settings)
            futures.append(future)
        
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # Print results
    logger.info("\n" + "=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)
    for result in results:
        logger.info(f"{result['email']}: {result['games_succeeded']}/{result['games_played']} games")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
