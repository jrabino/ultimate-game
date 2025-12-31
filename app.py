import streamlit as st
import random
import time
import json

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="Ultimate Tic-Tac-Toe", layout="wide")

# --- FIREBASE INITIALIZATION ---
# We use a singleton pattern to ensure Firebase is only initialized once.
if "firebase_db" not in st.session_state:
    st.session_state.firebase_db = None
    st.session_state.firebase_enabled = False

def init_firebase():
    """Attempts to initialize Firebase from st.secrets."""
    if not firebase_admin._apps:
        try:
            if "firebase" in st.secrets:
                # Convert Streamlit secrets (AtribDict) to a standard dict
                key_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)
                st.session_state.firebase_db = firestore.client()
                st.session_state.firebase_enabled = True
            else:
                st.session_state.firebase_enabled = False
        except Exception as e:
            st.error(f"Firebase initialization failed: {e}")
            st.session_state.firebase_enabled = False
    else:
        # Already initialized
        st.session_state.firebase_db = firestore.client()
        st.session_state.firebase_enabled = True

init_firebase()

# --- GAME LOGIC ENGINE ---

def check_win(board_grid):
    """Checks for a win in a 3x3 grid. Returns 'X', 'O', or None."""
    # Rows & Cols
    for i in range(3):
        if board_grid[i][0] == board_grid[i][1] == board_grid[i][2] and board_grid[i][0] != "":
            return board_grid[i][0]
        if board_grid[0][i] == board_grid[1][i] == board_grid[2][i] and board_grid[0][i] != "":
            return board_grid[0][i]
    # Diagonals
    if board_grid[0][0] == board_grid[1][1] == board_grid[2][2] and board_grid[0][0] != "":
        return board_grid[0][0]
    if board_grid[0][2] == board_grid[1][1] == board_grid[2][0] and board_grid[0][2] != "":
        return board_grid[0][2]
    return None

def is_board_full(board_grid):
    return all(cell != "" for row in board_grid for cell in row)

def init_game_state():
    """Returns a fresh game state dictionary."""
    return {
        # 9x9 grid represented as 3x3 list of 3x3 lists
        # board[big_row][big_col][small_row][small_col]
        "board": [[[["" for _ in range(3)] for _ in range(3)] for _ in range(3)] for _ in range(3)],
        "macro_board": [["" for _ in range(3)] for _ in range(3)], # Tracks winners of big boards
        "current_turn": "X",
        "next_board": None, # Tuple (r, c) or None (Free choice)
        "winner": None,
        "game_over": False
    }

def handle_move(state, big_r, big_c, small_r, small_c):
    """Updates the state based on a move. Returns True if move was valid."""
    
    # 1. Validate Move
    if state["game_over"]:
        return False
    
    # Check if move is allowed in this big board
    if state["next_board"] is not None:
        req_r, req_c = state["next_board"]
        if (big_r, big_c) != (req_r, req_c):
            return False
    
    # Check if big board is already won (unless free choice allowed logic varies, 
    # but standard rules say you can't play in a won board unless sent there, 
    # and if sent there and it's full/won, you get free choice. 
    # Here we assume if you are sent to a won board, you get free choice immediately, handled below).
    if state["macro_board"][big_r][big_c] != "":
        return False

    # Check if cell is empty
    if state["board"][big_r][big_c][small_r][small_c] != "":
        return False

    # 2. Apply Move
    player = state["current_turn"]
    state["board"][big_r][big_c][small_r][small_c] = player

    # 3. Check Small Board Win
    small_winner = check_win(state["board"][big_r][big_c])
    if small_winner:
        state["macro_board"][big_r][big_c] = small_winner
    
    # 4. Check Global Win
    global_winner = check_win(state["macro_board"])
    if global_winner:
        state["winner"] = global_winner
        state["game_over"] = True
        return True

    # 5. Determine Next Target Board
    # The move was at small_r, small_c. Opponent must play at Big Board small_r, small_c
    target_r, target_c = small_r, small_c
    
    # If target board is already won or full, Free Choice
    if state["macro_board"][target_r][target_c] != "" or is_board_full(state["board"][target_r][target_c]):
        state["next_board"] = None
    else:
        state["next_board"] = (target_r, target_c)

    # 6. Switch Turn
    state["current_turn"] = "O" if player == "X" else "X"
    return True

# --- AI LOGIC ---

def get_ai_move(state):
    """Basic AI: Win Small > Block Small > Random Valid."""
    valid_moves = []
    
    # Identify all valid moves
    for br in range(3):
        for bc in range(3):
            # Filter by constraint
            if state["next_board"] and (br, bc) != state["next_board"]:
                continue
            # Filter by won boards
            if state["macro_board"][br][bc] != "":
                continue
            
            for sr in range(3):
                for sc in range(3):
                    if state["board"][br][bc][sr][sc] == "":
                        valid_moves.append((br, bc, sr, sc))
    
    if not valid_moves:
        return None

    # Heuristic 1: Take a move that wins a small board
    for move in valid_moves:
        br, bc, sr, sc = move
        # Simulate
        state["board"][br][bc][sr][sc] = "O"
        if check_win(state["board"][br][bc]) == "O":
            state["board"][br][bc][sr][sc] = "" # Undo
            return move
        state["board"][br][bc][sr][sc] = "" # Undo

    # Heuristic 2: Block opponent from winning a small board
    for move in valid_moves:
        br, bc, sr, sc = move
        state["board"][br][bc][sr][sc] = "X" # Pretend we are X
        if check_win(state["board"][br][bc]) == "X":
            state["board"][br][bc][sr][sc] = "" # Undo
            return move
        state["board"][br][bc][sr][sc] = "" # Undo

    # Heuristic 3: Random
    return random.choice(valid_moves)

# --- UI COMPONENTS ---

def render_board(is_locked=False):
    """Renders the 9x9 grid."""
    st_state = st.session_state.game_state
    
    # CSS for styling
    st.markdown("""
        <style>
        div[data-testid="column"] { padding: 0px; }
        button { padding: 0px !important; min-height: 40px !important; }
        .won-x { background-color: #ffcccc; text-align: center; font-weight: bold; }
        .won-o { background-color: #ccefff; text-align: center; font-weight: bold; }
        .active-board { border: 2px solid #FF4B4B; padding: 5px; border-radius: 5px; }
        </style>
    """, unsafe_allow_html=True)

    # Outer Grid (3x3 Big Boards)
    for br in range(3):
        cols = st.columns(3)
        for bc in range(3):
            with cols[bc]:
                # Visual Indicator for Active Board or Won Board
                container_class = ""
                if st_state["next_board"] == (br, bc) or (st_state["next_board"] is None and st_state["macro_board"][br][bc] == "" and not st_state["game_over"]):
                    container_class = "active-board"
                
                # If board is won, show big overlay (simulated via markdown)
                winner = st_state["macro_board"][br][bc]
                if winner:
                    color = "#ffcccc" if winner == "X" else "#ccefff"
                    st.markdown(f"""
                        <div style="height: 150px; background-color: {color}; display: flex; 
                        align-items: center; justify-content: center; font-size: 3em; border: 1px solid #ddd;">
                        {winner}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    # Render 3x3 Small Grid
                    with st.container(border=True):
                        if container_class:
                            st.caption("Target")
                        for sr in range(3):
                            sub_cols = st.columns(3)
                            for sc in range(3):
                                cell_val = st_state["board"][br][bc][sr][sc]
                                key = f"{br}-{bc}-{sr}-{sc}"
                                
                                # Disable logic
                                disabled = is_locked or cell_val != "" or st_state["game_over"]
                                if not disabled and st_state["next_board"] is not None:
                                    if st_state["next_board"] != (br, bc):
                                        disabled = True
                                
                                if sub_cols[sc].button(cell_val if cell_val else " ", key=key, disabled=disabled, use_container_width=True):
                                    handle_move(st_state, br, bc, sr, sc)
                                    st.rerun()

# --- MAIN APP ---

def main():
    st.title("Ultimate Tic-Tac-Toe 🎮")

    # Sidebar Menu
    st.sidebar.header("Game Menu")
    
    # Mode Selection
    modes = ["Local Multiplayer", "Vs Computer"]
    if st.session_state.firebase_enabled:
        modes.append("Online Multiplayer")
    else:
        st.sidebar.warning("Online mode disabled. Configure Firebase secrets.")
        
    mode = st.sidebar.radio("Select Mode", modes)
    
    if st.sidebar.button("Reset Game"):
        st.session_state.game_state = init_game_state()
        st.session_state.online_game_id = None
        st.rerun()

    # Initialize State if missing
    if "game_state" not in st.session_state:
        st.session_state.game_state = init_game_state()

    # --- MODE: LOCAL ---
    if mode == "Local Multiplayer":
        st.subheader(f"Local Mode: Player {st.session_state.game_state['current_turn']}'s Turn")
        render_board()
        
        if st.session_state.game_state["winner"]:
            st.success(f"Player {st.session_state.game_state['winner']} Wins!")

    # --- MODE: VS COMPUTER ---
    elif mode == "Vs Computer":
        st.subheader(f"Vs AI: Player {st.session_state.game_state['current_turn']}'s Turn")
        
        # Human is X, AI is O
        is_ai_turn = st.session_state.game_state["current_turn"] == "O" and not st.session_state.game_state["game_over"]
        
        render_board(is_locked=is_ai_turn)

        if st.session_state.game_state["winner"]:
            if st.session_state.game_state["winner"] == "X":
                st.success("You Win!")
            else:
                st.error("Computer Wins!")
        
        # AI Move Logic
        if is_ai_turn:
            with st.spinner("AI is thinking..."):
                time.sleep(0.5) # UX delay
                move = get_ai_move(st.session_state.game_state)
                if move:
                    br, bc, sr, sc = move
                    handle_move(st.session_state.game_state, br, bc, sr, sc)
                    st.rerun()

    # --- MODE: ONLINE ---
    elif mode == "Online Multiplayer":
        st.subheader("Online Lobby")
        
        if "online_game_id" not in st.session_state:
            st.session_state.online_game_id = None
            st.session_state.player_side = None

        # Lobby UI
        c1, c2 = st.columns(2)
        game_id_input = c1.text_input("Enter Game ID (e.g., 'room1')")
        
        if c2.button("Join / Create"):
            if game_id_input:
                st.session_state.online_game_id = game_id_input
                # Fetch or Create
                doc_ref = st.session_state.firebase_db.collection("games").document(game_id_input)
                doc = doc_ref.get()
                if not doc.exists:
                    # Create new
                    new_state = init_game_state()
                    # Flatten board for Firestore (Firestore doesn't like deeply nested lists sometimes, but JSON dump is safer)
                    doc_ref.set({
                        "data": json.dumps(new_state),
                        "player_x_joined": True,
                        "player_o_joined": False
                    })
                    st.session_state.player_side = "X"
                    st.toast(f"Created Room {game_id_input}. You are X.")
                else:
                    # Join existing
                    data = doc.to_dict()
                    if not data.get("player_o_joined"):
                        doc_ref.update({"player_o_joined": True})
                        st.session_state.player_side = "O"
                        st.toast(f"Joined Room {game_id_input}. You are O.")
                    else:
                        # Rejoining or spectator
                        st.session_state.player_side = "Spectator"
                        st.warning("Room full. Watching as Spectator.")
                st.rerun()

        # Online Game Loop
        if st.session_state.online_game_id:
            doc_ref = st.session_state.firebase_db.collection("games").document(st.session_state.online_game_id)
            doc = doc_ref.get()
            
            if doc.exists:
                server_data = doc.to_dict()
                # Load state from JSON
                current_server_state = json.loads(server_data["data"])
                
                # Sync local state for rendering
                st.session_state.game_state = current_server_state
                
                turn = current_server_state["current_turn"]
                me = st.session_state.player_side
                
                st.write(f"Room: **{st.session_state.online_game_id}** | You are: **{me}** | Turn: **{turn}**")
                
                # Auto-refresh mechanism (Manual button + Auto-rerun trick)
                if st.button("Refresh Game State"):
                    st.rerun()
                
                # Determine if locked
                is_locked = (turn != me) or (me == "Spectator") or current_server_state["game_over"]
                
                # We need to intercept the render_board clicks. 
                # Since render_board calls handle_move locally, we need to wrap it or modify it.
                # For simplicity in this architecture, we let render_board update local state, 
                # then we detect the change and push to Firebase.
                
                # Snapshot before render
                state_before = json.dumps(st.session_state.game_state)
                
                render_board(is_locked=is_locked)
                
                # Snapshot after render (if button clicked inside render_board, script reruns immediately)
                # So we actually need to handle the push *inside* the button callback logic or 
                # check if we are in a post-interaction state.
                
                # However, Streamlit reruns the whole script on button click.
                # The `render_board` function calls `handle_move`.
                # If `handle_move` returns True, the local state is updated.
                # We need to push that to Firebase.
                
                state_after = json.dumps(st.session_state.game_state)
                
                if state_before != state_after and not is_locked:
                    # Push update
                    doc_ref.update({"data": state_after})
                    st.rerun()
                
                if current_server_state["winner"]:
                    st.success(f"Winner: {current_server_state['winner']}")

            else:
                st.error("Game room deleted or invalid.")

if __name__ == "__main__":
    main()
