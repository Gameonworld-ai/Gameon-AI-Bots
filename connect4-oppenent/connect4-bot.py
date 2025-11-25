#!/home/ubuntu/venvs/bots/bin/python3
"""
Connect 4 Multi-Account PARALLEL Bot
Enhanced with ULTRA-GODMODE AI with Opponent Prediction & Multi-Move Analysis
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException,
    StaleElementReferenceException
)
import time
import random
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import threading
import concurrent.futures
import hashlib

# Configure logging
LOG_DIR = Path(os.getenv('LOG_DIR', '/home/ubuntu/bots/logs'))
LOG_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'bot_parallel_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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


class Connect4Bot:
    def __init__(self, account_email, account_password, dashboard_url="https://app.gameonworld.ai/dashboard", 
                 difficulty="ultra_expert", bet_increase_clicks=0, headless=True):
        
        # Create unique user data directory for this account
        account_hash = hashlib.md5(account_email.encode()).hexdigest()[:8]
        user_data_dir = f"/tmp/chrome_profile_{account_hash}_{int(time.time())}"
        
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Unique profile for each instance
        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--disable-extensions')
        options.add_argument('--remote-debugging-port=0')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        
        if headless:
            options.add_argument('--headless=new')
        
        # Random window size for isolation
        window_width = 1920 + random.randint(-100, 100)
        window_height = 1080 + random.randint(-100, 100)
        options.add_argument(f'--window-size={window_width},{window_height}')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.dashboard_url = dashboard_url
        self.game_iframe = None
        self.difficulty = difficulty
        self.bet_increase_clicks = bet_increase_clicks
        self.last_board_state = None
        self.my_player = None
        self.move_timeout = 10
        self.account_email = account_email
        self.account_password = account_password
        self.user_data_dir = user_data_dir
        logger.info(f"[{account_email}] Bot initialized - ULTRA-GODMODE AI")
        
    def start(self):
        """Navigate to login page"""
        time.sleep(random.uniform(0.5, 2.0))
        self.driver.get("https://app.gameonworld.ai/auth/login")
        time.sleep(2)
        logger.info(f"[{self.account_email}] Login page loaded")
    
    def close_popups(self):
        """Close any popups"""
        try:
            close_selectors = [
                "button.absolute.top-3.right-3",
                "button svg[viewBox='0 0 512 512']//ancestor::button",
                "button[aria-label='Close']",
                "button[aria-label='close']",
                "button.close",
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            time.sleep(0.5)
                            return True
                except:
                    continue
            
            try:
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                time.sleep(0.3)
            except:
                pass
            return False
        except:
            return False
    
    def login(self):
        """Login to platform"""
        try:
            logger.info(f"[{self.account_email}] Logging in...")
            time.sleep(random.uniform(1.0, 3.0))
            
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][placeholder='Email']"))
            )
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password'][placeholder='Password']")
            
            email_input.clear()
            time.sleep(0.3)
            email_input.send_keys(self.account_email)
            time.sleep(random.uniform(0.5, 1.0))
            
            password_input.clear()
            time.sleep(0.3)
            password_input.send_keys(self.account_password)
            time.sleep(random.uniform(0.5, 1.0))
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Login')]")
            login_button.click()
            
            WebDriverWait(self.driver, 15).until(
                lambda driver: "login" not in driver.current_url.lower()
            )
            time.sleep(2)
            
            for i in range(5):
                if self.close_popups():
                    time.sleep(0.5)
            
            logger.info(f"[{self.account_email}] Login successful ✓")
            return True
        except Exception as e:
            logger.error(f"[{self.account_email}] Login error: {e}")
            return False
    
    def wait_for_challenges(self, timeout=300):
        """Wait for Connect 4 challenges in 'Challenges' section only (NOT 'AI Challenges')"""
        logger.info(f"[{self.account_email}] Monitoring Challenges section (timeout: {timeout}s)...")
        start_time = time.time()
        last_refresh = time.time()
        
        while time.time() - start_time < timeout:
            try:
                elapsed = int(time.time() - start_time)
                self.close_popups()
                
                # Strategy 1: Find by exact text "Challenges" (not "AI Challenges")
                try:
                    # Look for div with exact text "Challenges"
                    challenges_section = self.driver.find_element(
                        By.XPATH,
                        "//div[text()='Challenges' and contains(@class, 'font-semibold')]"
                    )
                    
                    # Get the main container (try different ancestor levels)
                    for level in [2, 3, 4, 5]:
                        try:
                            section_container = challenges_section.find_element(
                                By.XPATH, f"./ancestor::div[{level}]"
                            )
                            
                            # Look for Connect 4 within this container
                            connect4_cards = section_container.find_elements(
                                By.XPATH,
                                ".//img[@alt='Connect 4']"
                            )
                            
                            if connect4_cards:
                                for card in connect4_cards:
                                    if card.is_displayed():
                                        logger.info(f"[{self.account_email}] Connect 4 found in 'Challenges' section (level {level})!")
                                        return True
                        except:
                            continue
                except:
                    pass
                
                # Strategy 2: Find all sections with "Challenges" in text, exclude "AI Challenges"
                try:
                    all_headers = self.driver.find_elements(
                        By.XPATH,
                        "//div[contains(text(), 'Challenges') and contains(@class, 'font-semibold')]"
                    )
                    
                    for header in all_headers:
                        header_text = header.text.strip()
                        
                        # Skip if this is "AI Challenges"
                        if "AI" in header_text:
                            logger.debug(f"[{self.account_email}] Skipping AI Challenges section")
                            continue
                        
                        # Only process if it's exactly "Challenges"
                        if header_text == "Challenges":
                            for level in [2, 3, 4, 5]:
                                try:
                                    section_container = header.find_element(
                                        By.XPATH, f"./ancestor::div[{level}]"
                                    )
                                    
                                    connect4_cards = section_container.find_elements(
                                        By.XPATH,
                                        ".//img[@alt='Connect 4']"
                                    )
                                    
                                    if connect4_cards:
                                        for card in connect4_cards:
                                            if card.is_displayed():
                                                logger.info(f"[{self.account_email}] Connect 4 found in 'Challenges' section!")
                                                return True
                                except:
                                    continue
                except:
                    pass
                
                # Strategy 3: Direct search with class filter
                try:
                    # Find all Connect 4 images
                    all_connect4 = self.driver.find_elements(
                        By.XPATH,
                        "//img[@alt='Connect 4']"
                    )
                    
                    for img in all_connect4:
                        if not img.is_displayed():
                            continue
                        
                        # Check if this image is NOT under "AI Challenges"
                        try:
                            # Look up the DOM tree for section headers
                            parent = img.find_element(By.XPATH, "./ancestor::div[contains(@class, 'overflow-x-auto')]/preceding-sibling::div[contains(@class, 'font-semibold')]")
                            
                            if parent.text.strip() == "Challenges":
                                logger.info(f"[{self.account_email}] Connect 4 found in 'Challenges' section (direct)!")
                                return True
                        except:
                            # Alternative: check if "AI Challenges" header is NOT nearby
                            try:
                                ai_header = img.find_element(
                                    By.XPATH,
                                    "./ancestor::div[5]//div[contains(text(), 'AI Challenges')]"
                                )
                                # If we found AI Challenges header nearby, skip this image
                                logger.debug(f"[{self.account_email}] Skipping Connect 4 in AI Challenges")
                                continue
                            except:
                                # No AI Challenges header found nearby, this is probably the right one
                                logger.info(f"[{self.account_email}] Connect 4 found (not in AI section)!")
                                return True
                except:
                    pass
                
                if elapsed % 10 == 0:
                    logger.info(f"[{self.account_email}] No Connect 4 in 'Challenges' section... ({elapsed}s)")
                
                if time.time() - last_refresh >= 30:
                    logger.info(f"[{self.account_email}] Refreshing page...")
                    self.driver.refresh()
                    time.sleep(2)
                    self.close_popups()
                    last_refresh = time.time()
                
                time.sleep(2)
            except Exception as e:
                logger.error(f"[{self.account_email}] Error checking challenges: {e}")
                time.sleep(2)
        
        logger.warning(f"[{self.account_email}] Timeout - no Connect 4 in 'Challenges' section")
        return False
    
    def join_challenge(self):
        """Find and join Connect 4 challenge from 'Challenges' section only"""
        try:
            self.close_popups()
            
            # Find "Challenges" header (not "AI Challenges")
            challenges_header = None
            headers = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'font-semibold') and contains(@class, 'text-gray-800') and text()='Challenges']"
            )
            
            for header in headers:
                # Verify it's not "AI Challenges" by checking the exact text
                if header.text.strip() == "Challenges":
                    challenges_header = header
                    break
            
            if not challenges_header:
                logger.error(f"[{self.account_email}] 'Challenges' section not found")
                return False
            
            # Get the section container
            section_container = challenges_header.find_element(By.XPATH, "./ancestor::div[3]")
            
            # Find Connect 4 within this specific section
            connect4_card = section_container.find_element(
                By.XPATH,
                ".//img[@alt='Connect 4']/ancestor::div[contains(@class, 'cursor-pointer')]"
            )
            
            logger.info(f"[{self.account_email}] Clicking Connect 4 in 'Challenges' section...")
            connect4_card.click()
            time.sleep(2)
            
            self.close_popups()
            
            join_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Join Challenge')]"))
            )
            logger.info(f"[{self.account_email}] Joining challenge...")
            join_button.click()
            time.sleep(3)
            
            for _ in range(5):
                self.close_popups()
                time.sleep(1)
            
            return self.switch_to_game_iframe()
        except Exception as e:
            logger.error(f"[{self.account_email}] Error joining challenge: {e}")
            return False
    
    def switch_to_game_iframe(self):
        """Switch to game iframe"""
        try:
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='connect4']"))
            )
            self.driver.switch_to.frame(iframe)
            self.game_iframe = iframe
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".board, table")))
            logger.info(f"[{self.account_email}] Game loaded!")
            return True
        except:
            logger.error(f"[{self.account_email}] Could not switch to iframe")
            return False
    
    def read_board_state(self):
        """Read current board state"""
        board = [[0]*7 for _ in range(6)]
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            for row_idx, row in enumerate(rows):
                cells = row.find_elements(By.CSS_SELECTOR, "td.board-cell")
                for col_idx, cell in enumerate(cells):
                    try:
                        if cell.find_elements(By.CSS_SELECTOR, "img[src*='red']"):
                            board[row_idx][col_idx] = 1
                    except:
                        pass
                    try:
                        if cell.find_elements(By.CSS_SELECTOR, "img[src*='yellow']"):
                            board[row_idx][col_idx] = 2
                    except:
                        pass
        except:
            pass
        return board
    
    def detect_player_number(self):
        """Detect which player the bot is"""
        if self.my_player is not None:
            return self.my_player
        
        try:
            bottom_timer = self.driver.find_elements(By.CSS_SELECTOR, ".turn-timer-bottom")
            if bottom_timer and bottom_timer[0].is_displayed():
                banners = self.driver.find_elements(By.CSS_SELECTOR, ".player-banner")
                if len(banners) >= 2:
                    style = banners[-1].get_attribute("style") or ""
                    self.my_player = 1 if "FD7235" in style else 2
                    logger.info(f"[{self.account_email}] Player {self.my_player}")
                    return self.my_player
        except:
            pass
        
        self.my_player = 1
        return self.my_player
    
    def is_my_turn(self):
        """Check if it's bot's turn"""
        try:
            turn_timer = self.driver.find_elements(By.CSS_SELECTOR, ".turn-timer-bottom")
            return len(turn_timer) > 0 and turn_timer[0].is_displayed()
        except:
            return False
    
    def get_valid_moves(self, board):
        """Get valid columns"""
        return [col for col in range(7) if board[0][col] == 0]
    
    def calculate_best_move(self, board, player=1):
        """ULTRA-GODMODE AI - Enhanced algorithm"""
        start_time = time.time()
        transposition_table = {}
        
        def board_hash(b):
            return tuple(tuple(row) for row in b)
        
        def check_winner(b, p):
            # Horizontal
            for r in range(6):
                for c in range(4):
                    if all(b[r][c+i] == p for i in range(4)):
                        return True
            # Vertical
            for c in range(7):
                for r in range(3):
                    if all(b[r+i][c] == p for i in range(4)):
                        return True
            # Diagonal /
            for r in range(3):
                for c in range(4):
                    if all(b[r+i][c+i] == p for i in range(4)):
                        return True
            # Diagonal \
            for r in range(3, 6):
                for c in range(4):
                    if all(b[r-i][c+i] == p for i in range(4)):
                        return True
            return False
        
        def get_next_row(b, col):
            for r in range(5, -1, -1):
                if b[r][col] == 0:
                    return r
            return None
        
        def evaluate_position(b, p):
            if check_winner(b, p):
                return 10000000
            if check_winner(b, 3-p):
                return -10000000
            
            score = 0
            # Center preference
            center_weights = {0: 10, 1: 30, 2: 50, 3: 70, 4: 50, 5: 30, 6: 10}
            for col in range(7):
                for row in range(6):
                    if b[row][col] == p:
                        score += (6 - row) * center_weights[col]
                    elif b[row][col] == 3-p:
                        score -= (6 - row) * center_weights[col] * 0.8
            
            return score
        
        def minimax(b, depth, alpha, beta, maximizing):
            if time.time() - start_time > 9.0:
                return None, evaluate_position(b, player)
            
            b_hash = board_hash(b)
            if b_hash in transposition_table and transposition_table[b_hash][0] >= depth:
                return transposition_table[b_hash][1], transposition_table[b_hash][2]
            
            if depth == 0:
                return None, evaluate_position(b, player)
            
            if check_winner(b, player):
                return None, 10000000 + depth * 10000
            if check_winner(b, 3-player):
                return None, -10000000 - depth * 10000
            
            valid = self.get_valid_moves(b)
            if not valid:
                return None, 0
            
            # Sort moves by center preference
            valid.sort(key=lambda x: abs(3 - x))
            
            if maximizing:
                max_eval = float('-inf')
                best = valid[0]
                
                for col in valid:
                    row = get_next_row(b, col)
                    if row is None:
                        continue
                    
                    b[row][col] = player
                    _, ev = minimax(b, depth-1, alpha, beta, False)
                    b[row][col] = 0
                    
                    if ev > max_eval:
                        max_eval = ev
                        best = col
                    
                    alpha = max(alpha, ev)
                    if beta <= alpha:
                        break
                
                transposition_table[b_hash] = (depth, best, max_eval)
                return best, max_eval
            else:
                min_eval = float('inf')
                best = valid[0]
                
                for col in valid:
                    row = get_next_row(b, col)
                    if row is None:
                        continue
                    
                    b[row][col] = 3 - player
                    _, ev = minimax(b, depth-1, alpha, beta, True)
                    b[row][col] = 0
                    
                    if ev < min_eval:
                        min_eval = ev
                        best = col
                    
                    beta = min(beta, ev)
                    if beta <= alpha:
                        break
                
                transposition_table[b_hash] = (depth, best, min_eval)
                return best, min_eval
        
        valid_moves = self.get_valid_moves(board)
        if not valid_moves:
            return None
        
        total_pieces = sum(row.count(1) + row.count(2) for row in board)
        
        # Opening book
        if total_pieces == 0:
            choice = random.choice([2, 3, 3, 3, 4])
            logger.info(f"[{self.account_email}] Opening: {choice}")
            return choice
        
        # Check immediate win
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = player
                if check_winner(board, player):
                    board[row][col] = 0
                    logger.info(f"[{self.account_email}] ★★★ WINNING: {col}")
                    return col
                board[row][col] = 0
        
        # Block opponent
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = 3 - player
                if check_winner(board, 3 - player):
                    board[row][col] = 0
                    logger.info(f"[{self.account_email}] ★★ BLOCKING: {col}")
                    return col
                board[row][col] = 0
        
        # Adaptive depth
        depth = 12 if total_pieces < 16 else 14
        
        logger.info(f"[{self.account_email}] Computing depth {depth}...")
        column, score = minimax([row[:] for row in board], depth, float('-inf'), float('inf'), True)
        
        calc_time = time.time() - start_time
        
        if column is None:
            column = valid_moves[0]
        
        logger.info(f"[{self.account_email}] ★ Column {column}, Time: {calc_time:.2f}s, Score: {score:,}")
        return column
    
    def make_move(self, column):
        """Make a move"""
        try:
            cells = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr:first-child td.board-cell")
            if column < len(cells):
                cells[column].click()
                logger.info(f"[{self.account_email}] Played {column}")
                time.sleep(1)
                return True
        except Exception as e:
            logger.error(f"[{self.account_email}] Move error: {e}")
            return False
    
    def check_game_over(self):
        """Check if game is over"""
        try:
            popups = self.driver.find_elements(By.CSS_SELECTOR, "[style*='position: fixed']")
            for popup in popups:
                text = popup.text.lower()
                if any(word in text for word in ['won', 'defeat', 'draw', 'winner']):
                    return True
            
            self.driver.switch_to.default_content()
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='connect4']")
            if not iframes:
                return True
            
            if self.game_iframe:
                self.driver.switch_to.frame(self.game_iframe)
            
            return False
        except:
            return False
    
    def play_game(self):
        """Main game loop"""
        logger.info(f"[{self.account_email}] Starting game")
        move_count = 0
        time.sleep(2)
        
        self.detect_player_number()
        
        while move_count < 42:
            try:
                self.driver.switch_to.default_content()
                self.close_popups()
                
                if self.game_iframe:
                    self.driver.switch_to.frame(self.game_iframe)
                
                if self.check_game_over():
                    logger.info(f"[{self.account_email}] Game finished")
                    break
                
                if self.is_my_turn():
                    board = self.read_board_state()
                    column = self.calculate_best_move(board, self.my_player)
                    
                    if column is not None and self.make_move(column):
                        move_count += 1
                        time.sleep(1.5)
                else:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"[{self.account_email}] Game error: {e}")
                break
        
        logger.info(f"[{self.account_email}] Game completed ({move_count} moves)")
        time.sleep(3)
    
    def handle_post_game(self):
        """Return to dashboard"""
        try:
            logger.info(f"[{self.account_email}] Post-game handling")
            self.driver.switch_to.default_content()
            time.sleep(2)
            
            try:
                back_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Back to Home')]"))
                )
                back_button.click()
            except:
                self.driver.get(self.dashboard_url)
            
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"[{self.account_email}] Post-game error: {e}")
            return False
    
    def quit(self):
        """Close browser and cleanup"""
        try:
            self.driver.quit()
            logger.info(f"[{self.account_email}] Browser closed")
            
            # Cleanup temp directory
            try:
                import shutil
                if hasattr(self, 'user_data_dir') and os.path.exists(self.user_data_dir):
                    shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except:
                pass
        except:
            pass


def load_accounts_config(config_path="accounts.json"):
    """Load accounts from JSON config"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        example_config = {
            "accounts": [
                {
                    "email": "account1@example.com",
                    "password": "password1",
                    "games_per_run": 3,
                    "bet_increase_clicks": 0,
                    "enabled": True
                }
            ],
            "settings": {
                "headless": True,
                "challenge_wait_timeout": 300,
                "wait_between_games": 10,
                "max_parallel_accounts": 5,
                "stagger_start_delay": 2
            }
        }
        with open(config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
        logger.info(f"Created example config: {config_path}")
        return example_config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)


def run_bot_session(account, settings):
    """Run bot session for one account"""
    email = account['email']
    password = account['password']
    games_to_play = account.get('games_per_run', 1)
    
    start_delay = account.get('_start_delay', 0)
    if start_delay > 0:
        logger.info(f"[{email}] Waiting {start_delay}s (stagger delay)")
        time.sleep(start_delay)
    
    logger.info(f"[{email}] ╔════════════════════════════════════════╗")
    logger.info(f"[{email}] Starting session - {games_to_play} games")
    logger.info(f"[{email}] ╚════════════════════════════════════════╝")
    
    bot = None
    try:
        bot = Connect4Bot(
            account_email=email,
            account_password=password,
            headless=settings.get('headless', True)
        )
    except Exception as e:
        logger.error(f"[{email}] Failed to create bot: {e}")
        return {"email": email, "games_played": 0, "games_succeeded": 0, "success": False}
    
    games_played = 0
    games_succeeded = 0
    
    try:
        bot.start()
        
        if not bot.login():
            logger.error(f"[{email}] Login failed")
            return {"email": email, "games_played": 0, "games_succeeded": 0, "success": False}
        
        for game_num in range(1, games_to_play + 1):
            logger.info(f"[{email}] ─── Game {game_num}/{games_to_play} ───")
            
            try:
                if bot.wait_for_challenges(timeout=settings.get('challenge_wait_timeout', 300)):
                    if bot.join_challenge():
                        bot.play_game()
                        bot.handle_post_game()
                        games_played += 1
                        games_succeeded += 1
                        tracker.game_done(True)
                        
                        if game_num < games_to_play:
                            wait_time = settings.get('wait_between_games', 10)
                            logger.info(f"[{email}] Waiting {wait_time}s...")
                            time.sleep(wait_time)
                else:
                    logger.warning(f"[{email}] No challenge for game {game_num}")
                    games_played += 1
                    tracker.game_done(False)
                    time.sleep(10)
            except Exception as e:
                logger.error(f"[{email}] Game {game_num} error: {e}")
                games_played += 1
                tracker.game_done(False)
                continue
        
        tracker.account_done()
        return {
            "email": email,
            "games_played": games_played,
            "games_succeeded": games_succeeded,
            "success": True
        }
    except Exception as e:
        logger.error(f"[{email}] Fatal error: {e}")
        tracker.account_done()
        return {"email": email, "games_played": games_played, "games_succeeded": games_succeeded, "success": False}
    finally:
        if bot:
            bot.quit()


def main():
    """Main execution with parallel processing"""
    logger.info("╔═══════════════════════════════════════════════════════════════╗")
    logger.info("║  Connect 4 Multi-Account PARALLEL Bot - ULTRA-GODMODE AI     ║")
    logger.info(f"║  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
    logger.info("╚═══════════════════════════════════════════════════════════════╝")
    
    config_path = os.getenv('CONFIG_PATH', 'accounts.json')
    config = load_accounts_config(config_path)
    
    accounts = config.get('accounts', [])
    settings = config.get('settings', {})
    
    enabled_accounts = [acc for acc in accounts if acc.get('enabled', True)]
    
    if not enabled_accounts:
        logger.warning("No enabled accounts found")
        return
    
    max_parallel = settings.get('max_parallel_accounts', 5)
    stagger_delay = settings.get('stagger_start_delay', 2)
    
    logger.info(f"Processing {len(enabled_accounts)} accounts with max {max_parallel} parallel")
    logger.info(f"Stagger delay: {stagger_delay}s")
    
    # Add stagger delays
    for i, account in enumerate(enabled_accounts):
        account['_start_delay'] = i * stagger_delay
    
    results = []
    
    # Run in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        future_to_account = {
            executor.submit(run_bot_session, account, settings): account 
            for account in enabled_accounts
        }
        
        for future in concurrent.futures.as_completed(future_to_account):
            account = future_to_account[future]
            try:
                result = future.result()
                results.append(result)
                
                acc_done, games_done, games_succ = tracker.get_stats()
                logger.info(f"╠═══ PROGRESS: {acc_done}/{len(enabled_accounts)} accounts, "
                           f"{games_succ}/{games_done} games succeeded ═══╣")
                
            except Exception as e:
                logger.error(f"[{account['email']}] Thread exception: {e}")
                results.append({
                    "email": account['email'],
                    "games_played": 0,
                    "games_succeeded": 0,
                    "success": False
                })
    
    # Summary
    logger.info("\n╔═══════════════════════════════════════════════════════════════╗")
    logger.info("║                      EXECUTION SUMMARY                        ║")
    logger.info("╠═══════════════════════════════════════════════════════════════╣")
    
    total_games = sum(r['games_played'] for r in results)
    total_succeeded = sum(r.get('games_succeeded', 0) for r in results)
    successful_accounts = sum(1 for r in results if r['success'])
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        logger.info(f"║ {status} {result['email']:<40} "
                   f"{result.get('games_succeeded', 0):>2}/{result['games_played']:<2} games ║")
    
    logger.info("╠═══════════════════════════════════════════════════════════════╣")
    logger.info(f"║ Accounts: {successful_accounts}/{len(enabled_accounts)} successful"
               f"{' ' * (45 - len(str(successful_accounts)) - len(str(len(enabled_accounts))))}║")
    logger.info(f"║ Games:    {total_succeeded}/{total_games} succeeded"
               f"{' ' * (48 - len(str(total_succeeded)) - len(str(total_games)))}║")
    logger.info(f"║ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
               f"{' ' * 37}║")
    logger.info("╚═══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()