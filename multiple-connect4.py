#!/home/ubuntu/venvs/bots/bin/python3
"""
Connect 4 Multi-Account PARALLEL Bot
ULTRA-GODMODE AI with Opponent Prediction & Multi-Move Analysis
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import threading
from queue import Queue
import concurrent.futures

# Configure logging
LOG_DIR = Path("/home/ubuntu/bots/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'bot_ultra_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Thread-safe counter for tracking progress
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


class Connect4HostBot:
    def __init__(self, account_email, account_password, dashboard_url="https://app.gameonworld.ai/dashboard", 
                 difficulty="ultra_expert", bet_increase_clicks=0, headless=True):
        
        # Create unique user data directory for this account to prevent conflicts
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
        
        # CRITICAL: Each instance gets its own profile to prevent conflicts
        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-dev-shm-usage')
        
        # Additional isolation
        options.add_argument('--remote-debugging-port=0')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        
        if headless:
            options.add_argument('--headless=new')
        
        # Add random window size for better isolation
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
        self.user_data_dir = user_data_dir
        logger.info(f"[{account_email}] Bot initialized - ULTRA-GODMODE AI with Opponent Prediction")
        
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
            try:
                screenshot_path = f"/home/ubuntu/bots/logs/login_error_{email.split('@')[0]}_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"[{email}] Screenshot saved to {screenshot_path}")
            except:
                pass
            return False
    
    def create_game(self):
        """Create a new Connect 4 game"""
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
            
            connect4_found = False
            strategies = [
                self._find_by_card_structure,
                self._find_by_image_alt,
                self._find_by_heading,
                self._find_by_image_src,
                self._find_by_javascript
            ]
            
            for strategy in strategies:
                try:
                    if strategy():
                        connect4_found = True
                        break
                except:
                    continue
            
            if not connect4_found:
                logger.error(f"[{self.account_email}] Could not find Connect 4 card")
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
    
    def _find_by_card_structure(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-card='true']")
        for card in cards:
            if 'connect 4' in card.text.lower() and card.is_displayed():
                card.click()
                time.sleep(2)
                return True
        return False
    
    def _find_by_image_alt(self):
        images = self.driver.find_elements(By.XPATH, "//img[@alt='Connect 4']")
        for img in images:
            if img.is_displayed():
                parent = img.find_element(By.XPATH, "./ancestor::div[@data-card='true']")
                parent.click()
                time.sleep(2)
                return True
        return False
    
    def _find_by_heading(self):
        headings = self.driver.find_elements(By.XPATH, "//h4[contains(text(), 'Connect 4')]")
        for heading in headings:
            if heading.is_displayed():
                card = heading.find_element(By.XPATH, "./ancestor::div[@data-card='true']")
                card.click()
                time.sleep(2)
                return True
        return False
    
    def _find_by_image_src(self):
        images = self.driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            src = img.get_attribute("src") or ""
            if 'c1.jpg' in src.lower() and img.is_displayed():
                parent = img.find_element(By.XPATH, "./ancestor::div[@data-card='true']")
                parent.click()
                time.sleep(2)
                return True
        return False
    
    def _find_by_javascript(self):
        js_script = """
        let elements = Array.from(document.querySelectorAll('*')).filter(el => 
            (el.textContent && el.textContent.includes('Connect 4')) ||
            (el.alt && el.alt.includes('Connect 4'))
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
        
        while time.time() - start_time < timeout:
            try:
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='connect4']")
                if iframes:
                    logger.info(f"[{self.account_email}] Opponent joined! ✓")
                    time.sleep(2)
                    return True
                
                elapsed = int(time.time() - start_time)
                if elapsed % 60 == 0:
                    logger.info(f"[{self.account_email}] Still waiting... {elapsed}s elapsed")
                
                time.sleep(2)
            except Exception as e:
                logger.error(f"[{self.account_email}] Error while waiting: {e}")
                time.sleep(2)
        
        logger.warning(f"[{self.account_email}] Timeout - no opponent after {timeout}s")
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
            logger.info(f"[{self.account_email}] Switched to game iframe")
            return True
        except:
            logger.error(f"[{self.account_email}] Could not switch to game iframe")
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
                    logger.info(f"[{self.account_email}] Detected: Player {self.my_player}")
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
        """
        ULTRA-GODMODE AI - Advanced algorithm with opponent prediction
        - Predicts opponent's next 3 moves
        - Multi-path analysis
        - Pattern recognition
        - Time-optimized to stay within 10s limit
        """
        start_time = time.time()
        
        # Transposition table with depth tracking
        transposition_table = {}
        
        # Opponent prediction cache
        opponent_predictions = {}
        
        def board_hash(b):
            """Create unique hash for board state"""
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
        
        def count_threats(b, p, window_size=4):
            """Advanced threat counting with pattern recognition"""
            threats = {'4': 0, '3': 0, '2': 0, '1': 0}
            threat_positions = []
            
            # Check all directions
            directions = [
                (0, 1),   # Horizontal
                (1, 0),   # Vertical
                (1, 1),   # Diagonal /
                (1, -1)   # Diagonal \
            ]
            
            for r in range(6):
                for c in range(7):
                    for dr, dc in directions:
                        window = []
                        positions = []
                        for i in range(window_size):
                            nr, nc = r + dr * i, c + dc * i
                            if 0 <= nr < 6 and 0 <= nc < 7:
                                window.append(b[nr][nc])
                                positions.append((nr, nc))
                        
                        if len(window) == window_size:
                            p_count = window.count(p)
                            opp_count = window.count(3 - p)
                            empty_count = window.count(0)
                            
                            # Only count if no opponent pieces
                            if opp_count == 0 and p_count > 0:
                                threats[str(p_count)] += 1
                                if p_count >= 2:
                                    threat_positions.append({
                                        'count': p_count,
                                        'positions': positions,
                                        'empty': empty_count
                                    })
            
            return threats, threat_positions
        
        def predict_opponent_moves(b, opp, depth=3):
            """
            Predict opponent's most likely next 3 moves
            Returns list of (column, probability, threat_level) tuples
            """
            b_hash = board_hash(b)
            if b_hash in opponent_predictions:
                return opponent_predictions[b_hash]
            
            valid = self.get_valid_moves(b)
            if not valid:
                return []
            
            move_scores = []
            
            for col in valid:
                row = get_next_row(b, col)
                if row is None:
                    continue
                
                score = 0
                
                # Simulate move
                b[row][col] = opp
                
                # Check if winning move
                if check_winner(b, opp):
                    score += 1000000
                
                # Count threats created
                threats, positions = count_threats(b, opp)
                score += int(threats['3']) * 10000
                score += int(threats['2']) * 1000
                score += int(threats['1']) * 100
                
                # Check if blocks our winning move
                b[row][col] = player
                if check_winner(b, player):
                    score += 500000
                
                # Center preference
                score += (3 - abs(3 - col)) * 500
                
                # Connectivity bonus
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < 6 and 0 <= nc < 7 and b[nr][nc] == opp:
                        score += 2000
                
                b[row][col] = 0
                move_scores.append((col, score))
            
            # Sort and normalize to probabilities
            move_scores.sort(key=lambda x: x[1], reverse=True)
            total_score = sum(s for _, s in move_scores)
            
            if total_score == 0:
                predictions = [(col, 1.0/len(move_scores), 0) for col, _ in move_scores]
            else:
                predictions = [
                    (col, score / total_score, score) 
                    for col, score in move_scores
                ]
            
            # Cache top 3 predictions
            opponent_predictions[b_hash] = predictions[:3]
            return predictions[:3]
        
        def analyze_multi_move_sequence(b, p, my_move, depth=3):
            """
            Analyze move sequences considering opponent responses
            Returns expected value considering opponent's best replies
            """
            if depth == 0 or time.time() - start_time > 8.5:
                return evaluate_position_advanced(b, p)
            
            row = get_next_row(b, my_move)
            if row is None:
                return -999999
            
            # Make our move
            b[row][my_move] = p
            
            # Check immediate win
            if check_winner(b, p):
                b[row][my_move] = 0
                return 10000000 + depth * 100000
            
            # Predict opponent responses
            opp_predictions = predict_opponent_moves(b, 3 - p)
            
            expected_value = 0
            total_probability = 0
            
            for opp_col, probability, threat in opp_predictions:
                opp_row = get_next_row(b, opp_col)
                if opp_row is None:
                    continue
                
                # Simulate opponent move
                b[opp_row][opp_col] = 3 - p
                
                # Check opponent win
                if check_winner(b, 3 - p):
                    b[opp_row][opp_col] = 0
                    b[row][my_move] = 0
                    return -10000000 - depth * 100000
                
                # Evaluate resulting position
                pos_value = evaluate_position_advanced(b, p)
                expected_value += probability * pos_value
                total_probability += probability
                
                b[opp_row][opp_col] = 0
            
            b[row][my_move] = 0
            
            return expected_value / max(total_probability, 0.001)
        
        def evaluate_position_advanced(b, p):
            """Enhanced evaluation with pattern recognition"""
            if check_winner(b, p):
                return 10000000
            if check_winner(b, 3-p):
                return -10000000
            
            score = 0
            opp = 3 - p
            
            # Threat analysis
            our_threats, our_positions = count_threats(b, p)
            opp_threats, opp_positions = count_threats(b, opp)
            
            score += int(our_threats['3']) * 100000
            score -= int(opp_threats['3']) * 150000
            score += int(our_threats['2']) * 10000
            score -= int(opp_threats['2']) * 12000
            score += int(our_threats['1']) * 1000
            score -= int(opp_threats['1']) * 1200
            
            # Pattern recognition - recognize common winning patterns
            for threat_info in our_positions:
                if threat_info['count'] == 3 and threat_info['empty'] == 1:
                    # One move away from winning
                    score += 200000
                elif threat_info['count'] == 2 and threat_info['empty'] == 2:
                    # Two empty spaces for flexible attacks
                    score += 15000
            
            for threat_info in opp_positions:
                if threat_info['count'] == 3 and threat_info['empty'] == 1:
                    score -= 250000
                elif threat_info['count'] == 2 and threat_info['empty'] == 2:
                    score -= 18000
            
            # Center control with weight
            center_weights = {0: 10, 1: 30, 2: 50, 3: 70, 4: 50, 5: 30, 6: 10}
            for col in range(7):
                for row in range(6):
                    if b[row][col] == p:
                        score += (6 - row) * center_weights[col]
                    elif b[row][col] == opp:
                        score -= (6 - row) * center_weights[col] * 0.8
            
            # Connectivity bonus
            for r in range(6):
                for c in range(7):
                    if b[r][c] == p:
                        for dr, dc in [(0,1), (1,0), (1,1), (1,-1)]:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < 6 and 0 <= nc < 7 and b[nr][nc] == p:
                                score += 400
            
            return score
        
        def minimax_ultra(b, depth, alpha, beta, maximizing):
            """Ultra-optimized minimax with aggressive pruning"""
            # Time check - 9s hard limit
            if time.time() - start_time > 9.0:
                return None, evaluate_position_advanced(b, player)
            
            # Transposition table lookup
            b_hash = board_hash(b)
            if b_hash in transposition_table and transposition_table[b_hash][0] >= depth:
                return transposition_table[b_hash][1], transposition_table[b_hash][2]
            
            if depth == 0:
                return None, evaluate_position_advanced(b, player)
            
            # Terminal states
            if check_winner(b, player):
                return None, 10000000 + depth * 10000
            if check_winner(b, 3-player):
                return None, -10000000 - depth * 10000
            
            valid = self.get_valid_moves(b)
            if not valid:
                return None, 0
            
            # Ultra-aggressive move ordering
            def ultra_order_score(col):
                row = get_next_row(b, col)
                if row is None:
                    return float('inf')
                
                score = 0
                current_player = player if maximizing else (3-player)
                
                b[row][col] = current_player
                
                # Immediate win/loss detection
                if check_winner(b, current_player):
                    b[row][col] = 0
                    return -100000000
                
                # Threat analysis
                threats, _ = count_threats(b, current_player)
                score -= int(threats['3']) * 1000000
                score -= int(threats['2']) * 50000
                
                # Consider opponent predictions
                if not maximizing:
                    opp_pred = predict_opponent_moves(b, current_player, depth=1)
                    if opp_pred:
                        score -= opp_pred[0][2] * 10000
                
                # Center preference
                score -= abs(3 - col) * 5000
                
                b[row][col] = 0
                return score
            
            # Order moves
            move_scores = [(col, ultra_order_score(col)) for col in valid]
            move_scores.sort(key=lambda x: x[1])
            ordered_moves = [col for col, _ in move_scores]
            
            if maximizing:
                max_eval = float('-inf')
                best = ordered_moves[0]
                
                for col in ordered_moves:
                    row = get_next_row(b, col)
                    if row is None:
                        continue
                    
                    b[row][col] = player
                    _, ev = minimax_ultra(b, depth-1, alpha, beta, False)
                    b[row][col] = 0
                    
                    if ev > max_eval:
                        max_eval = ev
                        best = col
                    
                    alpha = max(alpha, ev)
                    if beta <= alpha:
                        break  # Beta cutoff
                
                transposition_table[b_hash] = (depth, best, max_eval)
                return best, max_eval
            else:
                min_eval = float('inf')
                best = ordered_moves[0]
                
                for col in ordered_moves:
                    row = get_next_row(b, col)
                    if row is None:
                        continue
                    
                    b[row][col] = 3 - player
                    _, ev = minimax_ultra(b, depth-1, alpha, beta, True)
                    b[row][col] = 0
                    
                    if ev < min_eval:
                        min_eval = ev
                        best = col
                    
                    beta = min(beta, ev)
                    if beta <= alpha:
                        break  # Alpha cutoff
                
                transposition_table[b_hash] = (depth, best, min_eval)
                return best, min_eval
        
        # ===== MAIN ALGORITHM =====
        
        valid_moves = self.get_valid_moves(board)
        if not valid_moves:
            return None
        
        total_pieces = sum(row.count(1) + row.count(2) for row in board)
        
        # Opening book (first 2 moves)
        if total_pieces == 0:
            opening_weights = {1: 5, 2: 15, 3: 35, 4: 15, 5: 5}
            choice = random.choices(list(opening_weights.keys()), 
                                   weights=list(opening_weights.values()))[0]
            logger.info(f"[{self.account_email}] Opening: Column {choice}")
            return choice
        
        if total_pieces == 1:
            opp_col = None
            for c in range(7):
                if board[5][c] != 0:
                    opp_col = c
                    break
            
            if opp_col == 3:
                choice = random.choice([2, 2, 2, 4, 4, 4])
            elif opp_col in [2, 4]:
                choice = random.choice([3, 3, 3, opp_col])
            else:
                choice = 3
            
            logger.info(f"[{self.account_email}] Counter-opening: Column {choice}")
            return choice
        
        # Immediate win check
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = player
                if check_winner(board, player):
                    board[row][col] = 0
                    logger.info(f"[{self.account_email}] ★★★ WINNING ★★★: Column {col}")
                    return col
                board[row][col] = 0
        
        # Block opponent win
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = 3 - player
                if check_winner(board, 3 - player):
                    board[row][col] = 0
                    logger.info(f"[{self.account_email}] ★★ BLOCKING ★★: Column {col}")
                    return col
                board[row][col] = 0
        
        # === TACTICAL ANALYSIS (only after sufficient pieces are on board) ===
        # Early game: focus on positioning, not tactics
        # Mid-late game: tactical opportunities become critical
        
        use_advanced_tactics = total_pieces >= 10  # Only use tactics after 10+ pieces
        
        if use_advanced_tactics:
            # Check for double threat opportunities (creates 2+ winning threats in one move)
            logger.info(f"[{self.account_email}] Scanning for double threats...")
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None:
                    board[row][col] = player
                    
                    # Count how many winning threats this move creates
                    threats_created = 0
                    winning_positions = []
                    
                    # Check all possible next moves for wins
                    for next_col in range(7):
                        next_row = get_next_row(board, next_col)
                        if next_row is not None:
                            board[next_row][next_col] = player
                            if check_winner(board, player):
                                threats_created += 1
                                winning_positions.append(next_col)
                            board[next_row][next_col] = 0
                    
                    board[row][col] = 0
                    
                    # If we create 2+ winning threats, opponent can't block both!
                    if threats_created >= 2:
                        logger.info(f"[{self.account_email}] ★★★ DOUBLE THREAT SETUP ★★★: Column {col} creates {threats_created} winning threats at {winning_positions}")
                        return col
            
            # Check if opponent can create double threat (and block it)
            logger.info(f"[{self.account_email}] Checking opponent double threats...")
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None:
                    board[row][col] = 3 - player
                    
                    # Count opponent's threats after this move
                    opp_threats = 0
                    for next_col in range(7):
                        next_row = get_next_row(board, next_col)
                        if next_row is not None:
                            board[next_row][next_col] = 3 - player
                            if check_winner(board, 3 - player):
                                opp_threats += 1
                            board[next_row][next_col] = 0
                    
                    board[row][col] = 0
                    
                    # Block opponent's double threat setup
                    if opp_threats >= 2:
                        logger.info(f"[{self.account_email}] ★★ BLOCKING OPPONENT DOUBLE THREAT ★★: Column {col}")
                        return col
        
        # Fork detection - only in mid-late game (16+ pieces)
        if total_pieces >= 16:
            # Check for fork opportunities (creating multiple 3-in-a-row threats)
            logger.info(f"[{self.account_email}] Scanning for fork opportunities...")
            def count_three_in_row_threats(b, p):
                """Count positions where player has 3-in-a-row with 1 empty (immediate winning threats)"""
                threat_count = 0
                threat_positions = set()
                
                # Horizontal
                for r in range(6):
                    for c in range(4):
                        window = [b[r][c+i] for i in range(4)]
                        if window.count(p) == 3 and window.count(0) == 1:
                            empty_idx = c + window.index(0)
                            # Check if this empty position is playable (has support below)
                            if r == 5 or b[r+1][empty_idx] != 0:
                                threat_positions.add((r, empty_idx))
                
                # Vertical
                for c in range(7):
                    for r in range(3):
                        window = [b[r+i][c] for i in range(4)]
                        if window.count(p) == 3 and window.count(0) == 1:
                            empty_idx = r + window.index(0)
                            if empty_idx == 5 or b[empty_idx+1][c] != 0:
                                threat_positions.add((empty_idx, c))
                
                # Diagonal /
                for r in range(3):
                    for c in range(4):
                        window = [b[r+i][c+i] for i in range(4)]
                        if window.count(p) == 3 and window.count(0) == 1:
                            empty_idx = window.index(0)
                            empty_r, empty_c = r + empty_idx, c + empty_idx
                            if empty_r == 5 or b[empty_r+1][empty_c] != 0:
                                threat_positions.add((empty_r, empty_c))
                
                # Diagonal \
                for r in range(3, 6):
                    for c in range(4):
                        window = [b[r-i][c+i] for i in range(4)]
                        if window.count(p) == 3 and window.count(0) == 1:
                            empty_idx = window.index(0)
                            empty_r, empty_c = r - empty_idx, c + empty_idx
                            if empty_r == 5 or b[empty_r+1][empty_c] != 0:
                                threat_positions.add((empty_r, empty_c))
                
                return len(threat_positions), threat_positions
            
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None:
                    board[row][col] = player
                    threat_count, positions = count_three_in_row_threats(board, player)
                    board[row][col] = 0
                    
                    # Fork = creating 2+ immediate winning threats
                    if threat_count >= 2:
                        logger.info(f"[{self.account_email}] ★★★ FORK OPPORTUNITY ★★★: Column {col} creates {threat_count} winning threats")
                        return col
            
            # Block opponent forks
            logger.info(f"[{self.account_email}] Checking opponent fork threats...")
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None:
                    board[row][col] = 3 - player
                    threat_count, positions = count_three_in_row_threats(board, 3 - player)
                    board[row][col] = 0
                    
                    if threat_count >= 2:
                        logger.info(f"[{self.account_email}] ★★ BLOCKING OPPONENT FORK ★★: Column {col}")
                        return col
        
        # Vertical threat analysis - always important but validate carefully
        if total_pieces >= 8:  # Only after some pieces are placed
            logger.info(f"[{self.account_email}] Analyzing vertical threats...")
            
            # Advanced: Avoid giving opponent vertical wins
            dangerous_moves = []
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None and row > 0:  # Must have space above
                    # Check if opponent has pieces below
                    opp_pieces_below = 0
                    for check_row in range(row + 1, 6):
                        if board[check_row][col] == 3 - player:
                            opp_pieces_below += 1
                    
                    # If opponent has 2+ pieces below, this is dangerous
                    if opp_pieces_below >= 2:
                        # Simulate: if we play here, opponent plays above us
                        board[row][col] = player
                        board[row-1][col] = 3 - player
                        if check_winner(board, 3 - player):
                            dangerous_moves.append(col)
                            logger.warning(f"[{self.account_email}] ⚠️ DANGEROUS: Column {col} gives opponent vertical win")
                        board[row][col] = 0
                        board[row-1][col] = 0
            
            # Filter out dangerous moves only if we have alternatives
            if dangerous_moves and len(valid_moves) > len(dangerous_moves):
                safe_moves = [col for col in valid_moves if col not in dangerous_moves]
                if safe_moves:
                    valid_moves = safe_moves
                    logger.info(f"[{self.account_email}] Filtered dangerous moves: {dangerous_moves}")
            
            # Check for our vertical threat opportunities
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None and row >= 2:  # Need at least 3 spaces above
                    # Check if playing here sets up vertical win potential
                    pieces_below = 0
                    for check_row in range(row + 1, 6):
                        if board[check_row][col] == player:
                            pieces_below += 1
                    
                    # If we have 2 pieces below, this creates a vertical threat
                    if pieces_below == 2:
                        board[row][col] = player
                        # Verify it's actually a winning threat (one more move wins)
                        if row > 0:
                            board[row-1][col] = player
                            is_win = check_winner(board, player)
                            board[row-1][col] = 0
                            if is_win:
                                board[row][col] = 0
                                logger.info(f"[{self.account_email}] ★★ VERTICAL THREAT ★★: Column {col} sets up vertical win")
                                return col
                        board[row][col] = 0
        
        # Multi-move sequence analysis for top moves
        logger.info(f"[{self.account_email}] Analyzing opponent predictions...")
        
        move_evaluations = []
        for col in valid_moves:
            seq_value = analyze_multi_move_sequence([row[:] for row in board], player, col, depth=2)
            move_evaluations.append((col, seq_value))
        
        # If we have clear winner from sequence analysis
        move_evaluations.sort(key=lambda x: x[1], reverse=True)
        best_seq_move, best_seq_value = move_evaluations[0]
        
        if len(move_evaluations) > 1:
            second_best = move_evaluations[1][1]
            if best_seq_value - second_best > 50000:
                logger.info(f"[{self.account_email}] ★ SEQUENCE ANALYSIS ★: Column {best_seq_move}, Value: {best_seq_value:,}")
                return best_seq_move
        
        # Adaptive depth based on game phase
        empty_cells = sum(row.count(0) for row in board)
        
        if total_pieces < 8:
            depth = 12
        elif total_pieces < 16:
            depth = 13
        elif total_pieces < 24:
            depth = 14
        else:
            depth = 15
        
        # Endgame perfect solving
        if empty_cells <= 12:
            depth = min(empty_cells + 5, 18)
            logger.info(f"[{self.account_email}] ENDGAME MODE: depth {depth}")
        
        logger.info(f"[{self.account_email}] ULTRA-GODMODE depth {depth}...")
        
        column, score = minimax_ultra([row[:] for row in board], depth, float('-inf'), float('inf'), True)
        
        calc_time = time.time() - start_time
        
        if column is None:
            column = best_seq_move
        
        # Log opponent predictions for chosen move
        opp_preds = predict_opponent_moves(board, 3-player)
        pred_str = ", ".join([f"Col{c}({p:.2f})" for c, p, _ in opp_preds[:2]])
        
        logger.info(f"[{self.account_email}] ★ ULTRA-GODMODE ★ Column {column}, Time: {calc_time:.2f}s, Score: {score:,}")
        logger.info(f"[{self.account_email}] Opponent likely: {pred_str}")
        
        return column
    
    def make_move(self, column):
        """Make a move"""
        try:
            cells = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr:first-child td.board-cell")
            if column < len(cells):
                cells[column].click()
                logger.info(f"[{self.account_email}] Played column {column}")
                time.sleep(1)
                return True
        except Exception as e:
            logger.error(f"[{self.account_email}] Error making move: {e}")
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
                logger.error(f"[{self.account_email}] Error in game loop: {e}")
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
        """Close browser and cleanup"""
        try:
            self.driver.quit()
            logger.info(f"[{self.account_email}] Browser closed")
            
            # Cleanup temporary profile directory
            try:
                import shutil
                if hasattr(self, 'user_data_dir') and os.path.exists(self.user_data_dir):
                    shutil.rmtree(self.user_data_dir, ignore_errors=True)
                    logger.info(f"[{self.account_email}] Cleaned up profile directory")
            except Exception as e:
                logger.warning(f"[{self.account_email}] Could not cleanup profile: {e}")
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
                    "bet_increase_clicks": 2,
                    "enabled": True
                },
                {
                    "email": "account2@example.com",
                    "password": "password2",
                    "games_per_run": 5,
                    "bet_increase_clicks": 3,
                    "enabled": True
                }
            ],
            "settings": {
                "headless": True,
                "opponent_wait_timeout": 900,
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
    bet_clicks = account.get('bet_increase_clicks', 0)
    
    # Add delay based on account index to stagger start times
    start_delay = account.get('_start_delay', 0)
    if start_delay > 0:
        logger.info(f"[{email}] Waiting {start_delay}s before starting (stagger delay)")
        time.sleep(start_delay)
    
    logger.info(f"[{email}] ╔═══════════════════════════════════════╗")
    logger.info(f"[{email}] Starting session - {games_to_play} games")
    logger.info(f"[{email}] ╚═══════════════════════════════════════╝")
    
    bot = None
    try:
        bot = Connect4HostBot(
            account_email=email,
            account_password=password,
            bet_increase_clicks=bet_clicks,
            headless=settings.get('headless', True)
        )
    except Exception as e:
        logger.error(f"[{email}] Failed to create bot instance: {e}")
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
    logger.info("╔═══════════════════════════════════════════════════════════════════╗")
    logger.info("║  Connect 4 Multi-Account PARALLEL Bot - ULTRA-GODMODE AI         ║")
    logger.info(f"║  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                 ║")
    logger.info("╚═══════════════════════════════════════════════════════════════════╝")
    
    config_path = os.getenv('CONFIG_PATH', 'accounts.json')
    config = load_accounts_config(config_path)
    
    accounts = config.get('accounts', [])
    settings = config.get('settings', {})
    
    enabled_accounts = [acc for acc in accounts if acc.get('enabled', True)]
    
    if not enabled_accounts:
        logger.warning("No enabled accounts found in config")
        return
    
    max_parallel = settings.get('max_parallel_accounts', 5)
    stagger_delay = settings.get('stagger_start_delay', 2)
    
    logger.info(f"Processing {len(enabled_accounts)} accounts with max {max_parallel} parallel")
    logger.info(f"Stagger delay: {stagger_delay}s between account starts")
    
    # Add stagger delays to accounts
    for i, account in enumerate(enabled_accounts):
        account['_start_delay'] = i * stagger_delay
    
    results = []
    
    # Run accounts in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        # Submit all accounts to thread pool
        future_to_account = {
            executor.submit(run_bot_session, account, settings): account 
            for account in enabled_accounts
        }
        
        # Process completed tasks
        for future in concurrent.futures.as_completed(future_to_account):
            account = future_to_account[future]
            try:
                result = future.result()
                results.append(result)
                
                # Progress update
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
    logger.info("\n╔═══════════════════════════════════════════════════════════════════╗")
    logger.info("║                      EXECUTION SUMMARY                            ║")
    logger.info("╠═══════════════════════════════════════════════════════════════════╣")
    
    total_games = sum(r['games_played'] for r in results)
    total_succeeded = sum(r.get('games_succeeded', 0) for r in results)
    successful_accounts = sum(1 for r in results if r['success'])
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        logger.info(f"║ {status} {result['email']:<40} "
                   f"{result.get('games_succeeded', 0):>2}/{result['games_played']:<2} games ║")
    
    logger.info("╠═══════════════════════════════════════════════════════════════════╣")
    logger.info(f"║ Accounts: {successful_accounts}/{len(enabled_accounts)} successful"
               f"{' ' * (45 - len(str(successful_accounts)) - len(str(len(enabled_accounts))))}║")
    logger.info(f"║ Games:    {total_succeeded}/{total_games} succeeded"
               f"{' ' * (48 - len(str(total_succeeded)) - len(str(total_games)))}║")
    logger.info(f"║ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
               f"{' ' * 37}║")
    logger.info("╚═══════════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()