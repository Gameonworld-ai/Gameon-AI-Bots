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

class CheckersUltraExpertBot:
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
        self.my_color = None
        self.move_timeout = 15
        
        # Configurable AI depth - OPTIMIZED FOR SPEED
        self.ai_early_depth = 4      # Reduced from 6 (faster opening)
        self.ai_mid_depth = 5        # Reduced from 8 (faster mid-game)
        self.ai_end_depth = 7        # Reduced from 10 (faster endgame)
        self.max_move_time = 7  
        
        print(f"Bot initialized with difficulty: {difficulty.upper()} - PERFECT PLAY MODE")
        
    
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
        """Wait ONLY for Checkers challenge card inside the Join Now section."""
        print(f"Monitoring ONLY Join Now section for Checkers (timeout: {timeout}s)...")
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
                            ".//div[contains(@class,'rounded') and .//img[contains(@alt,'Checkers')]]"
                        )

                        if card.is_displayed():
                            print("Checkers FOUND in Join Now section!")
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
                    print(f"No Checkers in Join Now yet... ({elapsed}s elapsed)")

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

        print(f"Timeout after {timeout}s — No Checkers found in Join Now section")
        return False


        
    def find_and_join_Checkers(self):
        """Find and join Checkers challenge"""
        try:
            self.aggressive_popup_close()
            
            Checkers_card = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Checkers']/ancestor::div[contains(@class, 'cursor-pointer')]"))
            )
            print("Clicking Checkers challenge...")
            Checkers_card.click()
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
        """Switch to the Checkers game iframe"""
        try:
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='checkerf']"))
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
                logger.error(f"[] Could not find grid container")
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
                logger.warning(f"[] Expected 64 squares, found {len(squares)}")
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
                    logger.debug(f"[] Error reading square {idx}: {e}")
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
            
            logger.debug(f"[] Position analysis: "
                        f"Bottom(A:{bottom_rows_A}, B:{bottom_rows_B}), "
                        f"Top(A:{top_rows_A}, B:{top_rows_B})")
            
            type_to_player = {}
            
            if bottom_rows_A > bottom_rows_B:
                type_to_player['A'] = 'player1'
                type_to_player['B'] = 'player2'
                logger.info(f"[] Piece mapping: Type A=player1 (bottom), Type B=player2 (top)")
            else:
                type_to_player['B'] = 'player1'
                type_to_player['A'] = 'player2'
                logger.info(f"[] Piece mapping: Type B=player1 (bottom), Type A=player2 (top)")
            
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
                
                logger.debug(f"[] Final board: {piece_count} pieces "
                           f"(P1: {p1_count}, P2: {p2_count}, Kings: {king_count})")
            else:
                logger.warning(f"[] ⚠ Empty board detected")
            
            return board
            
        except Exception as e:
            logger.error(f"[] Error reading board: {e}")
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
            
            logger.info(f"[] Board analysis: "
                       f"Bottom rows (P1:{bottom_rows_p1}, P2:{bottom_rows_p2}), "
                       f"Top rows (P1:{top_rows_p1}, P2:{top_rows_p2})")
            
            # Strategy 1: Check piece positions (most reliable)
            # If player1 pieces are at bottom, we are player1
            # If player2 pieces are at bottom, we are player2
            if bottom_rows_p1 > bottom_rows_p2:
                self.my_color = 'player1'
                logger.info(f"[] Detected by board position: PLAYER1 (bottom)")
                return self.my_color
            elif bottom_rows_p2 > bottom_rows_p1:
                self.my_color = 'player2'
                logger.info(f"[] Detected by board position: PLAYER2 (bottom)")
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
                        
                        logger.info(f"[] Detected by turn text: {self.my_color.upper()}")
                        return self.my_color
            except Exception as e:
                logger.debug(f"[] Turn text check failed: {e}")
            
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
                    logger.info(f"[] Starting position + our turn = PLAYER1")
                    return self.my_color
                else:
                    self.my_color = 'player2'
                    logger.info(f"[] Starting position + waiting = PLAYER2")
                    return self.my_color
            
            # Strategy 4: Default based on bottom row dominance
            if bottom_rows_p1 >= bottom_rows_p2:
                self.my_color = 'player1'
                logger.info(f"[] Default by bottom dominance: PLAYER1")
            else:
                self.my_color = 'player2'
                logger.info(f"[] Default by bottom dominance: PLAYER2")
            
            return self.my_color
            
        except Exception as e:
            logger.error(f"[] Error detecting color: {e}")
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
                logger.debug(f"[] Turn detected: 'Your Turn' text")
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
                        logger.debug(f"[] Turn detected: green bottom timer")
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
                        logger.debug(f"[] Turn detected: clickable pieces")
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"[] Error checking turn: {e}")
            return False
    
    def make_move(self, move):
        """Execute move on grid board - FIXED VERSION"""
        try:
            from_r, from_c = move['from']
            from_idx = from_r * 8 + from_c
            
            logger.info(f"[] Executing move from ({from_r},{from_c}) idx={from_idx}")
            
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
                logger.error(f"[] Cannot find grid")
                return False
            
            # Get all squares
            squares = grid.find_elements(By.CSS_SELECTOR, "div[class*='aspect-square']")
            
            if len(squares) < 64:
                logger.error(f"[] Not enough squares: {len(squares)}")
                return False
            
            # Click source
            if from_idx >= len(squares):
                logger.error(f"[] Invalid from_idx: {from_idx}")
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
                
                logger.info(f"[] ✓ Selected square {from_idx} ({from_r},{from_c})")
                time.sleep(0.6)
                
            except Exception as e:
                logger.error(f"[] Failed to select source: {e}")
                
                # Try clicking image inside
                try:
                    imgs = source.find_elements(By.TAG_NAME, "img")
                    if imgs:
                        self.driver.execute_script("arguments[0].click();", imgs[0])
                        logger.info(f"[] ✓ Selected via image")
                        time.sleep(0.6)
                except:
                    return False
            
            # Click destinations
            for step_idx, (to_r, to_c) in enumerate(move['path']):
                to_idx = to_r * 8 + to_c
                
                if to_idx >= len(squares):
                    logger.error(f"[] Invalid to_idx: {to_idx}")
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
                    
                    logger.info(f"[] ✓ Moved to square {to_idx} ({to_r},{to_c}) "
                              f"[step {step_idx+1}/{len(move['path'])}]")
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"[] Failed to click destination {to_idx}: {e}")
                    return False
            
            logger.info(f"[] ★ Move completed successfully ★")
            time.sleep(1)
            return True
            
        except Exception as e:
            logger.error(f"[] ✗ Critical error making move: {e}")
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
        
        logger.info(f"[] ULTRA EXPERT depth {depth} (pieces: {total_pieces})...")
        
        move, score = minimax_ultra(deepcopy(board), depth, float('-inf'), float('inf'), True)
        
        calc_time = time.time() - start_time
        logger.info(f"[] ★ ULTRA EXPERT DEPTH {depth} ★ Time: {calc_time:.2f}s, Score: {score:,}")
        
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
                iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='checkerf']")
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
        """Main game loop - FIXED VERSION"""
        logger.info(f"[] Starting game")
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
                        logger.warning(f"[] Failed to switch to saved iframe: {e}")
                        iframe_switch_failures += 1
                        
                        if iframe_switch_failures <= 3:
                            logger.info(f"[] Attempting to re-locate iframe...")
                            if not self.switch_to_game_iframe():
                                if iframe_switch_failures >= 3:
                                    logger.error(f"[] Cannot find iframe after 3 attempts")
                                    break
                                time.sleep(2)
                                continue
                        else:
                            logger.error(f"[] Too many iframe switch failures")
                            break
                else:
                    logger.info(f"[] No saved iframe, searching...")
                    if not self.switch_to_game_iframe():
                        logger.error(f"[] Could not locate game iframe")
                        break
                
                # Check game over
                if self.check_game_over():
                    logger.info(f"[] Game finished")
                    break
                
                # Read board
                board = self.read_board_state()
                piece_count = sum(1 for r in board for c in r if c)
                
                if piece_count == 0:
                    logger.warning(f"[] Empty board, quick retry...")
                    
                    for retry in range(3):
                        time.sleep(2)
                        board = self.read_board_state()
                        piece_count = sum(1 for r in board for c in r if c)
                        
                        if piece_count > 0:
                            logger.info(f"[] ✓ Board loaded with {piece_count} pieces")
                            break
                    
                    if piece_count == 0:
                        logger.warning(f"[] Board still empty after retries")
                        continue
                
                # Check turn
                is_my_turn = self.is_my_turn()
                
                if is_my_turn:
                    no_turn_count = 0
                    logger.info(f"[] ══════ Move {move_count + 1} ({self.my_color.upper()}) ══════")
                    
                    # Get moves
                    all_moves = self.get_all_moves_for_player(board, self.my_color)
                    
                    if not all_moves:
                        logger.warning(f"[] No valid moves available!")
                        time.sleep(1)
                        board = self.read_board_state()
                        all_moves = self.get_all_moves_for_player(board, self.my_color)
                        
                        if not all_moves:
                            logger.error(f"[] Still no moves - game may be over")
                            time.sleep(3)
                            break
                    
                    logger.info(f"[] Found {len(all_moves)} possible moves")
                    
                    # Calculate best move
                    move = self.calculate_best_move_ultra_expert(board, self.my_color)
                    
                    if move:
                        logger.info(f"[] Selected: {move['from']} -> {move['path']} "
                                  f"(type: {move['type']})")
                        
                        if self.make_move(move):
                            move_count += 1
                            consecutive_failed_moves = 0
                            logger.info(f"[] ★ Move {move_count} completed ★")
                            time.sleep(2)
                        else:
                            consecutive_failed_moves += 1
                            logger.error(f"[] ✗ Failed to execute move "
                                       f"(failures: {consecutive_failed_moves})")
                            
                            if consecutive_failed_moves >= 3:
                                logger.error(f"[] Too many failures, breaking")
                                break
                            
                            time.sleep(2)
                    else:
                        logger.error(f"[] AI returned no move")
                        consecutive_failed_moves += 1
                        
                        if consecutive_failed_moves >= 3:
                            break
                        
                        time.sleep(2)
                else:
                    no_turn_count += 1
                    if no_turn_count % 5 == 0:
                        logger.info(f"[] Waiting for turn... ({no_turn_count}s)")
                    time.sleep(1)
                
                if no_turn_count > 60:
                    logger.warning(f"[] Waited 60s, checking game status")
                    if self.check_game_over():
                        break
                    no_turn_count = 0
                
            except StaleElementReferenceException:
                logger.warning(f"[] Stale element, refreshing...")
                self.game_iframe = None
                time.sleep(2)
                continue
            except Exception as e:
                logger.error(f"[] Error in game loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(2)
                
                try:
                    self.driver.switch_to.default_content()
                    if not self.switch_to_game_iframe():
                        logger.error(f"[] Cannot recover")
                        break
                except:
                    break
        
        logger.info(f"[] Game completed after {move_count} moves")
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
    EMAIL = os.getenv('GAME_EMAIL', '9h2qy@comfythings.com')
    PASSWORD = os.getenv('GAME_PASSWORD', '123456')
    
    DIFFICULTY = "medium"  # Expert mode for maximum strength
    
    bot = CheckersUltraExpertBot(difficulty=DIFFICULTY)
    
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
                    if bot.find_and_join_Checkers():
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