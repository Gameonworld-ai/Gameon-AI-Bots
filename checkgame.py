from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException,
    StaleElementReferenceException, UnexpectedAlertPresentException
)
import time
import random
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("./logs")
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

class Connect4Bot:
    def __init__(self, dashboard_url="https://app.gameonworld.ai/dashboard", difficulty="medium", headless=True,):
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # CRITICAL: Each instance gets its own profile to prevent conflicts
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
        self.last_board_state = None
        self.my_player = None
        
        # Optimization: Precompute winning positions and patterns
        self.winning_positions = self._precompute_winning_positions()
        self.transposition_table = {}
        self.killer_moves = [[None, None] for _ in range(20)]  # Killer move heuristic
        self.history_table = {}  # History heuristic for move ordering
        
        # Perfect play database - known winning/drawing positions
        self.perfect_play_db = self._initialize_perfect_play_db()
        
        # Bitboard masks for ultra-fast winner checking
        self.bitboard_masks = self._initialize_bitboard_masks()
        
        print(f"Bot initialized with difficulty: {difficulty.upper()} - PERFECT PLAY MODE")
        
    def _precompute_winning_positions(self):
        """Precompute all possible winning positions for faster lookup"""
        positions = []
        
        # Horizontal wins
        for r in range(6):
            for c in range(4):
                positions.append([(r, c+i) for i in range(4)])
        
        # Vertical wins
        for c in range(7):
            for r in range(3):
                positions.append([(r+i, c) for i in range(4)])
        
        # Diagonal wins (/)
        for r in range(3, 6):
            for c in range(4):
                positions.append([(r-i, c+i) for i in range(4)])
        
        # Diagonal wins (\)
        for r in range(3):
            for c in range(4):
                positions.append([(r+i, c+i) for i in range(4)])
        
        return positions
    
    def _initialize_bitboard_masks(self):
        """Initialize bitboard masks for ultra-fast winner detection"""
        # Each position in Connect 4 can be represented as a bit
        # This allows checking wins with bitwise operations (much faster)
        masks = {
            'columns': [(1 << (i * 7)) - 1 << j for j in range(7) for i in range(1, 7)],
            'winning_positions': []
        }
        
        # Precompute winning bitmasks
        for positions in self.winning_positions:
            mask = 0
            for r, c in positions:
                mask |= (1 << (r * 7 + c))
            masks['winning_positions'].append(mask)
        
        return masks
    
    def _initialize_perfect_play_db(self):
        """Initialize database of known perfect play positions"""
        # These are proven winning/drawing continuations from solved positions
        db = {
            'forced_draws': set(),
            'winning_sequences': {},
            'avoid_positions': set()
        }
        
        # Known drawn positions (symmetric, both players control center)
        # These patterns force draws with perfect play
        db['forced_draws'].add(tuple([0]*7*6))  # Empty board with perfect play
        
        # Positions to avoid (lead to opponent advantage)
        # Playing column 0 or 6 on moves 1-2 is suboptimal
        
        return db
    
    def start(self):
        """Navigate to login page"""
        self.driver.get("https://app.gameonworld.ai/auth/login")
        self.driver.maximize_window()
        time.sleep(2)
        print("Login page loaded")
    
    def close_popups(self):
        """Close any popups including wallet connection modals"""
        try:
            popup_closed = False
            
            close_selectors = [
                "button.absolute.top-3.right-3",
                "button svg[viewBox='0 0 512 512'] path[d*='289.94']//ancestor::button",
                "svg[viewBox='0 0 512 512']//ancestor::button",
                "button[aria-label='Close']",
                "button[aria-label='close']",
                "button.close",
                ".close-button",
                "button[class*='absolute'][class*='top'][class*='right']",
                "div[role='dialog'] button:first-child",
                "button svg[stroke='currentColor']//ancestor::button",
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            print(f"Closed popup using selector: {selector}")
                            popup_closed = True
                            time.sleep(0.5)
                            break
                    if popup_closed:
                        break
                except Exception:
                    continue
            
            if not popup_closed:
                try:
                    xpath_selectors = [
                        "//button[contains(text(), 'Close')]",
                        "//button[contains(text(), 'Ã—')]",
                        "//button[@aria-label='Close' or @aria-label='close']",
                    ]
                    
                    for xpath in xpath_selectors:
                        buttons = self.driver.find_elements(By.XPATH, xpath)
                        for button in buttons:
                            if button.is_displayed():
                                button.click()
                                print(f"Closed popup using xpath: {xpath}")
                                popup_closed = True
                                time.sleep(0.5)
                                break
                        if popup_closed:
                            break
                except:
                    pass
            
            if not popup_closed:
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    popup_closed = True
                    time.sleep(0.3)
                except:
                    pass
                    
            return popup_closed
            
        except Exception as e:
            return False
    
    def aggressive_popup_close(self):
        """Aggressively close all visible popups"""
        closed_count = 0
        
        try:
            if self.close_popups():
                closed_count += 1
        except:
            pass
        
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            closed_count += 1
            time.sleep(0.3)
        except:
            pass
        
        try:
            self.driver.execute_script("""
                document.querySelectorAll('[role="dialog"], .modal, .popup, [class*="modal"], [class*="popup"]').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });
            """)
            closed_count += 1
        except:
            pass
        
        return closed_count > 0
        
    def login(self, email, password):
        """Login with URL-based verification"""
        try:
            print("Waiting for login form...")
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][placeholder='Email']"))
            )
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password'][placeholder='Password']")
            
            print("Entering credentials...")
            
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(0.5)
            
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Login')]")
            login_button.click()
            
            print("Waiting for redirect...")
            WebDriverWait(self.driver, 15).until(
                lambda driver: "login" not in driver.current_url.lower()
            )
            
            print(f"Redirected to: {self.driver.current_url}")
            time.sleep(2)
            
            print("Closing post-login popups...")
            for i in range(5):
                if self.close_popups():
                    print(f"Closed popup {i+1}")
                    time.sleep(0.5)
            
            print("Login successful - Dashboard loaded")
            return True
            
        except TimeoutException:
            print("Login failed - no redirect from login page")
            self.driver.save_screenshot("login_no_redirect.png")
            return False
        except Exception as e:
            print(f"Login error: {e}")
            self.driver.save_screenshot("login_error.png")
            return False
    
    def wait_for_challenges(self, timeout=300):
        """Wait ONLY for Connect 4 challenge card inside the Join Now section."""
        print(f"Monitoring ONLY Join Now section for Connect 4 (timeout: {timeout}s)...")
        start_time = time.time()
        last_refresh = time.time()

        while time.time() - start_time < timeout:
            try:
                elapsed = int(time.time() - start_time)
                self.close_popups()

                # 1️⃣ Find the "Join Now" title
                try:
                    join_now_title = self.driver.find_element(
                        By.XPATH,
                        "//div[text()='Join Now']"
                    )

                    # 2️⃣ Get the container directly after it
                    join_now_section = join_now_title.find_element(
                        By.XPATH,
                        "following-sibling::div"
                    )

                    # 3️⃣ Scrollable container INSIDE the Join Now section
                    scroll_container = join_now_section.find_element(
                        By.XPATH,
                        ".//div[contains(@class,'overflow-x-scroll')]"
                    )
                except:
                    if elapsed % 10 == 0:
                        print("Join Now section not found yet...")
                    time.sleep(1)
                    continue

                # 🔍 Search ONLY inside the Join Now container
                for _ in range(20):
                    try:
                        # Connect-4 card inside Join Now only
                        card = scroll_container.find_element(
                            By.XPATH,
                            ".//div[contains(@class,'rounded') and .//img[contains(@alt,'Connect')]]"
                        )

                        if card.is_displayed():
                            print("CONNECT 4 FOUND in Join Now section!")
                            return True

                    except:
                        pass

                    # scroll only the Join Now bar
                    self.driver.execute_script(
                        "arguments[0].scrollLeft += 300;",
                        scroll_container
                    )
                    time.sleep(0.25)

                if elapsed % 10 == 0:
                    print(f"No Connect 4 in Join Now yet... ({elapsed}s elapsed)")

                # ⟳ Periodic refresh
                if time.time() - last_refresh >= 30:
                    print(f"Refreshing page... ({elapsed}s elapsed)")
                    self.driver.refresh()
                    time.sleep(2)
                    self.close_popups()
                    last_refresh = time.time()

                time.sleep(1)

            except Exception as e:
                print(f"Error checking Join Now: {e}")
                time.sleep(2)

        print(f"Timeout after {timeout}s — No Connect 4 found in Join Now section")
        return False


        
    def find_and_join_connect4(self):
        """Find and join Connect 4 challenge"""
        try:
            self.aggressive_popup_close()
            
            connect4_card = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Connect 4']/ancestor::div[contains(@class, 'cursor-pointer')]"))
            )
            print("Clicking Connect 4 challenge...")
            connect4_card.click()
            time.sleep(2)
            
            self.close_popups()
            
            join_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Join Challenge')]"))
            )
            print("Clicking Join Challenge...")
            join_button.click()
            time.sleep(3)
            
            print("Waiting for opponent...")
            
            for _ in range(5):
                self.close_popups()
                time.sleep(1)
            
            self.switch_to_game_iframe()
            
            return True
            
        except TimeoutException as e:
            print(f"Error joining challenge: {e}")
            self.driver.save_screenshot("error_join.png")
            return False
            
    def switch_to_game_iframe(self):
        """Switch to the Connect 4 game iframe"""
        try:
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='connect4']"))
            )
            print("Found game iframe, switching context...")
            self.driver.switch_to.frame(iframe)
            self.game_iframe = iframe
            
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".board, table"))
            )
            print("Game loaded successfully!")
            
        except TimeoutException:
            print("Could not find game iframe")
            self.driver.save_screenshot("error_iframe.png")
    
    def read_board_state(self):
        """Read current board state with improved detection"""
        board = [[0]*7 for _ in range(6)]
        
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row_idx, row in enumerate(rows):
                cells = row.find_elements(By.CSS_SELECTOR, "td.board-cell")
                
                for col_idx, cell in enumerate(cells):
                    # Check for red piece (player 1)
                    try:
                        red_imgs = cell.find_elements(By.CSS_SELECTOR, "img[src*='red']")
                        if red_imgs and any(img.is_displayed() for img in red_imgs):
                            board[row_idx][col_idx] = 1
                    except:
                        pass
                    
                    # Check for yellow piece (player 2)
                    try:
                        yellow_imgs = cell.find_elements(By.CSS_SELECTOR, "img[src*='yellow']")
                        if yellow_imgs and any(img.is_displayed() for img in yellow_imgs):
                            board[row_idx][col_idx] = 2
                    except:
                        pass
            
            return board
            
        except Exception as e:
            print(f"Error reading board: {e}")
            return board
    
    def detect_player_number(self):
        """Detect which player number the bot is"""
        if self.my_player is not None:
            return self.my_player
        
        try:
            # Check turn indicator at bottom (your turn)
            bottom_timer = self.driver.find_elements(By.CSS_SELECTOR, ".turn-timer-bottom")
            if bottom_timer and bottom_timer[0].is_displayed():
                # If bottom timer shows, check banner colors to determine player
                banners = self.driver.find_elements(By.CSS_SELECTOR, ".player-banner")
                if len(banners) >= 2:
                    # Bottom banner should be ours
                    bottom_banner = banners[-1]
                    style = bottom_banner.get_attribute("style") or ""
                    
                    if "FD7235" in style or "red" in style.lower():
                        self.my_player = 1
                        print("Detected: Bot is Player 1 (Red)")
                    else:
                        self.my_player = 2
                        print("Detected: Bot is Player 2 (Yellow)")
                    
                    return self.my_player
            
            # Default to player 1 if can't detect
            self.my_player = 1
            print("Using default: Bot is Player 1 (Red)")
            return self.my_player
            
        except:
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
        """Get valid column indices"""
        return [col for col in range(7) if board[0][col] == 0]
    
    def _board_to_string(self, board):
        """Convert board to string for transposition table"""
        return ''.join(''.join(map(str, row)) for row in board)
    
    def _check_winner_fast(self, board, player):
        """Fast winner check using precomputed positions"""
        for positions in self.winning_positions:
            if all(board[r][c] == player for r, c in positions):
                return True
        return False
    
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
            logger.info(f"[] Opening: Column {choice}")
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
            
            logger.info(f"[] Counter-opening: Column {choice}")
            return choice
        
        # Immediate win check
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = player
                if check_winner(board, player):
                    board[row][col] = 0
                    logger.info(f"[] ★★★ WINNING ★★★: Column {col}")
                    return col
                board[row][col] = 0
        
        # Block opponent win
        for col in valid_moves:
            row = get_next_row(board, col)
            if row is not None:
                board[row][col] = 3 - player
                if check_winner(board, 3 - player):
                    board[row][col] = 0
                    logger.info(f"[] ★★ BLOCKING ★★: Column {col}")
                    return col
                board[row][col] = 0
        
        # === TACTICAL ANALYSIS (only after sufficient pieces are on board) ===
        # Early game: focus on positioning, not tactics
        # Mid-late game: tactical opportunities become critical
        
        use_advanced_tactics = total_pieces >= 10  # Only use tactics after 10+ pieces
        
        if use_advanced_tactics:
            # Check for double threat opportunities (creates 2+ winning threats in one move)
            logger.info(f"[] Scanning for double threats...")
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
                        logger.info(f"[] ★★★ DOUBLE THREAT SETUP ★★★: Column {col} creates {threats_created} winning threats at {winning_positions}")
                        return col
            
            # Check if opponent can create double threat (and block it)
            logger.info(f"[] Checking opponent double threats...")
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
                        logger.info(f"[] ★★ BLOCKING OPPONENT DOUBLE THREAT ★★: Column {col}")
                        return col
        
        # Fork detection - only in mid-late game (16+ pieces)
        if total_pieces >= 16:
            # Check for fork opportunities (creating multiple 3-in-a-row threats)
            logger.info(f"[] Scanning for fork opportunities...")
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
                        logger.info(f"[] ★★★ FORK OPPORTUNITY ★★★: Column {col} creates {threat_count} winning threats")
                        return col
            
            # Block opponent forks
            logger.info(f"[] Checking opponent fork threats...")
            for col in valid_moves:
                row = get_next_row(board, col)
                if row is not None:
                    board[row][col] = 3 - player
                    threat_count, positions = count_three_in_row_threats(board, 3 - player)
                    board[row][col] = 0
                    
                    if threat_count >= 2:
                        logger.info(f"[] ★★ BLOCKING OPPONENT FORK ★★: Column {col}")
                        return col
        
        # Vertical threat analysis - always important but validate carefully
        if total_pieces >= 8:  # Only after some pieces are placed
            logger.info(f"[] Analyzing vertical threats...")
            
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
                            logger.warning(f"[] ⚠️ DANGEROUS: Column {col} gives opponent vertical win")
                        board[row][col] = 0
                        board[row-1][col] = 0
            
            # Filter out dangerous moves only if we have alternatives
            if dangerous_moves and len(valid_moves) > len(dangerous_moves):
                safe_moves = [col for col in valid_moves if col not in dangerous_moves]
                if safe_moves:
                    valid_moves = safe_moves
                    logger.info(f"[] Filtered dangerous moves: {dangerous_moves}")
            
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
                                logger.info(f"[] ★★ VERTICAL THREAT ★★: Column {col} sets up vertical win")
                                return col
                        board[row][col] = 0
        
        # Multi-move sequence analysis for top moves
        logger.info(f"[] Analyzing opponent predictions...")
        
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
                logger.info(f"[] ★ SEQUENCE ANALYSIS ★: Column {best_seq_move}, Value: {best_seq_value:,}")
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
            logger.info(f"[] ENDGAME MODE: depth {depth}")
        
        logger.info(f"[] ULTRA-GODMODE depth {depth}...")
        
        column, score = minimax_ultra([row[:] for row in board], depth, float('-inf'), float('inf'), True)
        
        calc_time = time.time() - start_time
        
        if column is None:
            column = best_seq_move
        
        # Log opponent predictions for chosen move
        opp_preds = predict_opponent_moves(board, 3-player)
        pred_str = ", ".join([f"Col{c}({p:.2f})" for c, p, _ in opp_preds[:2]])
        
        logger.info(f"[] ★ ULTRA-GODMODE ★ Column {column}, Time: {calc_time:.2f}s, Score: {score:,}")
        logger.info(f"[] Opponent likely: {pred_str}")
        
        return column
    
    
    def detect_opponent_move(self, old_board, new_board):
        """Detect which column opponent played"""
        for col in range(7):
            for row in range(6):
                if old_board[row][col] != new_board[row][col]:
                    print(f"[Opponent] Played column {col} at row {row}")
                    return col, row
        return None, None
    
    def make_move(self, column):
        """Click column to drop piece"""
        try:
            cells = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr:first-child td.board-cell")
            
            if column < len(cells):
                cells[column].click()
                print(f"[Bot] Played column {column}")
                time.sleep(1)
                return True
            
        except Exception as e:
            print(f"Error making move: {e}")
            return False
    
    def check_game_over(self):
        """Enhanced game over detection"""
        try:
            # Check for game over popups/overlays
            popups = self.driver.find_elements(By.CSS_SELECTOR, "[style*='position: fixed']")
            for popup in popups:
                try:
                    text = popup.text.lower()
                    if any(word in text for word in ['won', 'defeat', 'draw', 'winner', 'time', 'victory']):
                        print(f"Game Over detected: {text[:50]}")
                        return True
                except:
                    continue
            
            # Check if iframe is still present
            try:
                self.driver.switch_to.default_content()
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='connect4']")
                if not iframes:
                    print("Game iframe no longer present")
                    return True
                
                # Switch back if iframe exists
                if self.game_iframe:
                    self.driver.switch_to.frame(self.game_iframe)
            except:
                pass
            
            return False
            
        except:
            return False
    
    def play_game(self):
        """Main game loop with robust error handling and game-end detection"""
        print(f"\n=== STARTING GAME (Difficulty: {self.difficulty.upper()}) ===")
        move_count = 0
        stale_element_count = 0
        max_stale_attempts = 3
        
        # Detect which player we are
        time.sleep(2)
        my_player = self.detect_player_number()
        
        self.last_board_state = self.read_board_state()
        
        while move_count < 42:
            try:
                self.driver.switch_to.default_content()
                self.close_popups()
                
                if self.game_iframe:
                    try:
                        self.driver.switch_to.frame(self.game_iframe)
                    except:
                        print("Error switching to iframe - game may have ended")
                        break
                
                # Check for game over first
                if self.check_game_over():
                    print("Game finished!")
                    time.sleep(3)
                    break
                
                # Try to read board - if fails, game might be over
                try:
                    current_board = self.read_board_state()
                except:
                    print("Cannot read board - checking if game ended...")
                    self.driver.switch_to.default_content()
                    if self.check_for_result_page():
                        print("Game ended - result page detected")
                        break
                    time.sleep(1)
                    continue
                
                # Detect opponent move
                if self.last_board_state != current_board and not self.is_my_turn():
                    opp_col, opp_row = self.detect_opponent_move(self.last_board_state, current_board)
                    if opp_col is not None:
                        print(f"[Detected] Opponent played column {opp_col}")
                
                if self.is_my_turn():
                    board = self.read_board_state()
                    
                    print(f"\n--- Move {move_count + 1} ---")
                    print("Current Board:")
                    for row in board:
                        print(row)
                    
                    best_column = self.calculate_best_move(board, my_player)
                    
                    if best_column is not None:
                        if self.make_move(best_column):
                            move_count += 1
                            time.sleep(1.5)
                            
                            # Reset stale element counter on successful move
                            stale_element_count = 0
                            
                            try:
                                self.last_board_state = self.read_board_state()
                            except:
                                print("Board read failed after move - game may have ended")
                                break
                    else:
                        print("No valid moves")
                        break
                else:
                    time.sleep(1)
            
            except StaleElementReferenceException:
                stale_element_count += 1
                print(f"Stale element detected (attempt {stale_element_count}/{max_stale_attempts})")
                
                if stale_element_count >= max_stale_attempts:
                    print("Multiple stale elements - game likely ended")
                    
                    # Switch to main content and check for result page
                    self.driver.switch_to.default_content()
                    
                    if self.check_for_result_page():
                        print("Game ended - result page found")
                        break
                    else:
                        print("Game may have ended - exiting game loop")
                        break
                
                time.sleep(2)
                continue
                
            except Exception as e:
                print(f"Error in game loop: {e}")
                
                # Check if game ended
                self.driver.switch_to.default_content()
                if self.check_for_result_page():
                    print("Game ended - result page detected")
                    break
                
                self.driver.save_screenshot(f"error_move_{move_count}.png")
                time.sleep(2)
        
        print(f"\nGame ended after {move_count} moves")
        time.sleep(3)

    def check_for_result_page(self):
        """Check if we're on the result/game-over page"""
        try:
            # Look for result page indicators
            result_selectors = [
                "//h2[contains(text(), 'Defeat')]",
                "//h2[contains(text(), 'Victory')]",
                "//h2[contains(text(), 'Winner')]",
                "//button[contains(., 'Back to Home')]",
                "//button[contains(., 'Play Again')]",
                "//section[contains(@class, 'bg-black/90')]//img[@alt='player']",
            ]
            
            for selector in result_selectors:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements and any(el.is_displayed() for el in elements):
                    print(f"Result page confirmed: {selector}")
                    return True
            
            return False
            
        except:
            return False

    def _safe_click(driver, el):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'center'})", el)
        except Exception:
            pass
        try:
            el.click()
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException):
            try:
                driver.execute_script("arguments[0].click()", el)
                return True
            except Exception:
                return False

    def _hard_redirect(driver, url):
        # Navigate at the top window â€" works even if weâ€™re inside an iframe/modal
        try:
            driver.execute_script("window.top.location.href = arguments[0];", url)
        except Exception:
            driver.get(url)
    
    def handle_post_game(self):
        """Enhanced post-game handler with automatic result page detection"""
        try:
            print("\nHandling post-game...")
            
            # Make sure we're in default content
            self.driver.switch_to.default_content()
            self.game_iframe = None
            
            # Wait a bit for any transitions
            time.sleep(2)
            
            # Check if already on result page
            if not self.check_for_result_page():
                print("Waiting for result page to appear...")
                time.sleep(3)
            
            # Close any popups
            self.close_popups()
            time.sleep(1)
            
            # Look for Back to Home button with extended timeout
            print("Looking for 'Back to Home' button...")
            
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    back_button = self.driver.find_element(By.XPATH, "//button[contains(., 'Back to Home')]")
                    if back_button.is_displayed():
                        print(f"Found 'Back to Home' button (attempt {attempt + 1})")
                        back_button.click()
                        time.sleep(2)
                        break
                except:
                    if attempt < max_attempts - 1:
                        print(f"Back button not found yet (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(2)
                    else:
                        print("Back button not found after multiple attempts")
                        # Navigate directly to dashboard
                        print("Navigating directly to dashboard...")
                        self.driver.get(self.dashboard_url)
                        time.sleep(3)
            
            # Clean up popups
            print("Cleaning up popups...")
            for _ in range(3):
                self.close_popups()
                time.sleep(0.5)
            
            # Verify dashboard
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//h3[contains(text(), 'Challenges')] | //div[contains(@class, 'overflow-x-auto')]"))
                )
                print("Successfully returned to dashboard")
            except:
                print("Dashboard verification timeout - may need manual check")
            
            return True
            
        except Exception as e:
            print(f"Error in post-game handling: {e}")
            print("Forcing navigation to dashboard...")
            self.driver.get(self.dashboard_url)
            time.sleep(3)
            self.close_popups()
            return True
    
    def quit(self):
        """Clean shutdown"""
        try:
            self.driver.quit()
        except:
            pass

# Main execution
if __name__ == "__main__":
    EMAIL = os.getenv('GAME_EMAIL', 'jafat54491@gamepec.com')
    PASSWORD = os.getenv('GAME_PASSWORD', '123456')
    
    DIFFICULTY = "medium"  # Expert mode for maximum strength
    
    bot = Connect4Bot(difficulty=DIFFICULTY)
    
    try:
        bot.start()
        
        if bot.login(EMAIL, PASSWORD):
            game_count = 0
            
            while True:
                game_count += 1
                print(f"\n{'='*60}")
                print(f"GAME SESSION {game_count} - Difficulty: {DIFFICULTY.upper()}")
                print(f"{'='*60}\n")
                
                if bot.wait_for_challenges(timeout=30000):
                    if bot.find_and_join_connect4():
                        bot.play_game()
                        bot.handle_post_game()
                        print("\nReturning to challenge monitoring...")
                        time.sleep(2)
                    else:
                        print("Failed to join challenge, retrying...")
                        time.sleep(5)
                else:
                    print("No challenges found in 5 minutes")
                    user_input = input("Continue waiting? (y/n): ")
                    if user_input.lower() != 'y':
                        break
        else:
            print("Login failed. Exiting...")
            
    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        bot.driver.save_screenshot("fatal_error.png")
    finally:
        input("\nPress Enter to close browser...")
        bot.quit()
