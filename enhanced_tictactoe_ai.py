"""
Enhanced Tic-Tac-Toe AI Engine
3x3 board, 3-in-a-row win condition
"""

import time
from typing import List, Tuple, Optional

BOARD_SIZE = 3
EMPTY = None

# Position weights for evaluation (center is best)
POSITION_WEIGHTS = [
    [3, 2, 3],
    [2, 4, 2],
    [3, 2, 3]
]


def get_best_move_advanced(board, player, max_depth=9, time_limit=5):
    """
    Get best move using minimax with alpha-beta pruning
    
    Args:
        board: 3x3 board state
        player: Current player (1 or 2)
        max_depth: Maximum search depth
        time_limit: Time limit in seconds
    
    Returns:
        Tuple (row, col) or None
    """
    start_time = time.time()
    valid_moves = get_valid_moves(board)
    
    if not valid_moves:
        return None
    
    # Quick tactical checks
    win_move = find_winning_move(board, player)
    if win_move:
        return win_move
    
    opponent = 3 - player
    block_move = find_winning_move(board, opponent)
    if block_move:
        return block_move
    
    # Minimax search
    best_move = None
    best_score = float('-inf')
    alpha = float('-inf')
    beta = float('inf')
    
    # Order moves for better pruning
    ordered_moves = order_moves(board, player, valid_moves)
    
    for move in ordered_moves:
        if time.time() - start_time > time_limit:
            break
        
        # Simulate move
        test_board = [row[:] for row in board]
        test_board[move[0]][move[1]] = player
        
        # Minimax
        score = minimax(
            test_board, opponent, max_depth - 1, 
            alpha, beta, False, player, start_time, time_limit
        )
        
        if score > best_score:
            best_score = score
            best_move = move
        
        alpha = max(alpha, best_score)
    
    return best_move if best_move else ordered_moves[0]


def minimax(board, player, depth, alpha, beta, is_maximizing, original_player, start_time, time_limit):
    """Minimax with alpha-beta pruning"""
    
    # Time check
    if time.time() - start_time > time_limit:
        return evaluate_board(board, original_player)
    
    # Terminal conditions
    winner = check_winner(board)
    if winner is not None:
        return 10000 if winner == original_player else -10000
    
    if depth == 0:
        return evaluate_board(board, original_player)
    
    valid_moves = get_valid_moves(board)
    if not valid_moves:
        return evaluate_board(board, original_player)
    
    if is_maximizing:
        max_eval = float('-inf')
        for move in valid_moves:
            test_board = [row[:] for row in board]
            test_board[move[0]][move[1]] = original_player
            
            eval_score = minimax(
                test_board, 3 - original_player, depth - 1, 
                alpha, beta, False, original_player, start_time, time_limit
            )
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for move in valid_moves:
            test_board = [row[:] for row in board]
            test_board[move[0]][move[1]] = player
            
            eval_score = minimax(
                test_board, 3 - player, depth - 1, 
                alpha, beta, True, original_player, start_time, time_limit
            )
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            
            if beta <= alpha:
                break
        return min_eval


def get_valid_moves(board):
    """Get all valid moves (empty cells)"""
    valid_moves = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] is None:
                valid_moves.append((r, c))
    return valid_moves


def find_winning_move(board, player):
    """Find immediate winning move"""
    valid_moves = get_valid_moves(board)
    
    for move in valid_moves:
        test_board = [row[:] for row in board]
        test_board[move[0]][move[1]] = player
        
        if check_winner(test_board) == player:
            return move
    
    return None


def order_moves(board, player, valid_moves):
    """Order moves for better alpha-beta pruning"""
    center_moves = []
    corner_moves = []
    edge_moves = []
    
    for move in valid_moves:
        r, c = move
        # Center (best)
        if r == 1 and c == 1:
            center_moves.append(move)
        # Corners (second best)
        elif (r, c) in [(0, 0), (0, 2), (2, 0), (2, 2)]:
            corner_moves.append(move)
        # Edges (last)
        else:
            edge_moves.append(move)
    
    return center_moves + corner_moves + edge_moves


def evaluate_board(board, player):
    """Evaluate board position"""
    opponent = 3 - player
    score = 0
    
    # Check all possible 3-in-a-row lines
    # Horizontal
    for r in range(BOARD_SIZE):
        line = [board[r][c] for c in range(BOARD_SIZE)]
        score += evaluate_line(line, player, opponent)
    
    # Vertical
    for c in range(BOARD_SIZE):
        line = [board[r][c] for r in range(BOARD_SIZE)]
        score += evaluate_line(line, player, opponent)
    
    # Diagonal (top-left to bottom-right)
    line = [board[i][i] for i in range(BOARD_SIZE)]
    score += evaluate_line(line, player, opponent)
    
    # Diagonal (top-right to bottom-left)
    line = [board[i][BOARD_SIZE - 1 - i] for i in range(BOARD_SIZE)]
    score += evaluate_line(line, player, opponent)
    
    # Position weights
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == player:
                score += POSITION_WEIGHTS[r][c]
            elif board[r][c] == opponent:
                score -= POSITION_WEIGHTS[r][c]
    
    return score


def evaluate_line(line, player, opponent):
    """Evaluate a 3-cell line"""
    player_count = line.count(player)
    opponent_count = line.count(opponent)
    empty_count = line.count(None)
    
    # Win
    if player_count == 3:
        return 1000
    if opponent_count == 3:
        return -1000
    
    # 2-in-a-row with empty (strong threat)
    if player_count == 2 and empty_count == 1:
        return 100
    if opponent_count == 2 and empty_count == 1:
        return -150  # Block opponent wins with higher priority
    
    # 1-in-a-row with two empty
    if player_count == 1 and empty_count == 2:
        return 10
    if opponent_count == 1 and empty_count == 2:
        return -10
    
    return 0


def check_winner(board):
    """Check if there's a winner (3-in-a-row)"""
    
    # Check horizontal
    for r in range(BOARD_SIZE):
        if board[r][0] is not None and board[r][0] == board[r][1] == board[r][2]:
            return board[r][0]
    
    # Check vertical
    for c in range(BOARD_SIZE):
        if board[0][c] is not None and board[0][c] == board[1][c] == board[2][c]:
            return board[0][c]
    
    # Check diagonal (top-left to bottom-right)
    if board[0][0] is not None and board[0][0] == board[1][1] == board[2][2]:
        return board[0][0]
    
    # Check diagonal (top-right to bottom-left)
    if board[0][2] is not None and board[0][2] == board[1][1] == board[2][0]:
        return board[0][2]
    
    return None
