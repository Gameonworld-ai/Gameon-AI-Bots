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

class TicTacToeBot:
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
        
        # (Old tictactoe precomputations are left as-is but unused)
        self.winning_positions = self._precompute_winning_positions()
        self.transposition_table = {}
        self.killer_moves = [[None, None] for _ in range(20)]
        self.history_table = {}
        self.perfect_play_db = self._initialize_perfect_play_db()
        self.bitboard_masks = self._initialize_bitboard_masks()
        
        print(f"Bot initialized with difficulty: {difficulty.upper()} - SUPER TIC TAC TOE MODE")
        
    def _precompute_winning_positions(self):
        """Precompute all possible winning positions (old tictactoe logic, unused now)"""
        positions = []
        for r in range(6):
            for c in range(4):
                positions.append([(r, c+i) for i in range(4)])
        for c in range(7):
            for r in range(3):
                positions.append([(r+i, c) for i in range(4)])
        for r in range(3, 6):
            for c in range(4):
                positions.append([(r-i, c+i) for i in range(4)])
        for r in range(3):
            for c in range(4):
                positions.append([(r+i, c+i) for i in range(4)])
        return positions
    
    def _initialize_bitboard_masks(self):
        """Old tictactoe bitboard masks (kept but unused)"""
        masks = {
            'columns': [(1 << (i * 7)) - 1 << j for j in range(7) for i in range(1, 7)],
            'winning_positions': []
        }
        for positions in self.winning_positions:
            mask = 0
            for r, c in positions:
                mask |= (1 << (r * 7 + c))
            masks['winning_positions'].append(mask)
        return masks
    
    def _initialize_perfect_play_db(self):
        """Old tictactoe DB (kept but unused)"""
        db = {
            'forced_draws': set(),
            'winning_sequences': {},
            'avoid_positions': set()
        }
        db['forced_draws'].add(tuple([0]*7*6))
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
        """Wait ONLY for tictactoe challenge card inside the Join Now section."""
        print(f"Monitoring ONLY Join Now section for tictactoe (timeout: {timeout}s)...")
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
                            ".//div[contains(@class,'rounded') and .//img[contains(@alt,'Super Tic Tac Toe')]]"
                        )

                        if card.is_displayed():
                            print("tictactoe FOUND in Join Now section!")
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
                    print(f"No tictactoe in Join Now yet... ({elapsed}s elapsed)")

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

        print(f"Timeout after {timeout}s — No tictactoe found in Join Now section")
        return False

        
    def find_and_join_tictactoe(self):
        """Find and join tictactoe challenge (UI flow left unchanged)"""
        try:
            self.aggressive_popup_close()
            
            tictactoe_card = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Super Tic Tac Toe']/ancestor::div[contains(@class, 'cursor-pointer')]"))
            )
            print("Clicking tictactoe challenge...")
            tictactoe_card.click()
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
        """Switch to the game iframe (selector kept same; adjust if your super TTT iframe src differs)"""
        try:
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='tic']"))
            )
            print("Found game iframe, switching context...")
            self.driver.switch_to.frame(iframe)
            self.game_iframe = iframe
            
            # For TTT, we'll just wait for cells to appear instead of .board/table
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cell, div[class*='cell'], div[class*='aspect-square']"))
            )
            print("Game loaded successfully!")
            
        except TimeoutException:
            print("Could not find game iframe")
            self.driver.save_screenshot("error_iframe.png")

    # ======================================================================
    # SUPER TIC TAC TOE: BOARD READING & AI HELPERS
    # ======================================================================

    def _ttt_get_lines(self):
        """All winning lines on 3x3 board"""
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

    def _ttt_check_winner(self, board):
        """Check if there's a winner. Returns 'X', 'O', or None"""
        for line in self._ttt_get_lines():
            values = [board[r][c] for r, c in line]
            if values[0] == values[1] == values[2] and values[0] is not None:
                return values[0]
        return None

    def _ttt_is_board_full(self, board):
        """Check if 3x3 board is full"""
        return all(board[r][c] is not None for r in range(3) for c in range(3))

    def _ttt_get_valid_moves(self, board):
        """All empty cells"""
        return [(r, c) for r in range(3) for c in range(3) if board[r][c] is None]

    def _ttt_minimax(self, board, depth, is_maximizing, player, alpha, beta, start_time, max_time):
        """Minimax with alpha-beta pruning and time limit"""
        if time.time() - start_time > max_time:
            return 0
        
        opponent = 'O' if player == 'X' else 'X'
        
        winner = self._ttt_check_winner(board)
        if winner == player:
            return 100 - depth
        elif winner == opponent:
            return depth - 100
        elif self._ttt_is_board_full(board):
            return 0
        
        if depth >= 9:
            return 0
        
        valid_moves = self._ttt_get_valid_moves(board)
        
        if is_maximizing:
            max_eval = float('-inf')
            for r, c in valid_moves:
                board[r][c] = player
                eval_score = self._ttt_minimax(board, depth + 1, False, player, alpha, beta, start_time, max_time)
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
                eval_score = self._ttt_minimax(board, depth + 1, True, player, alpha, beta, start_time, max_time)
                board[r][c] = None
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def _ttt_get_best_move(self, board, player, max_time=6):
        """Get best move using minimax with time limit"""
        start_time = time.time()
        valid_moves = self._ttt_get_valid_moves(board)
        
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
            score = self._ttt_minimax(board, 0, False, player, float('-inf'), float('inf'), start_time, max_time)
            board[r][c] = None
            
            if score > best_score:
                best_score = score
                best_move = (r, c)
        
        return best_move if best_move else random.choice(valid_moves)

    # ======================================================================
    # SUPER TIC TAC TOE: GAMEPLAY FUNCTIONS (REPLACED)
    # ======================================================================

    def read_board_state(self):
        """
        Read the 3x3 tic-tac-toe board state.
        Uses same logic as your working TicTacToe bot.
        """
        board = [[None for _ in range(3)] for _ in range(3)]
        try:
            cells = self.driver.find_elements(By.CSS_SELECTOR, "div.cell")
            logger.info(f"[TTT] Found {len(cells)} cells")

            if len(cells) != 9:
                logger.warning(f"[TTT] Expected 9 cells, found {len(cells)}")
                cells = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='aspect-square'], div[class*='cell']"
                )
                logger.info(f"[TTT] Alternative selector found {len(cells)} cells")
                if len(cells) == 0:
                    logger.error("[TTT] No cells found!")
                    return board

            for i in range(min(9, len(cells))):
                cell = cells[i]
                row = i // 3
                col = i % 3

                try:
                    # data-value attribute (if exists)
                    data_value = cell.get_attribute('data-value')
                    if data_value:
                        try:
                            val = int(data_value)
                            board[row][col] = 'X' if val == 1 else 'O' if val == 2 else None
                            continue
                        except:
                            pass

                    # images inside cell
                    imgs = cell.find_elements(By.TAG_NAME, "img")
                    if imgs:
                        for img in imgs:
                            alt = img.get_attribute('alt') or ''
                            src = img.get_attribute('src') or ''
                            if alt.upper() == 'X' or 'W-rTeAz-qe.png' in src:
                                board[row][col] = 'X'
                                break
                            elif alt.upper() == 'O' or 'B-4DvpsQW3.png' in src:
                                board[row][col] = 'O'
                                break

                    # fallback: check HTML / class
                    if board[row][col] is None:
                        cell_class = cell.get_attribute('class') or ''
                        if 'disabled' in cell_class:
                            html = cell.get_attribute('innerHTML') or ''
                            if 'W-rTeAz-qe.png' in html or 'alt="X"' in html:
                                board[row][col] = 'X'
                            elif 'B-4DvpsQW3.png' in html or 'alt="O"' in html:
                                board[row][col] = 'O'
                except Exception as e:
                    logger.debug(f"[TTT] Error reading cell {i}: {e}")
                    continue

            return board

        except Exception as e:
            logger.error(f"[TTT] Error reading board: {e}")
            return board

    def detect_player_number(self):
        """Detect if bot is 'X' or 'O' (adapted from TicTacToeBot.detect_my_player)"""
        if self.my_player is not None:
            return self.my_player
        try:
            print("[TTT] Detecting player...")
            time.sleep(2)

            # Method 1: turn indicator divs
            turn_divs = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.current-player-turn, div.my-turn, div.opponent-turn"
            )
            for div in turn_divs:
                if div.is_displayed():
                    text = (div.text or "").upper()
                    classes = div.get_attribute('class') or ''
                    print(f"[TTT] Turn indicator: '{text}' classes='{classes}'")
                    if 'YOUR TURN' in text or 'MY TURN' in text:
                        if 'my-turn-o' in classes:
                            self.my_player = 'O'
                            print("[TTT] Bot is O (from class)")
                            return self.my_player
                        elif 'my-turn-x' in classes:
                            self.my_player = 'X'
                            print("[TTT] Bot is X (from class)")
                            return self.my_player

            # Method 2: 'Your Turn' vs 'Opponent'
            your_turn = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Your Turn')]")
            if your_turn and any(el.is_displayed() for el in your_turn):
                self.my_player = 'X'
                print("[TTT] Bot is X (Your Turn)")
                return self.my_player

            opponent_turn = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Opponent')]")
            if opponent_turn and any(el.is_displayed() for el in opponent_turn):
                self.my_player = 'O'
                print("[TTT] Bot is O (Opponent indicator)")
                return self.my_player

            # Method 3: board fill
            board = self.read_board_state()
            if board:
                filled = sum(1 for row in board for cell in row if cell is not None)
                print(f"[TTT] Board has {filled} filled cells")
                if filled == 0:
                    self.my_player = 'X'
                    print("[TTT] Bot is X (empty board)")
                    return self.my_player
                elif filled == 1:
                    self.my_player = 'O'
                    print("[TTT] Bot is O (one piece)")
                    return self.my_player

            # Default
            self.my_player = 'O'
            print("[TTT] Bot defaulting to O")
            return self.my_player

        except Exception as e:
            print(f"[TTT] Detection error: {e}")
            self.my_player = 'X'
            return self.my_player

    def is_my_turn(self):
        """Check if it's our turn (Tic Tac Toe logic)"""
        try:
            # my-turn class
            my_turn_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.my-turn")
            for div in my_turn_divs:
                if div.is_displayed():
                    text = (div.text or "").upper()
                    if 'YOUR TURN' in text:
                        return True

            # opponent-turn class
            opponent_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.opponent-turn")
            for div in opponent_divs:
                if div.is_displayed():
                    return False

            # board class
            boards = self.driver.find_elements(By.CSS_SELECTOR, "div.board")
            for board in boards:
                classes = board.get_attribute('class') or ''
                if 'my-turn-board' in classes:
                    return True
                if 'opponent-turn-board' in classes:
                    return False

            # Simple text indicators
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

    def get_valid_moves(self, board):
        """Wrapper for Tic Tac Toe valid moves"""
        return self._ttt_get_valid_moves(board)

    def calculate_best_move(self, board, player=None):
        """
        Tic Tac Toe minimax-based move chooser.
        `player` is 'X' or 'O'; if None, uses self.my_player.
        """
        if player is None:
            player = self.my_player or 'X'

        # Simple difficulty handling if you want later
        max_time = 6
        if self.difficulty == "easy":
            max_time = 2
        elif self.difficulty == "hard":
            max_time = 8

        best_move = self._ttt_get_best_move(board, player, max_time=max_time)
        logger.info(f"[TTT] Best move for {player}: {best_move}")
        return best_move

    def detect_opponent_move(self, old_board, new_board):
        """Detect which (row, col) opponent played in 3x3"""
        try:
            for r in range(3):
                for c in range(3):
                    if old_board[r][c] != new_board[r][c]:
                        print(f"[Opponent] Played ({r},{c}) from '{old_board[r][c]}' to '{new_board[r][c]}'")
                        return (r, c)
        except:
            pass
        return None

    def make_move(self, row, col):
        """Click specific 3x3 Tic Tac Toe cell"""
        try:
            cells = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.cell, div[class*='aspect-square'], div[class*='cell']"
            )
            logger.info(f"[TTT] Making move ({row},{col}) - {len(cells)} cells found")

            idx = row * 3 + col
            if idx < len(cells):
                cell = cells[idx]

                # Scroll into view
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", cell
                    )
                    time.sleep(0.3)
                except:
                    pass

                try:
                    cell.click()
                except:
                    self.driver.execute_script("arguments[0].click();", cell)

                print(f"[Bot] Played ({row},{col})")
                time.sleep(1)
                return True
            else:
                logger.error(f"[TTT] Cell index {idx} out of range (have {len(cells)} cells)")
                return False

        except Exception as e:
            logger.error(f"[TTT] Move error: {e}")
            return False

    def check_game_over(self):
        """Enhanced game over detection (works for TTT too)"""
        try:
            # Overlays / popups
            popups = self.driver.find_elements(By.CSS_SELECTOR, "[style*='position: fixed']")
            for popup in popups:
                try:
                    text = (popup.text or "").lower()
                    if any(word in text for word in ['won', 'defeat', 'draw', 'winner', 'time', 'victory']):
                        print(f"Game Over detected: {text[:50]}")
                        return True
                except:
                    continue
            
            # Also check headings like the dedicated TTT bot
            game_over = self.driver.find_elements(By.XPATH,
                "//h1[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')] | "
                "//h2[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')]"
            )
            if game_over and any(el.is_displayed() for el in game_over):
                result = " ".join([el.text for el in game_over if el.is_displayed()])
                print(f"Game Over detected (heading): {result}")
                return True

            # iframe presence check
            try:
                self.driver.switch_to.default_content()
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='tic']")
                if not iframes:
                    print("Game iframe no longer present")
                    return True
                if self.game_iframe:
                    self.driver.switch_to.frame(self.game_iframe)
            except:
                pass
            
            return False
            
        except:
            return False
    
    def play_game(self):
        """Main Super Tic Tac Toe game loop with robust handling"""
        print(f"\n=== STARTING SUPER TIC TAC TOE GAME (Difficulty: {self.difficulty.upper()}) ===")
        move_count = 0
        stale_element_count = 0
        max_stale_attempts = 3
        
        time.sleep(2)
        my_player = self.detect_player_number()
        self.last_board_state = self.read_board_state()
        
        max_moves = 50  # safety cap; real max is 9
        
        while move_count < max_moves:
            try:
                # Popups & iframe management like original code
                self.driver.switch_to.default_content()
                self.close_popups()
                
                if self.game_iframe:
                    try:
                        self.driver.switch_to.frame(self.game_iframe)
                    except:
                        print("Error switching to iframe - game may have ended")
                        break
                
                # Check generic game over
                if self.check_game_over():
                    print("Game finished (generic detector)!")
                    time.sleep(3)
                    break

                # Direct heading-based detection (Victory/Defeat/Draw)
                try:
                    game_over = self.driver.find_elements(By.XPATH,
                        "//h1[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')] | "
                        "//h2[contains(text(), 'Victory') or contains(text(), 'Defeat') or contains(text(), 'Draw')]"
                    )
                    if game_over and any(el.is_displayed() for el in game_over):
                        result = " ".join([el.text for el in game_over if el.is_displayed()])
                        print(f"Game ended - {result}")
                        break
                except:
                    pass
                
                # Try to read board
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
                if (
                    self.last_board_state is not None
                    and current_board is not None
                    and self.last_board_state != current_board
                    and not self.is_my_turn()
                ):
                    opp_move = self.detect_opponent_move(self.last_board_state, current_board)
                    if opp_move is not None:
                        r, c = opp_move
                        print(f"[Detected] Opponent played ({r},{c})")
                
                # Wait if it's not our turn
                if not self.is_my_turn():
                    print("Waiting for opponent...")
                    time.sleep(2)
                    continue
                
                print(f"\n--- Move {move_count + 1} ---")
                board = current_board
                if board is None:
                    print("Could not read board")
                    time.sleep(2)
                    continue
                
                print("Current Board:")
                for row in board:
                    row_str = " | ".join([cell if cell else "." for cell in row])
                    print("  " + row_str)
                
                best_move = self.calculate_best_move(board, my_player)
                
                if best_move is None:
                    print("No valid moves")
                    time.sleep(2)
                    break
                
                row, col = best_move
                print(f"Best move: ({row},{col}) for player {my_player}")
                
                if self.make_move(row, col):
                    move_count += 1
                    time.sleep(2)
                    
                    stale_element_count = 0
                    
                    try:
                        self.last_board_state = self.read_board_state()
                    except:
                        print("Board read failed after move - game may have ended")
                        break
                else:
                    print("Move failed")
                    time.sleep(1)
            
            except StaleElementReferenceException:
                stale_element_count += 1
                print(f"Stale element detected (attempt {stale_element_count}/{max_stale_attempts})")
                
                if stale_element_count >= max_stale_attempts:
                    print("Multiple stale elements - game likely ended")
                    
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
        try:
            driver.execute_script("window.top.location.href = arguments[0];", url)
        except Exception:
            driver.get(url)
    
    def handle_post_game(self):
        """Enhanced post-game handler with automatic result page detection"""
        try:
            print("\nHandling post-game...")
            
            self.driver.switch_to.default_content()
            self.game_iframe = None
            
            time.sleep(2)
            
            if not self.check_for_result_page():
                print("Waiting for result page to appear...")
                time.sleep(3)
            
            self.close_popups()
            time.sleep(1)
            
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
                        print("Navigating directly to dashboard...")
                        self.driver.get(self.dashboard_url)
                        time.sleep(3)
            
            print("Cleaning up popups...")
            for _ in range(3):
                self.close_popups()
                time.sleep(0.5)
            
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
    EMAIL = os.getenv('GAME_EMAIL', 'fmgmv@comfythings.com')
    PASSWORD = os.getenv('GAME_PASSWORD', '123456')
    
    DIFFICULTY = "medium"  # Expert mode for maximum strength
    
    bot = TicTacToeBot(difficulty=DIFFICULTY)
    
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
                    if bot.find_and_join_tictactoe():
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
