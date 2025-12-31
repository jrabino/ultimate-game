import streamlit as st
import random
import json
import time

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore

# --- הגדרות עמוד ---
st.set_page_config(page_title="איקס עיגול אולטימטיבי", layout="wide", initial_sidebar_state="collapsed")

# --- CSS אגרסיבי לתיקון המובייל ---
st.markdown("""
    <style>
    /* כיוון כללי */
    .stApp {
        direction: rtl;
        text-align: right;
    }

    /* --- תיקון קריטי למובייל: ביטול שבירת שורות --- */
    
    /* מכריח את הקונטיינר של העמודות לא לשבור שורה */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 2px !important; /* רווח קטנטן בין עמודות */
    }

    /* מכריח את העמודות להיות ברוחב שליש בדיוק, גם במובייל */
    div[data-testid="column"] {
        width: 33.33% !important;
        flex: 1 1 33.33% !important;
        min-width: 10px !important; /* מאפשר לעמודה להתכווץ מאוד */
        padding: 0px !important; /* ביטול ריפוד פנימי */
    }

    /* הקטנת הכותרת הראשית במובייל שלא תתפוס את כל המסך */
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* עיצוב כפתורי המשחק - קומפקטיים במיוחד */
    button {
        padding: 0px !important;
        min-height: 35px !important; /* גובה קבוע */
        height: 35px !important;
        width: 100% !important;
        font-size: 14px !important;
        font-weight: bold !important;
        margin: 1px 0px !important; /* רווח אנכי קטן */
        line-height: 1 !important;
        border: 1px solid #ccc !important;
    }
    
    /* הסתרת אלמנטים מיותרים של Streamlit כדי לחסוך מקום */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    
    /* --- עיצוב הלוחות --- */
    
    /* מסגרת ללוח פעיל */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 2px !important;
        margin: 1px !important;
    }
    
    /* התאמות ספציפיות למסכים ממש קטנים (אייפון ישן וכו') */
    @media only screen and (max-width: 400px) {
        button {
            min-height: 28px !important;
            height: 28px !important;
            font-size: 10px !important;
        }
        h1 { font-size: 1.2rem !important; }
        h3 { font-size: 1rem !important; }
    }
    
    /* צבעים לניצחונות */
    .won-box {
        height: 100px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 2.5em;
        font-weight: bold;
        border-radius: 4px;
        width: 100%;
    }
    .won-x { background-color: #ffcccc; color: #cc0000; }
    .won-o { background-color: #ccefff; color: #0066cc; }
    
    </style>
""", unsafe_allow_html=True)

# --- אתחול FIREBASE ---
if "firebase_db" not in st.session_state:
    st.session_state.firebase_db = None
    st.session_state.firebase_enabled = False

def init_firebase():
    if not firebase_admin._apps:
        try:
            if "firebase" in st.secrets:
                key_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)
                st.session_state.firebase_db = firestore.client()
                st.session_state.firebase_enabled = True
            else:
                st.session_state.firebase_enabled = False
        except Exception as e:
            st.session_state.firebase_enabled = False
    else:
        st.session_state.firebase_db = firestore.client()
        st.session_state.firebase_enabled = True

init_firebase()

# --- לוגיקת משחק ---

def check_win(board_grid):
    for i in range(3):
        if board_grid[i][0] == board_grid[i][1] == board_grid[i][2] and board_grid[i][0] != "":
            return board_grid[i][0]
        if board_grid[0][i] == board_grid[1][i] == board_grid[2][i] and board_grid[0][i] != "":
            return board_grid[0][i]
    if board_grid[0][0] == board_grid[1][1] == board_grid[2][2] and board_grid[0][0] != "":
        return board_grid[0][0]
    if board_grid[0][2] == board_grid[1][1] == board_grid[2][0] and board_grid[0][2] != "":
        return board_grid[0][2]
    return None

def is_board_full(board_grid):
    return all(cell != "" for row in board_grid for cell in row)

def init_game_state():
    return {
        "board": [[[["" for _ in range(3)] for _ in range(3)] for _ in range(3)] for _ in range(3)],
        "macro_board": [["" for _ in range(3)] for _ in range(3)],
        "current_turn": "X",
        "next_board": None,
        "winner": None,
        "game_over": False
    }

def handle_move(state, big_r, big_c, small_r, small_c):
    if state["game_over"]: return False
    
    if state["next_board"] is not None:
        req_r, req_c = state["next_board"]
        if (big_r, big_c) != (req_r, req_c): return False
    
    if state["macro_board"][big_r][big_c] != "": return False
    if state["board"][big_r][big_c][small_r][small_c] != "": return False

    player = state["current_turn"]
    state["board"][big_r][big_c][small_r][small_c] = player

    small_winner = check_win(state["board"][big_r][big_c])
    if small_winner:
        state["macro_board"][big_r][big_c] = small_winner
    
    global_winner = check_win(state["macro_board"])
    if global_winner:
        state["winner"] = global_winner
        state["game_over"] = True
        return True

    target_r, target_c = small_r, small_c
    if state["macro_board"][target_r][target_c] != "" or is_board_full(state["board"][target_r][target_c]):
        state["next_board"] = None
    else:
        state["next_board"] = (target_r, target_c)

    state["current_turn"] = "O" if player == "X" else "X"
    return True

# --- AI ---
def get_ai_move(state):
    valid_moves = []
    for br in range(3):
        for bc in range(3):
            if state["next_board"] and (br, bc) != state["next_board"]: continue
            if state["macro_board"][br][bc] != "": continue
            for sr in range(3):
                for sc in range(3):
                    if state["board"][br][bc][sr][sc] == "":
                        valid_moves.append((br, bc, sr, sc))
    
    if not valid_moves: return None

    # 1. Win small
    for move in valid_moves:
        br, bc, sr, sc = move
        state["board"][br][bc][sr][sc] = "O"
        if check_win(state["board"][br][bc]) == "O":
            state["board"][br][bc][sr][sc] = ""
            return move
        state["board"][br][bc][sr][sc] = ""

    # 2. Block
    for move in valid_moves:
        br, bc, sr, sc = move
        state["board"][br][bc][sr][sc] = "X"
        if check_win(state["board"][br][bc]) == "X":
            state["board"][br][bc][sr][sc] = ""
            return move
        state["board"][br][bc][sr][sc] = ""

    return random.choice(valid_moves)

# --- רכיבי ממשק ---

def render_board(is_locked=False):
    st_state = st.session_state.game_state
    
    # לולאה חיצונית: 3 שורות של לוחות גדולים
    for br in range(3):
        # שימוש ב-gap="small" כדי לצמצם רווחים
        big_cols = st.columns(3, gap="small")
        
        for bc in range(3):
            with big_cols[bc]:
                # בדיקת סטטוס לוח
                is_active = False
                if not st_state["game_over"] and st_state["macro_board"][br][bc] == "":
                    if st_state["next_board"] == (br, bc) or st_state["next_board"] is None:
                        is_active = True
                
                winner = st_state["macro_board"][br][bc]
                
                # אם הלוח פעיל, נצייר מסגרת בולטת בעזרת st.container
                # אם לא, מסגרת רגילה
                
                # טריק: אם הלוח פעיל, נוסיף אימוג'י קטן מעליו כדי לסמן אותו ויזואלית בלי לתפוס מקום
                if is_active:
                    st.markdown("<div style='text-align:center; line-height:1; font-size:10px;'>🟢</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True) # רווח ריק לשמירה על גובה אחיד

                with st.container(border=True):
                    if winner:
                        color_class = "won-x" if winner == "X" else "won-o"
                        st.markdown(f'<div class="won-box {color_class}">{winner}</div>', unsafe_allow_html=True)
                    else:
                        # לוח פנימי 3X3
                        for sr in range(3):
                            # כאן ה-CSS שלנו יכריח את העמודות האלו להיות בשורה אחת
                            row_cols = st.columns(3, gap="small")
                            for sc in range(3):
                                cell_val = st_state["board"][br][bc][sr][sc]
                                key = f"{br}-{bc}-{sr}-{sc}"
                                
                                disabled = is_locked or cell_val != "" or st_state["game_over"] or (not is_active and st_state["next_board"] is not None)
                                
                                # אם הכפתור לא שייך ללוח הפעיל, נציג אותו כלא זמין
                                if row_cols[sc].button(cell_val if cell_val else " ", key=key, disabled=disabled):
                                    handle_move(st_state, br, bc, sr, sc)
                                    st.rerun()

# --- אפליקציה ראשית ---

def main():
    st.title("איקס עיגול אולטימטיבי 🏆")

    # --- סרגל צד ---
    st.sidebar.header("תפריט")
    
    if "player_names" not in st.session_state:
        st.session_state.player_names = {"X": "שחקן X", "O": "שחקן O"}

    with st.sidebar.expander("שמות שחקנים"):
        st.session_state.player_names["X"] = st.text_input("שם X", st.session_state.player_names["X"])
        st.session_state.player_names["O"] = st.text_input("שם O", st.session_state.player_names["O"])

    modes = ["מקומי (2 שחקנים)", "נגד המחשב"]
    if st.session_state.firebase_enabled:
        modes.append("אונליין")
    
    mode = st.sidebar.radio("מצב משחק:", modes)
    
    if st.sidebar.button("משחק חדש", type="primary"):
        st.session_state.game_state = init_game_state()
        st.session_state.online_game_id = None
        st.rerun()

    if "game_state" not in st.session_state:
        st.session_state.game_state = init_game_state()

    # --- תצוגת סטטוס קומפקטית ---
    turn = st.session_state.game_state['current_turn']
    name = st.session_state.player_names[turn]
    
    # שימוש ב-columns כדי שהסטטוס לא יתפוס גובה רב
    c1, c2 = st.columns([2, 1])
    c1.info(f"תור: {name} ({turn})")
    
    if st.session_state.game_state["next_board"]:
        c2.warning("שחק בלוח המסומן 🟢")
    else:
        c2.success("בחירה חופשית!")

    # --- לוגיקת מצבים ---
    
    if mode == "מקומי (2 שחקנים)":
        render_board()
        if st.session_state.game_state["winner"]:
            w = st.session_state.game_state['winner']
            st.balloons()
            st.success(f"המנצח: {st.session_state.player_names[w]}!")

    elif mode == "נגד המחשב":
        is_ai_turn = turn == "O" and not st.session_state.game_state["game_over"]
        render_board(is_locked=is_ai_turn)

        if st.session_state.game_state["winner"]:
            if st.session_state.game_state["winner"] == "X":
                st.balloons()
                st.success("ניצחת!")
            else:
                st.error("המחשב ניצח!")
        
        if is_ai_turn:
            with st.spinner("..."):
                time.sleep(0.3)
                move = get_ai_move(st.session_state.game_state)
                if move:
                    br, bc, sr, sc = move
                    handle_move(st.session_state.game_state, br, bc, sr, sc)
                    st.rerun()

    elif mode == "אונליין":
        if not st.session_state.online_game_id:
            code = st.text_input("קוד חדר:")
            if st.button("כנס"):
                if code:
                    st.session_state.online_game_id = code
                    doc_ref = st.session_state.firebase_db.collection("games").document(code)
                    doc = doc_ref.get()
                    if not doc.exists:
                        new_state = init_game_state()
                        doc_ref.set({
                            "data": json.dumps(new_state),
                            "player_x_name": st.session_state.player_names["X"],
                            "player_o_name": "...",
                            "player_x_joined": True,
                            "player_o_joined": False
                        })
                        st.session_state.player_side = "X"
                    else:
                        data = doc.to_dict()
                        if not data.get("player_o_joined"):
                            doc_ref.update({"player_o_joined": True, "player_o_name": st.session_state.player_names["O"]})
                            st.session_state.player_side = "O"
                        else:
                            st.session_state.player_side = "Spectator"
                    st.rerun()
        else:
            if st.button("יציאה"):
                st.session_state.online_game_id = None
                st.rerun()
            
            doc_ref = st.session_state.firebase_db.collection("games").document(st.session_state.online_game_id)
            doc = doc_ref.get()
            if doc.exists:
                server_data = doc.to_dict()
                current_server_state = json.loads(server_data["data"])
                st.session_state.game_state = current_server_state
                
                me = st.session_state.player_side
                turn = current_server_state["current_turn"]
                
                if st.button("🔄 רענן"): st.rerun()
                
                is_locked = (turn != me) or (me == "Spectator") or current_server_state["game_over"]
                
                state_before = json.dumps(st.session_state.game_state)
                render_board(is_locked=is_locked)
                state_after = json.dumps(st.session_state.game_state)
                
                if state_before != state_after and not is_locked:
                    doc_ref.update({"data": state_after})
                    st.rerun()

if __name__ == "__main__":
    main()
