#!/home/ubuntu/venvs/bots/bin/python3
"""
Checkers Multi-Account PARALLEL Bot - ULTRA EXPERT AI (FIXED FOR GRID LAYOUT)
Fixed for grid-based board with player1/player2 system
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
        logging.FileHandler(LOG_DIR / f'checkers_parallel_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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


class CheckersUltraExpertBot:
    def __init__(self, account_email, account_password, dashboard_url="https://app.gameonworld.ai/dashboard",
                 bet_increase_clicks=0, headless=True):
        
        # Create unique user data directory
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
        options.add_argument('--remote-debugging-port=0')
        options.add_argument('--disable-web-security')
        
        if headless:
            options.add_argument('--headless=new')
        
        window_width = 1920 + random.randint(-100, 100)
        window_height = 1080 + random.randint(-100, 100)
        options.add_argument(f'--window-size={window_width},{window_height}')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.dashboard_url = dashboard_url
        self.game_iframe = None
        self.bet_increase_clicks = bet_increase_clicks
        self.my_color = None
        self.move_timeout = 15
        self.account_email = account_email
        self.user_data_dir = user_data_dir
        self.transposition_table = {}
        
        # Configurable AI depth - OPTIMIZED FOR SPEED
        self.ai_early_depth = 4      # Reduced from 6 (faster opening)
        self.ai_mid_depth = 5        # Reduced from 8 (faster mid-game)
        self.ai_end_depth = 7        # Reduced from 10 (faster endgame)
        self.max_move_time = 7       # Maximum seconds per move calculation
        
        logger.info(f"[{account_email}] Ultra Expert Checkers AI initialized (GRID LAYOUT)")
        
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
    
    def login(self, email, password):
        """Login to platform"""
        try:
            logger.info(f"[{email}] Logging in...")
            time.sleep(random.uniform(1.0, 3.0))
            
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][placeholder='Email']"))
            )
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password'][placeholder='Password']")
            
            email_input.clear()
            time.sleep(0.3)
            email_input.send_keys(email)
            time.sleep(random.uniform(0.5, 1.0))
            
            password_input.clear()
            time.sleep(0.3)
            password_input.send_keys(password)
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
            
            logger.info(f"[{email}] Login successful ✓")
            return True
        except Exception as e:
            logger.error(f"[{email}] Login error: {e}")
            return False
    
    def create_game(self):
        """Create a new Checkers game"""
        try:
            logger.info(f"[{self.account_email}] Creating game...")
            
            current_url = self.driver.current_url
            if "dashboard" not in current_url:
                self.driver.get(self.dashboard_url)
                time.sleep(3)
            
            self.close_popups()
            time.sleep(2)
            
            self.driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)
            
            checkers_found = False
            strategies = [
                self._find_by_text_content,
                self._find_by_image,
                self._find_by_javascript
            ]
            
            for strategy in strategies:
                try:
                    if strategy():
                        checkers_found = True
                        break
                except:
                    continue
            
            if not checkers_found:
                logger.error(f"[{self.account_email}] Could not find Checkers card")
                return False
            
            time.sleep(2)
            
            play_now_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Now')]"))
            )
            play_now_button.click()
            logger.info(f"[{self.account_email}] Clicked 'Play Now'")
            time.sleep(2)
            
            if self.bet_increase_clicks > 0:
                self._increase_bet()
            
            play_game_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Game')]"))
            )
            play_game_button.click()
            logger.info(f"[{self.account_email}] Game created ✓")
            time.sleep(3)
            
            return True
        except Exception as e:
            logger.error(f"[{self.account_email}] Error creating game: {e}")
            return False
    
    def _find_by_text_content(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-card='true']")
        for card in cards:
            if 'checker' in card.text.lower() and card.is_displayed():
                card.click()
                time.sleep(2)
                return True
        return False
    
    def _find_by_image(self):
        images = self.driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            alt = (img.get_attribute("alt") or "").lower()
            src = (img.get_attribute("src") or "").lower()
            if 'checker' in alt or 'checker' in src:
                if img.is_displayed():
                    try:
                        parent = img.find_element(By.XPATH, "./ancestor::div[@data-card='true']")
                        parent.click()
                        time.sleep(2)
                        return True
                    except:
                        pass
        return False
    
    def _find_by_javascript(self):
        js_script = """
        let elements = Array.from(document.querySelectorAll('*')).filter(el => 
            el.textContent && el.textContent.toLowerCase().includes('checker')
        );
        for (let el of elements) {
            if (el.offsetParent !== null) {
                let clickable = el.closest('[data-card="true"]');
                if (clickable) {
                    clickable.click();
                    return true;
                }
            }
        }
        return false;
        """
        return self.driver.execute_script(js_script)
    
    def _increase_bet(self):
        logger.info(f"[{self.account_email}] Increasing bet ({self.bet_increase_clicks} clicks)")
        for i in range(self.bet_increase_clicks):
            try:
                plus_button = self.driver.find_element(By.XPATH, 
                    "//svg[.//line[@x1='12' and @y1='5']]//ancestor::button")
                if plus_button.is_displayed():
                    plus_button.click()
                    time.sleep(0.3)
            except:
                break
    
    def wait_for_opponent(self, timeout=900):
        """Wait for opponent"""
        logger.info(f"[{self.account_email}] Waiting for opponent (max {timeout}s)")
        start_time = time.time()
        last_iframe_count = 0
        
        while time.time() - start_time < timeout:
            try:
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe")
                
                if len(iframes) != last_iframe_count:
                    logger.info(f"[{self.account_email}] Iframe count changed: {last_iframe_count} -> {len(iframes)}")
                    last_iframe_count = len(iframes)
                
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if src:
                        logger.debug(f"[{self.account_email}] Found iframe: {src[:80]}")
                        
                        if "checker" in src.lower() or "game" in src.lower():
                            logger.info(f"[{self.account_email}] ✓ Opponent joined! (Game iframe detected)")
                            time.sleep(3)
                            return True
                
                # Check for grid structure appearing
                try:
                    grids = self.driver.find_elements(By.CSS_SELECTOR, 
                        "div.grid.grid-cols-8, div[class*='grid-cols-8']")
                    
                    if grids:
                        for grid in grids:
                            squares = grid.find_elements(By.CSS_SELECTOR, 
                                "div[class*='aspect-square']")
                            if len(squares) == 64:
                                logger.info(f"[{self.account_email}] ✓ Opponent joined! (Board detected)")
                                time.sleep(2)
                                return True
                except:
                    pass
                
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0:
                    logger.info(f"[{self.account_email}] Still waiting... {elapsed}s elapsed")
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"[{self.account_email}] Error while waiting: {e}")
                time.sleep(2)
        
        logger.warning(f"[{self.account_email}] ✗ Timeout - no opponent after {timeout}s")
        return False
    
    def switch_to_game_iframe(self):
        """Switch to game iframe"""
        try:
            logger.info(f"[{self.account_email}] Looking for game iframe...")
            time.sleep(1)
            
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe")
            logger.info(f"[{self.account_email}] Found {len(iframes)} total iframes")
            
            for idx, iframe in enumerate(iframes):
                try:
                    src = iframe.get_attribute("src") or ""
                    logger.info(f"[{self.account_email}] Iframe {idx}: {src[:100]}")
                    
                    if "checker" in src.lower():
                        logger.info(f"[{self.account_email}] Found checkers iframe by src")
                        self.driver.switch_to.frame(iframe)
                        self.game_iframe = iframe
                        
                        # Quick wait for grid board
                        logger.info(f"[{self.account_email}] Waiting for grid board (max 10s)...")
                        
                        for wait_attempt in range(5):
                            try:
                                grids = self.driver.find_elements(By.CSS_SELECTOR, 
                                    "div.grid.grid-cols-8, div[class*='grid-cols-8']")
                                
                                if grids:
                                    squares = self.driver.find_elements(By.CSS_SELECTOR, 
                                        "div[class*='aspect-square']")
                                    
                                    if len(squares) == 64:
                                        # Check for pieces
                                        piece_images = self.driver.find_elements(By.CSS_SELECTOR, 
                                            "div[class*='aspect-square'] img")
                                        piece_count = sum(1 for img in piece_images if img.is_displayed())
                                        
                                        if piece_count >= 5:
                                            logger.info(f"[{self.account_email}] ✓ Board ready with {piece_count} pieces")
                                            return True
                                        
                                        logger.debug(f"[{self.account_email}] Found {piece_count} pieces, waiting...")
                                
                                time.sleep(2)
                            except Exception as e:
                                logger.debug(f"[{self.account_email}] Check attempt {wait_attempt+1}: {e}")
                                time.sleep(1)
                        
                        logger.warning(f"[{self.account_email}] Board timeout, proceeding anyway")
                        return True
                        
                except Exception as e:
                    logger.debug(f"[{self.account_email}] Error checking iframe {idx}: {e}")
                    continue
            
            logger.error(f"[{self.account_email}] ✗ Could not find game board")
            return False
            
        except Exception as e:
            logger.error(f"[{self.account_email}] ✗ Error switching to iframe: {e}")
            return False
    
    def read_board_state(self):
        """Read board from grid layout - FIXED PLAYER DETECTION"""
        board = [[None for _ in range(8)] for _ in range(8)]
        
        try:
            # Find grid container
            grid_selectors = [
                "div.grid.grid-cols-8",
                "div[class*='grid-cols-8']",
                "div[class*='board-responsive']"
            ]
            
            grid = None
            for selector in grid_selectors:
                try:
                    grids = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if grids:
                        grid = grids[0]
                        break
                except:
                    continue
            
            if not grid:
                logger.error(f"[{self.account_email}] Could not find grid container")
                return board
            
            # Get all square divs
            squares = []
            for selector in ["div[class*='aspect-square']", "div.w-full.aspect-square", "> div"]:
                try:
                    squares = grid.find_elements(By.CSS_SELECTOR, selector)
                    if len(squares) == 64:
                        break
                except:
                    continue
            
            if len(squares) != 64:
                logger.warning(f"[{self.account_email}] Expected 64 squares, found {len(squares)}")
                if len(squares) < 64:
                    return board
            
            # First pass: Detect piece TYPES (not players yet)
            piece_type_map = {}
            
            for idx in range(min(64, len(squares))):
                row = idx // 8
                col = idx % 8
                square = squares[idx]
                
                try:
                    imgs = square.find_elements(By.TAG_NAME, "img")
                    
                    for img in imgs:
                        if not img.is_displayed():
                            continue
                        
                        alt = (img.get_attribute("alt") or "").lower()
                        src = (img.get_attribute("src") or "").lower()
                        
                        is_king = ("king" in alt or "crown" in alt or "king" in src or 
                                  "double" in alt or "crowned" in src)
                        
                        piece_type = None
                        
                        if "w-rteaz-qe" in src or "/w-" in src or "player1" in alt:
                            piece_type = 'A'
                        elif "b-4dvpsqw3" in src or "/b-" in src or "player2" in alt:
                            piece_type = 'B'
                        
                        if piece_type:
                            board[row][col] = {'type': piece_type, 'isKing': is_king}
                            if piece_type not in piece_type_map:
                                piece_type_map[piece_type] = src
                            break
                
                except Exception as e:
                    logger.debug(f"[{self.account_email}] Error reading square {idx}: {e}")
                    continue
            
            # Second pass: Determine which type corresponds to player1/player2
            bottom_rows_A = sum(1 for r in [5,6,7] for c in range(8) 
                               if board[r][c] and board[r][c]['type'] == 'A')
            bottom_rows_B = sum(1 for r in [5,6,7] for c in range(8) 
                               if board[r][c] and board[r][c]['type'] == 'B')
            
            top_rows_A = sum(1 for r in [0,1,2] for c in range(8) 
                            if board[r][c] and board[r][c]['type'] == 'A')
            top_rows_B = sum(1 for r in [0,1,2] for c in range(8) 
                            if board[r][c] and board[r][c]['type'] == 'B')
            
            logger.debug(f"[{self.account_email}] Position analysis: "
                        f"Bottom(A:{bottom_rows_A}, B:{bottom_rows_B}), "
                        f"Top(A:{top_rows_A}, B:{top_rows_B})")
            
            type_to_player = {}
            
            if bottom_rows_A > bottom_rows_B:
                type_to_player['A'] = 'player1'
                type_to_player['B'] = 'player2'
                logger.info(f"[{self.account_email}] Piece mapping: Type A=player1 (bottom), Type B=player2 (top)")
            else:
                type_to_player['B'] = 'player1'
                type_to_player['A'] = 'player2'
                logger.info(f"[{self.account_email}] Piece mapping: Type B=player1 (bottom), Type A=player2 (top)")
            
            # Third pass: Convert type to actual player
            for row in range(8):
                for col in range(8):
                    if board[row][col]:
                        piece_type = board[row][col]['type']
                        is_king = board[row][col]['isKing']
                        player = type_to_player.get(piece_type, 'player1')
                        board[row][col] = {'player': player, 'isKing': is_king}
            
            # Validation
            piece_count = sum(1 for r in board for c in r if c)
            
            if piece_count > 0:
                p1_count = sum(1 for r in board for c in r if c and c['player'] == 'player1')
                p2_count = sum(1 for r in board for c in r if c and c['player'] == 'player2')
                king_count = sum(1 for r in board for c in r if c and c['isKing'])
                
                logger.debug(f"[{self.account_email}] Final board: {piece_count} pieces "
                           f"(P1: {p1_count}, P2: {p2_count}, Kings: {king_count})")
            else:
                logger.warning(f"[{self.account_email}] ⚠ Empty board detected")
            
            return board
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Error reading board: {e}")
            import traceback
            traceback.print_exc()
            return board

    def detect_my_color(self):
        """Detect which player the bot is - IMPROVED VERSION"""
        if self.my_color is not None:
            return self.my_color
        
        try:
            # Read board first
            board = self.read_board_state()
            
            # Count pieces in starting positions
            # Player1 pieces start in rows 5, 6, 7 (bottom 3 rows)
            # Player2 pieces start in rows 0, 1, 2 (top 3 rows)
            
            bottom_rows_p1 = sum(1 for r in [5,6,7] for c in range(8) 
                               if board[r][c] and board[r][c]['player'] == 'player1')
            bottom_rows_p2 = sum(1 for r in [5,6,7] for c in range(8) 
                               if board[r][c] and board[r][c]['player'] == 'player2')
            
            top_rows_p1 = sum(1 for r in [0,1,2] for c in range(8) 
                            if board[r][c] and board[r][c]['player'] == 'player1')
            top_rows_p2 = sum(1 for r in [0,1,2] for c in range(8) 
                            if board[r][c] and board[r][c]['player'] == 'player2')
            
            logger.info(f"[{self.account_email}] Board analysis: "
                       f"Bottom rows (P1:{bottom_rows_p1}, P2:{bottom_rows_p2}), "
                       f"Top rows (P1:{top_rows_p1}, P2:{top_rows_p2})")
            
            # Strategy 1: Check piece positions (most reliable)
            # If player1 pieces are at bottom, we are player1
            # If player2 pieces are at bottom, we are player2
            if bottom_rows_p1 > bottom_rows_p2:
                self.my_color = 'player1'
                logger.info(f"[{self.account_email}] Detected by board position: PLAYER1 (bottom)")
                return self.my_color
            elif bottom_rows_p2 > bottom_rows_p1:
                self.my_color = 'player2'
                logger.info(f"[{self.account_email}] Detected by board position: PLAYER2 (bottom)")
                return self.my_color
            
            # Strategy 2: Check "Your Turn" text position
            try:
                turn_texts = self.driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'Your Turn') or contains(text(), 'your turn')]")
                
                for text_elem in turn_texts:
                    if text_elem.is_displayed():
                        location = text_elem.location
                        window_height = self.driver.execute_script("return window.innerHeight")
                        
                        # If "Your Turn" is at bottom, check which pieces are there
                        if location['y'] > window_height * 0.5:  # Bottom
                            # We're at bottom - which pieces dominate bottom rows?
                            if bottom_rows_p1 >= bottom_rows_p2:
                                self.my_color = 'player1'
                            else:
                                self.my_color = 'player2'
                        else:  # Top
                            # We're at top - which pieces dominate top rows?
                            if top_rows_p1 >= top_rows_p2:
                                self.my_color = 'player1'
                            else:
                                self.my_color = 'player2'
                        
                        logger.info(f"[{self.account_email}] Detected by turn text: {self.my_color.upper()}")
                        return self.my_color
            except Exception as e:
                logger.debug(f"[{self.account_email}] Turn text check failed: {e}")
            
            # Strategy 3: If it's first turn, player1 ALWAYS goes first
            # Check if board is in starting position (12 pieces each side)
            total_p1 = sum(1 for r in range(8) for c in range(8) 
                          if board[r][c] and board[r][c]['player'] == 'player1')
            total_p2 = sum(1 for r in range(8) for c in range(8) 
                          if board[r][c] and board[r][c]['player'] == 'player2')
            
            if total_p1 == 12 and total_p2 == 12:
                # Starting position - check if it's our turn
                if self.is_my_turn():
                    self.my_color = 'player1'
                    logger.info(f"[{self.account_email}] Starting position + our turn = PLAYER1")
                    return self.my_color
                else:
                    self.my_color = 'player2'
                    logger.info(f"[{self.account_email}] Starting position + waiting = PLAYER2")
                    return self.my_color
            
            # Strategy 4: Default based on bottom row dominance
            if bottom_rows_p1 >= bottom_rows_p2:
                self.my_color = 'player1'
                logger.info(f"[{self.account_email}] Default by bottom dominance: PLAYER1")
            else:
                self.my_color = 'player2'
                logger.info(f"[{self.account_email}] Default by bottom dominance: PLAYER2")
            
            return self.my_color
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Error detecting color: {e}")
            import traceback
            traceback.print_exc()
            self.my_color = 'player1'
            return self.my_color
    
    def is_my_turn(self):
        """Check if it's bot's turn - FIXED VERSION"""
        try:
            # Check for "Your Turn" text
            turn_texts = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'Your Turn') or contains(text(), 'your turn')]")
            
            if any(elem.is_displayed() for elem in turn_texts):
                logger.debug(f"[{self.account_email}] Turn detected: 'Your Turn' text")
                return True
            
            # Check for green timer (active turn indicator)
            green_timers = self.driver.find_elements(By.CSS_SELECTOR, 
                "span[class*='text-green-100'], span.text-green-100")
            
            for timer in green_timers:
                if timer.is_displayed():
                    # Make sure it's on our side (bottom half)
                    location = timer.location
                    window_height = self.driver.execute_script("return window.innerHeight")
                    
                    if location['y'] > window_height * 0.4:
                        logger.debug(f"[{self.account_email}] Turn detected: green bottom timer")
                        return True
            
            # Check for clickable squares
            try:
                grid = self.driver.find_element(By.CSS_SELECTOR, 
                    "div.grid.grid-cols-8, div[class*='grid-cols-8']")
                squares = grid.find_elements(By.CSS_SELECTOR, "div[class*='aspect-square']")
                
                for square in squares[:24]:  # Check bottom 3 rows (player1 starting area)
                    class_attr = square.get_attribute("class") or ""
                    style = square.get_attribute("style") or ""
                    
                    if ("cursor-pointer" in class_attr or "cursor: pointer" in style or
                        "highlight" in class_attr or "select" in class_attr):
                        logger.debug(f"[{self.account_email}] Turn detected: clickable pieces")
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"[{self.account_email}] Error checking turn: {e}")
            return False
    
    def make_move(self, move):
        """Execute move on grid board - FIXED VERSION"""
        try:
            from_r, from_c = move['from']
            from_idx = from_r * 8 + from_c
            
            logger.info(f"[{self.account_email}] Executing move from ({from_r},{from_c}) idx={from_idx}")
            
            # Find grid
            grid = None
            for selector in ["div.grid.grid-cols-8", "div[class*='grid-cols-8']"]:
                try:
                    grids = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if grids:
                        grid = grids[0]
                        break
                except:
                    continue
            
            if not grid:
                logger.error(f"[{self.account_email}] Cannot find grid")
                return False
            
            # Get all squares
            squares = grid.find_elements(By.CSS_SELECTOR, "div[class*='aspect-square']")
            
            if len(squares) < 64:
                logger.error(f"[{self.account_email}] Not enough squares: {len(squares)}")
                return False
            
            # Click source
            if from_idx >= len(squares):
                logger.error(f"[{self.account_email}] Invalid from_idx: {from_idx}")
                return False
            
            source = squares[from_idx]
            
            try:
                # Scroll into view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", 
                    source
                )
                time.sleep(0.3)
                
                # Try clicking
                try:
                    source.click()
                except:
                    # JS click fallback
                    self.driver.execute_script("arguments[0].click();", source)
                
                logger.info(f"[{self.account_email}] ✓ Selected square {from_idx} ({from_r},{from_c})")
                time.sleep(0.6)
                
            except Exception as e:
                logger.error(f"[{self.account_email}] Failed to select source: {e}")
                
                # Try clicking image inside
                try:
                    imgs = source.find_elements(By.TAG_NAME, "img")
                    if imgs:
                        self.driver.execute_script("arguments[0].click();", imgs[0])
                        logger.info(f"[{self.account_email}] ✓ Selected via image")
                        time.sleep(0.6)
                except:
                    return False
            
            # Click destinations
            for step_idx, (to_r, to_c) in enumerate(move['path']):
                to_idx = to_r * 8 + to_c
                
                if to_idx >= len(squares):
                    logger.error(f"[{self.account_email}] Invalid to_idx: {to_idx}")
                    return False
                
                dest = squares[to_idx]
                
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", 
                        dest
                    )
                    time.sleep(0.3)
                    
                    try:
                        dest.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", dest)
                    
                    logger.info(f"[{self.account_email}] ✓ Moved to square {to_idx} ({to_r},{to_c}) "
                              f"[step {step_idx+1}/{len(move['path'])}]")
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"[{self.account_email}] Failed to click destination {to_idx}: {e}")
                    return False
            
            logger.info(f"[{self.account_email}] ★ Move completed successfully ★")
            time.sleep(1)
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_email}] ✗ Critical error making move: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def calculate_best_move_ultra_expert(self, board, player):
        """ULTRA EXPERT AI with deep minimax - FIXED FOR PLAYER1/PLAYER2"""
        start_time = time.time()
        
        def board_hash(b):
            return tuple(tuple(
                (cell['player'], cell['isKing']) if cell else None 
                for cell in row
            ) for row in b)
        
        def get_all_moves(b, p):
            """Get all possible moves"""
            jumps = []
            simple_moves = []
            
            for r in range(8):
                for c in range(8):
                    piece = b[r][c]
                    if piece and piece['player'] == p:
                        jump_sequences = self._find_jump_sequences(b, r, c, p, piece['isKing'])
                        if jump_sequences:
                            jumps.extend(jump_sequences)
                        else:
                            simple = self._get_simple_moves(b, r, c, p, piece['isKing'])
                            simple_moves.extend(simple)
            
            return jumps if jumps else simple_moves
        
        def evaluate_position_ultra(b, p):
            """Ultra advanced evaluation"""
            if not get_all_moves(b, p):
                return -1000000
            
            opp = 'player2' if p == 'player1' else 'player1'
            if not get_all_moves(b, opp):
                return 1000000
            
            score = 0
            my_pieces = 0
            my_kings = 0
            opp_pieces = 0
            opp_kings = 0
            
            for r in range(8):
                for c in range(8):
                    piece = b[r][c]
                    if piece:
                        if piece['player'] == p:
                            my_pieces += 1
                            if piece['isKing']:
                                my_kings += 1
                                score += 3000
                            else:
                                score += 1000
                                # Advancement bonus
                                advancement = r if p == 'player1' else (7 - r)
                                score += advancement * 100
                            
                            # Center control
                            center_dist = abs(3.5 - c)
                            score += (3.5 - center_dist) * 50
                            
                            # Mobility
                            moves = len(self._get_simple_moves(b, r, c, p, piece['isKing']))
                            score += moves * 80
                            
                        else:
                            opp_pieces += 1
                            if piece['isKing']:
                                opp_kings += 1
                                score -= 2800
                            else:
                                score -= 1000
            
            # Material advantage
            piece_diff = my_pieces - opp_pieces
            king_diff = my_kings - opp_kings
            score += piece_diff * 500
            score += king_diff * 1000
            
            # Endgame
            total_pieces = my_pieces + opp_pieces
            if total_pieces <= 8:
                score += king_diff * 2000
            
            return score
        
        def minimax_ultra(b, depth, alpha, beta, maximizing):
            """Ultra deep minimax with alpha-beta"""
            if time.time() - start_time > 14.5:
                return None, evaluate_position_ultra(b, player)
            
            b_hash = board_hash(b)
            if b_hash in self.transposition_table and self.transposition_table[b_hash][0] >= depth:
                return self.transposition_table[b_hash][1], self.transposition_table[b_hash][2]
            
            if depth == 0:
                return None, evaluate_position_ultra(b, player)
            
            current_player = player if maximizing else ('player2' if player == 'player1' else 'player1')
            moves = get_all_moves(b, current_player)
            
            if not moves:
                return None, -1000000 if maximizing else 1000000
            
            # Move ordering
            def move_score(move):
                test_board = self._apply_move(deepcopy(b), move)
                return evaluate_position_ultra(test_board, player)
            
            if maximizing:
                moves.sort(key=move_score, reverse=True)
            else:
                moves.sort(key=move_score)
            
            if maximizing:
                max_eval = float('-inf')
                best_move = moves[0]
                
                for move in moves[:min(15, len(moves))]:
                    new_board = self._apply_move(deepcopy(b), move)
                    _, ev = minimax_ultra(new_board, depth - 1, alpha, beta, False)
                    
                    if ev > max_eval:
                        max_eval = ev
                        best_move = move
                    
                    alpha = max(alpha, ev)
                    if beta <= alpha:
                        break
                
                self.transposition_table[b_hash] = (depth, best_move, max_eval)
                return best_move, max_eval
            else:
                min_eval = float('inf')
                best_move = moves[0]
                
                for move in moves[:min(15, len(moves))]:
                    new_board = self._apply_move(deepcopy(b), move)
                    _, ev = minimax_ultra(new_board, depth - 1, alpha, beta, True)
                    
                    if ev < min_eval:
                        min_eval = ev
                        best_move = move
                    
                    beta = min(beta, ev)
                    if beta <= alpha:
                        break
                
                self.transposition_table[b_hash] = (depth, best_move, min_eval)
                return best_move, min_eval
        
        # Adaptive depth
        total_pieces = sum(1 for r in board for c in r if c)
        
        if total_pieces > 16:
            depth = self.ai_early_depth
        elif total_pieces > 10:
            depth = self.ai_mid_depth
        else:
            depth = self.ai_end_depth
        
        logger.info(f"[{self.account_email}] ULTRA EXPERT depth {depth} (pieces: {total_pieces})...")
        
        move, score = minimax_ultra(deepcopy(board), depth, float('-inf'), float('inf'), True)
        
        calc_time = time.time() - start_time
        logger.info(f"[{self.account_email}] ★ ULTRA EXPERT DEPTH {depth} ★ Time: {calc_time:.2f}s, Score: {score:,}")
        
        return move
    
    def _find_jump_sequences(self, board, r, c, player, is_king):
        """Find all jump sequences - FIXED FOR PLAYER1/PLAYER2"""
        sequences = []
        
        def dfs_jumps(curr_r, curr_c, path, temp_board, captured):
            found_jump = False
            
            if is_king:
                # Kings can jump in all 4 diagonal directions
                directions = [(-2, -2), (-2, 2), (2, -2), (2, 2)]
            elif player == 'player1':
                # Player1 at BOTTOM (rows 5,6,7) jumps UP (decreasing row numbers)
                directions = [(-2, -2), (-2, 2)]  # Jump UP toward row 0
            else:
                # Player2 at TOP (rows 0,1,2) jumps DOWN (increasing row numbers)
                directions = [(2, -2), (2, 2)]  # Jump DOWN toward row 7
            
            for dr, dc in directions:
                new_r, new_c = curr_r + dr, curr_c + dc
                mid_r, mid_c = curr_r + dr // 2, curr_c + dc // 2
                
                if (0 <= new_r < 8 and 0 <= new_c < 8 and
                    temp_board[new_r][new_c] is None and
                    (mid_r, mid_c) not in captured):
                    
                    mid_piece = temp_board[mid_r][mid_c]
                    if mid_piece and mid_piece['player'] != player:
                        found_jump = True
                        new_path = path + [(new_r, new_c)]
                        new_captured = captured | {(mid_r, mid_c)}
                        
                        dfs_jumps(new_r, new_c, new_path, temp_board, new_captured)
            
            if not found_jump and len(path) > 1:
                sequences.append({
                    'from': (r, c),
                    'path': path[1:],
                    'type': 'jump',
                    'captured': captured
                })
        
        dfs_jumps(r, c, [(r, c)], deepcopy(board), set())
        return sequences
    
    def _get_simple_moves(self, board, r, c, player, is_king):
        """Get simple moves - CORRECTED DIRECTIONS"""
        moves = []
        
        if is_king:
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        elif player == 'player1':
            # Player1 at BOTTOM (rows 5,6,7) moves UP (decreasing row numbers)
            directions = [(-1, -1), (-1, 1)]  # Move UP toward row 0
        else:
            # Player2 at TOP (rows 0,1,2) moves DOWN (increasing row numbers)
            directions = [(1, -1), (1, 1)]  # Move DOWN toward row 7
        
        for dr, dc in directions:
            new_r, new_c = r + dr, c + dc
            if (0 <= new_r < 8 and 0 <= new_c < 8 and
                board[new_r][new_c] is None):
                moves.append({
                    'from': (r, c),
                    'path': [(new_r, new_c)],
                    'type': 'simple'
                })
        
        return moves
    
    def _apply_move(self, board, move):
        """Apply move to board - FIXED FOR PLAYER1/PLAYER2"""
        from_r, from_c = move['from']
        piece = board[from_r][from_c]
        board[from_r][from_c] = None
        
        for to_r, to_c in move['path']:
            if move['type'] == 'jump':
                mid_r = (from_r + to_r) // 2
                mid_c = (from_c + to_c) // 2
                board[mid_r][mid_c] = None
            
            from_r, from_c = to_r, to_c
        
        # Check for kinging
        final_r = move['path'][-1][0]
        if piece['player'] == 'player1' and final_r == 7:
            piece = {'player': 'player1', 'isKing': True}
        elif piece['player'] == 'player2' and final_r == 0:
            piece = {'player': 'player2', 'isKing': True}
        
        board[move['path'][-1][0]][move['path'][-1][1]] = piece
        return board
    
    def get_all_moves_for_player(self, board, player):
        """Get all moves for player - FIXED FOR PLAYER1/PLAYER2"""
        jumps = []
        simple_moves = []
        
        for r in range(8):
            for c in range(8):
                piece = board[r][c]
                if piece and piece['player'] == player:
                    jump_sequences = self._find_jump_sequences(board, r, c, player, piece['isKing'])
                    if jump_sequences:
                        jumps.extend(jump_sequences)
                    else:
                        simple = self._get_simple_moves(board, r, c, player, piece['isKing'])
                        simple_moves.extend(simple)
        
        return jumps if jumps else simple_moves
    
    def check_game_over(self):
        """Check if game is over"""
        try:
            result_texts = ['won', 'lost', 'defeat', 'victory', 'draw', 'winner']
            elements = self.driver.find_elements(By.XPATH, "//*")
            
            for elem in elements:
                try:
                    if elem.is_displayed():
                        text = elem.text.lower()
                        if any(word in text for word in result_texts):
                            return True
                except:
                    pass
            
            self.driver.switch_to.default_content()
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe")
            has_game = any("checker" in (i.get_attribute("src") or "").lower() for i in iframes)
            
            if not has_game:
                return True
            
            if self.game_iframe:
                self.driver.switch_to.frame(self.game_iframe)
            
            return False
        except:
            return False
    
    def play_game(self):
        """Main game loop - FIXED VERSION"""
        logger.info(f"[{self.account_email}] Starting game")
        move_count = 0
        max_moves = 200
        no_turn_count = 0
        consecutive_failed_moves = 0
        iframe_switch_failures = 0
        time.sleep(2)
        
        self.detect_my_color()
        
        while move_count < max_moves:
            try:
                # Switch to default
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
                
                self.close_popups()
                
                # Switch to game iframe
                if self.game_iframe:
                    try:
                        self.driver.switch_to.frame(self.game_iframe)
                        iframe_switch_failures = 0
                    except Exception as e:
                        logger.warning(f"[{self.account_email}] Failed to switch to saved iframe: {e}")
                        iframe_switch_failures += 1
                        
                        if iframe_switch_failures <= 3:
                            logger.info(f"[{self.account_email}] Attempting to re-locate iframe...")
                            if not self.switch_to_game_iframe():
                                if iframe_switch_failures >= 3:
                                    logger.error(f"[{self.account_email}] Cannot find iframe after 3 attempts")
                                    break
                                time.sleep(2)
                                continue
                        else:
                            logger.error(f"[{self.account_email}] Too many iframe switch failures")
                            break
                else:
                    logger.info(f"[{self.account_email}] No saved iframe, searching...")
                    if not self.switch_to_game_iframe():
                        logger.error(f"[{self.account_email}] Could not locate game iframe")
                        break
                
                # Check game over
                if self.check_game_over():
                    logger.info(f"[{self.account_email}] Game finished")
                    break
                
                # Read board
                board = self.read_board_state()
                piece_count = sum(1 for r in board for c in r if c)
                
                if piece_count == 0:
                    logger.warning(f"[{self.account_email}] Empty board, quick retry...")
                    
                    for retry in range(3):
                        time.sleep(2)
                        board = self.read_board_state()
                        piece_count = sum(1 for r in board for c in r if c)
                        
                        if piece_count > 0:
                            logger.info(f"[{self.account_email}] ✓ Board loaded with {piece_count} pieces")
                            break
                    
                    if piece_count == 0:
                        logger.warning(f"[{self.account_email}] Board still empty after retries")
                        continue
                
                # Check turn
                is_my_turn = self.is_my_turn()
                
                if is_my_turn:
                    no_turn_count = 0
                    logger.info(f"[{self.account_email}] ══════ Move {move_count + 1} ({self.my_color.upper()}) ══════")
                    
                    # Get moves
                    all_moves = self.get_all_moves_for_player(board, self.my_color)
                    
                    if not all_moves:
                        logger.warning(f"[{self.account_email}] No valid moves available!")
                        time.sleep(1)
                        board = self.read_board_state()
                        all_moves = self.get_all_moves_for_player(board, self.my_color)
                        
                        if not all_moves:
                            logger.error(f"[{self.account_email}] Still no moves - game may be over")
                            time.sleep(3)
                            break
                    
                    logger.info(f"[{self.account_email}] Found {len(all_moves)} possible moves")
                    
                    # Calculate best move
                    move = self.calculate_best_move_ultra_expert(board, self.my_color)
                    
                    if move:
                        logger.info(f"[{self.account_email}] Selected: {move['from']} -> {move['path']} "
                                  f"(type: {move['type']})")
                        
                        if self.make_move(move):
                            move_count += 1
                            consecutive_failed_moves = 0
                            logger.info(f"[{self.account_email}] ★ Move {move_count} completed ★")
                            time.sleep(2)
                        else:
                            consecutive_failed_moves += 1
                            logger.error(f"[{self.account_email}] ✗ Failed to execute move "
                                       f"(failures: {consecutive_failed_moves})")
                            
                            if consecutive_failed_moves >= 3:
                                logger.error(f"[{self.account_email}] Too many failures, breaking")
                                break
                            
                            time.sleep(2)
                    else:
                        logger.error(f"[{self.account_email}] AI returned no move")
                        consecutive_failed_moves += 1
                        
                        if consecutive_failed_moves >= 3:
                            break
                        
                        time.sleep(2)
                else:
                    no_turn_count += 1
                    if no_turn_count % 5 == 0:
                        logger.info(f"[{self.account_email}] Waiting for turn... ({no_turn_count}s)")
                    time.sleep(1)
                
                if no_turn_count > 60:
                    logger.warning(f"[{self.account_email}] Waited 60s, checking game status")
                    if self.check_game_over():
                        break
                    no_turn_count = 0
                
            except StaleElementReferenceException:
                logger.warning(f"[{self.account_email}] Stale element, refreshing...")
                self.game_iframe = None
                time.sleep(2)
                continue
            except Exception as e:
                logger.error(f"[{self.account_email}] Error in game loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(2)
                
                try:
                    self.driver.switch_to.default_content()
                    if not self.switch_to_game_iframe():
                        logger.error(f"[{self.account_email}] Cannot recover")
                        break
                except:
                    break
        
        logger.info(f"[{self.account_email}] Game completed after {move_count} moves")
        time.sleep(3)
    
    def handle_post_game(self):
        """Return to dashboard"""
        try:
            logger.info(f"[{self.account_email}] Handling post-game")
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
            logger.error(f"[{self.account_email}] Error in post-game: {e}")
            return False
    
    def quit(self):
        """Close browser"""
        try:
            self.driver.quit()
            logger.info(f"[{self.account_email}] Browser closed")
            
            try:
                import shutil
                if hasattr(self, 'user_data_dir') and os.path.exists(self.user_data_dir):
                    shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except:
                pass
        except:
            pass


def load_accounts_config(config_path="accounts.json"):
    """Load Checkers accounts from unified JSON config"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Extract Checkers-specific accounts from unified config
        checkers_accounts = []
        
        for account in config.get('accounts', []):
            # Skip disabled accounts
            if not account.get('enabled', True):
                continue
            
            # Check if Checkers is enabled for this account
            game_config = account.get('games', {}).get('checkers', {})
            
            if not game_config.get('enabled', False):
                continue
            
            # Create Checkers account entry with game-specific settings
            checkers_account = {
                'email': account['email'],
                'password': account['password'],
                'games_per_run': game_config.get('games_per_run', 1),
                'bet_increase_clicks': game_config.get('bet_increase_clicks', 0),
                'enabled': True
            }
            checkers_accounts.append(checkers_account)
        
        # Build Checkers config with extracted accounts
        settings = config.get('settings', {})
        checkers_settings = settings.get('checkers', {})
        
        checkers_config = {
            'accounts': checkers_accounts,
            'settings': {
                'headless': settings.get('headless', True),
                'opponent_wait_timeout': settings.get('opponent_wait_timeout', 900),
                'wait_between_games': settings.get('wait_between_games', 10),
                'max_parallel_accounts': settings.get('max_parallel_accounts', 3),
                'stagger_start_delay': settings.get('stagger_start_delay', 5),
                'ai_settings': {
                    'early_game_depth': checkers_settings.get('early_game_depth', 4),
                    'mid_game_depth': checkers_settings.get('mid_game_depth', 5),
                    'end_game_depth': checkers_settings.get('end_game_depth', 7),
                    'max_time_per_move': checkers_settings.get('max_time_per_move', 7)
                }
            }
        }
        
        logger.info(f"Loaded {len(checkers_accounts)} Checkers-enabled accounts from unified config")
        return checkers_config
        
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        logger.error("Please create accounts.json with unified configuration")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)

def run_bot_session(account, settings):
    """Run bot session for one account"""
    email = account['email']
    password = account['password']
    games_to_play = account.get('games_per_run', 1)
    bet_clicks = account.get('bet_increase_clicks', 0)
    
    ai_settings = settings.get('ai_settings', {})
    early_depth = ai_settings.get('early_game_depth', 6)
    mid_depth = ai_settings.get('mid_game_depth', 8)
    end_depth = ai_settings.get('end_game_depth', 10)
    max_time = ai_settings.get('max_time_per_move', 15)
    
    logger.info(f"[{email}] AI Config: Early={early_depth}, Mid={mid_depth}, End={end_depth}, MaxTime={max_time}s")
    
    start_delay = account.get('_start_delay', 0)
    if start_delay > 0:
        logger.info(f"[{email}] Waiting {start_delay}s before starting")
        time.sleep(start_delay)
    
    logger.info(f"[{email}] ╔══════════════════════════════════════╗")
    logger.info(f"[{email}] Starting session - {games_to_play} games")
    logger.info(f"[{email}] ╚══════════════════════════════════════╝")
    
    bot = None
    try:
        bot = CheckersUltraExpertBot(
            account_email=email,
            account_password=password,
            bet_increase_clicks=bet_clicks,
            headless=settings.get('headless', True)
        )
        
        bot.ai_early_depth = early_depth
        bot.ai_mid_depth = mid_depth
        bot.ai_end_depth = end_depth
        bot.move_timeout = max_time
        
    except Exception as e:
        logger.error(f"[{email}] Failed to create bot: {e}")
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
                            bot.play_game()
                            bot.handle_post_game()
                            games_played += 1
                            games_succeeded += 1
                            tracker.game_done(True)
                            
                            if game_num < games_to_play:
                                wait_time = settings.get('wait_between_games', 10)
                                logger.info(f"[{email}] Waiting {wait_time}s before next game")
                                time.sleep(wait_time)
                    else:
                        logger.warning(f"[{email}] No opponent for game {game_num}")
                        games_played += 1
                        tracker.game_done(False)
                        bot.driver.get(bot.dashboard_url)
                        time.sleep(3)
                else:
                    logger.error(f"[{email}] Failed to create game {game_num}")
                    tracker.game_done(False)
                    time.sleep(10)
            except Exception as e:
                logger.error(f"[{email}] Error in game {game_num}: {e}")
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
    logger.info("╔══════════════════════════════════════════════════════════════════╗")
    logger.info("║  Checkers Multi-Account PARALLEL Bot - ULTRA EXPERT AI (FIXED)  ║")
    logger.info(f"║  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                 ║")
    logger.info("╚══════════════════════════════════════════════════════════════════╝")
    
    config_path = os.getenv('CONFIG_PATH', 'accounts.json')
    config = load_accounts_config(config_path)
    
    accounts = config.get('accounts', [])
    settings = config.get('settings', {})
    
    enabled_accounts = [acc for acc in accounts if acc.get('enabled', True)]
    
    if not enabled_accounts:
        logger.warning("No enabled accounts")
        return
    
    max_parallel = settings.get('max_parallel_accounts', 5)
    stagger_delay = settings.get('stagger_start_delay', 2)
    
    logger.info(f"Processing {len(enabled_accounts)} accounts with max {max_parallel} parallel")
    logger.info(f"Stagger delay: {stagger_delay}s between account starts")
    
    for i, account in enumerate(enabled_accounts):
        account['_start_delay'] = i * stagger_delay
    
    results = []
    
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
    logger.info("\n╔══════════════════════════════════════════════════════════════════╗")
    logger.info("║                      EXECUTION SUMMARY                           ║")
    logger.info("╠══════════════════════════════════════════════════════════════════╣")
    
    total_games = sum(r['games_played'] for r in results)
    total_succeeded = sum(r.get('games_succeeded', 0) for r in results)
    successful_accounts = sum(1 for r in results if r['success'])
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        logger.info(f"║ {status} {result['email']:<40} "
                   f"{result.get('games_succeeded', 0):>2}/{result['games_played']:<2} games ║")
    
    logger.info("╠══════════════════════════════════════════════════════════════════╣")
    logger.info(f"║ Accounts: {successful_accounts}/{len(enabled_accounts)} successful"
               f"{' ' * (45 - len(str(successful_accounts)) - len(str(len(enabled_accounts))))}║")
    logger.info(f"║ Games:    {total_succeeded}/{total_games} succeeded"
               f"{' ' * (48 - len(str(total_succeeded)) - len(str(total_games)))}║")
    logger.info(f"║ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
               f"{' ' * 37}║")
    logger.info("╚══════════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
