import streamlit as st
import random
import time
import json
from streamlit_autorefresh import st_autorefresh

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore

# --- הגדרות עמוד ועיצוב ---
st.set_page_config(page_title="איקס עיגול אולטימטיבי", layout="wide", initial_sidebar_state="expanded")

# הזרקת CSS לעיצוב רספונסיבי ותמיכה בעברית (RTL)
st.markdown("""
    <style>
    /* כיוון כללי לימין-שמאל */
    .stApp {
        direction: rtl;
        text-align: right;
    }
    
    /* התאמת כפתורים למובייל ולמסך מחשב */
    div[data-testid="column"] {
        padding: 1px !important;
        min-width: 0 !important;
    }
    
    /* עיצוב כפתורי המשחק */
    button {
        padding: 0px !important;
        min-height: 35px !important; /* גובה מינימלי קטן יותר למובייל */
        height: 100%;
        font-size: 14px !important;
        font-weight: bold !important;
        margin: 0px !important;
    }
    
    /* צבעים לניצחונות */
    .won-x { background-color: #ffcccc; color: black; display: flex; align-items: center; justify-content: center; font-size: 2em; border: 1px solid #ddd; height: 100px; }
    .won-o { background-color: #ccefff; color: black; display: flex; align-items: center; justify-content: center; font-size: 2em; border: 1px solid #ddd; height: 100px; }
    
    /* סימון הלוח הפעיל */
    .active-board {
        border: 3px solid #FF4B4B;
        border-radius: 8px;
        padding: 3px;
        background-color: rgba(255, 75, 75, 0.05);
    }
    
    /* התאמות למסכים קטנים (מובייל) */
    @media only screen and (max-width: 600px) {
        button {
            min-height: 30px !important;
            font-size: 10px !important;
        }
        .won-x, .won-o {
            height: 80px;
            font-size: 1.5em;
        }
    }
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
    """בדיקת ניצחון בלוח 3x3"""
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
        "game_over": False,
        "last_move_time": time.time(), # לטיימר
        "turn_duration": 30 # שניות לתור
    }

def handle_move(state, big_r, big_c, small_r, small_c):
    if state["game_over"]:
        return False
    
    # בדיקת חוקיות הלוח הגדול
    if state["next_board"] is not None:
        req_r, req_c = state["next_board"]
        if (big_r, big_c) != (req_r, req_c):
            return False
    
    if state["macro_board"][big_r][big_c] != "":
        return False

    if state["board"][big_r][big_c][small_r][small_c] != "":
        return False

    # ביצוע המהלך
    player = state["current_turn"]
    state["board"][big_r][big_c][small_r][small_c] = player

    # בדיקת ניצחון בלוח הקטן
    small_winner = check_win(state["board"][big_r][big_c])
    if small_winner:
        state["macro_board"][big_r][big_c] = small_winner
    
    # בדיקת ניצחון כללי
    global_winner = check_win(state["macro_board"])
    if global_winner:
        state["winner"] = global_winner
        state["game_over"] = True
        return True

    # קביעת הלוח הבא
    target_r, target_c = small_r, small_c
    if state["macro_board"][target_r][target_c] != "" or is_board_full(state["board"][target_r][target_c]):
        state["next_board"] = None
    else:
        state["next_board"] = (target_r, target_c)

    # החלפת תור ואיפוס טיימר
    state["current_turn"] = "O" if player == "X" else "X"
    state["last_move_time"] = time.time()
    return True

# --- AI (מחשב) ---
def get_ai_move(state):
    valid_moves = []
    for br in range(3):
        for bc in range(3):
            if state["next_board"] and (br, bc) != state["next_board"]:
                continue
            if state["macro_board"][br][bc] != "":
                continue
            for sr in range(3):
                for sc in range(3):
                    if state["board"][br][bc][sr][sc] == "":
                        valid_moves.append((br, bc, sr, sc))
    
    if not valid_moves:
        return None

    # 1. נסה לנצח לוח קטן
    for move in valid_moves:
        br, bc, sr, sc = move
        state["board"][br][bc][sr][sc] = "O"
        if check_win(state["board"][br][bc]) == "O":
            state["board"][br][bc][sr][sc] = ""
            return move
        state["board"][br][bc][sr][sc] = ""

    # 2. חסום את היריב
    for move in valid_moves:
        br, bc, sr, sc = move
        state["board"][br][bc][sr][sc] = "X"
        if check_win(state["board"][br][bc]) == "X":
            state["board"][br][bc][sr][sc] = ""
            return move
        state["board"][br][bc][sr][sc] = ""

    return random.choice(valid_moves)

# --- רכיבי ממשק ---

def render_timer():
    """מציג ומנהל את הטיימר"""
    st_state = st.session_state.game_state
    if st_state["game_over"]:
        return

    # רענון אוטומטי כל שנייה כדי שהשעון יזוז
    st_autorefresh(interval=1000, limit=None, key="timer_refresh")

    elapsed = time.time() - st_state["last_move_time"]
    remaining = st_state["turn_duration"] - elapsed
    
    # תצוגת הזמן
    timer_color = "red" if remaining < 5 else "green"
    st.markdown(f"""
        <div style="text-align: center; font-size: 1.2em; font-weight: bold; color: {timer_color}; margin-bottom: 10px;">
            ⏳ זמן נותר: {int(remaining)} שניות
        </div>
    """, unsafe_allow_html=True)

    # טיפול בסיום הזמן (מהלך רנדומלי או העברת תור)
    if remaining <= 0:
        st.toast("הזמן נגמר! מבצע מהלך אקראי...")
        # לוגיקה פשוטה: בחר מהלך רנדומלי חוקי
        ai_move = get_ai_move(st_state) # משתמשים בלוגיקת ה-AI כדי למצוא מהלך חוקי
        if ai_move:
            br, bc, sr, sc = ai_move
            # מבצעים את המהלך עבור השחקן הנוכחי (גם אם הוא אנושי)
            # צריך לוודא שהפונקציה handle_move משתמשת ב-current_turn
            handle_move(st_state, br, bc, sr, sc)
            st.rerun()

def render_board(is_locked=False):
    st_state = st.session_state.game_state
    
    # הצגת הלוח
    # לולאה חיצונית (לוחות גדולים)
    for br in range(3):
        cols = st.columns(3)
        for bc in range(3):
            with cols[bc]:
                # בדיקה אם זה הלוח הפעיל
                is_active = False
                if not st_state["game_over"] and st_state["macro_board"][br][bc] == "":
                    if st_state["next_board"] == (br, bc) or st_state["next_board"] is None:
                        is_active = True
                
                container_class = "active-board" if is_active else ""
                
                winner = st_state["macro_board"][br][bc]
                if winner:
                    color_class = "won-x" if winner == "X" else "won-o"
                    st.markdown(f'<div class="{color_class}">{winner}</div>', unsafe_allow_html=True)
                else:
                    # שימוש ב-container כדי לצייר מסגרת ללוח הפעיל
                    with st.container():
                        if is_active:
                            st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
                        
                        # לוח פנימי 3x3
                        for sr in range(3):
                            sub_cols = st.columns(3)
                            for sc in range(3):
                                cell_val = st_state["board"][br][bc][sr][sc]
                                key = f"{br}-{bc}-{sr}-{sc}"
                                
                                # האם הכפתור פעיל?
                                disabled = is_locked or cell_val != "" or st_state["game_over"]
                                if not disabled and st_state["next_board"] is not None:
                                    if st_state["next_board"] != (br, bc):
                                        disabled = True
                                
                                if sub_cols[sc].button(cell_val if cell_val else " ", key=key, disabled=disabled, use_container_width=True):
                                    handle_move(st_state, br, bc, sr, sc)
                                    st.rerun()
                        
                        if is_active:
                            st.markdown('</div>', unsafe_allow_html=True)

# --- אפליקציה ראשית ---

def main():
    st.title("🏆 איקס עיגול אולטימטיבי")

    # --- סרגל צד (הגדרות) ---
    st.sidebar.header("תפריט משחק")
    
    # שמות שחקנים
    if "player_names" not in st.session_state:
        st.session_state.player_names = {"X": "שחקן X", "O": "שחקן O"}

    with st.sidebar.expander("שמות שחקנים", expanded=True):
        st.session_state.player_names["X"] = st.text_input("שם לשחקן X", st.session_state.player_names["X"])
        st.session_state.player_names["O"] = st.text_input("שם לשחקן O", st.session_state.player_names["O"])

    # בחירת מצב משחק
    modes = ["משחק מקומי (2 שחקנים)", "נגד המחשב"]
    if st.session_state.firebase_enabled:
        modes.append("משחק אונליין")
    else:
        st.sidebar.warning("מצב אונליין לא זמין (חסרים מפתחות Firebase)")
        
    mode = st.sidebar.radio("בחר מצב משחק:", modes)
    
    # הגדרת זמן לתור
    turn_time = st.sidebar.slider("זמן לתור (שניות)", 10, 60, 30)
    
    if st.sidebar.button("התחל משחק חדש", type="primary"):
        st.session_state.game_state = init_game_state()
        st.session_state.game_state["turn_duration"] = turn_time
        st.session_state.online_game_id = None
        st.rerun()

    # אתחול מצב אם חסר
    if "game_state" not in st.session_state:
        st.session_state.game_state = init_game_state()
        st.session_state.game_state["turn_duration"] = turn_time

    current_turn_symbol = st.session_state.game_state['current_turn']
    current_player_name = st.session_state.player_names[current_turn_symbol]

    # --- מצב: מקומי ---
    if mode == "משחק מקומי (2 שחקנים)":
        st.subheader(f"תור: {current_player_name} ({current_turn_symbol})")
        render_timer()
        render_board()
        
        if st.session_state.game_state["winner"]:
            winner_sym = st.session_state.game_state['winner']
            st.success(f"🎉 המנצח הוא: {st.session_state.player_names[winner_sym]}!")

    # --- מצב: נגד המחשב ---
    elif mode == "נגד המחשב":
        st.subheader(f"תור: {current_player_name if current_turn_symbol == 'X' else 'מחשב'}")
        
        # האדם הוא X, המחשב הוא O
        is_ai_turn = current_turn_symbol == "O" and not st.session_state.game_state["game_over"]
        
        if not is_ai_turn:
            render_timer()
        
        render_board(is_locked=is_ai_turn)

        if st.session_state.game_state["winner"]:
            if st.session_state.game_state["winner"] == "X":
                st.balloons()
                st.success(f"כל הכבוד {st.session_state.player_names['X']}, ניצחת!")
            else:
                st.error("המחשב ניצח!")
        
        # תור המחשב
        if is_ai_turn:
            with st.spinner("המחשב חושב..."):
                time.sleep(0.7)
                move = get_ai_move(st.session_state.game_state)
                if move:
                    br, bc, sr, sc = move
                    handle_move(st.session_state.game_state, br, bc, sr, sc)
                    st.rerun()

    # --- מצב: אונליין ---
    elif mode == "משחק אונליין":
        st.subheader("לובי אונליין")
        
        if "online_game_id" not in st.session_state:
            st.session_state.online_game_id = None
            st.session_state.player_side = None

        c1, c2 = st.columns([3, 1])
        game_id_input = c1.text_input("הכנס קוד חדר (למשל: room1)")
        
        if c2.button("הצטרף / צור"):
            if game_id_input:
                st.session_state.online_game_id = game_id_input
                doc_ref = st.session_state.firebase_db.collection("games").document(game_id_input)
                doc = doc_ref.get()
                
                my_name = st.session_state.player_names["X"] # שם זמני לכניסה
                
                if not doc.exists:
                    # יצירת חדר חדש
                    new_state = init_game_state()
                    new_state["turn_duration"] = turn_time
                    doc_ref.set({
                        "data": json.dumps(new_state),
                        "player_x_name": st.session_state.player_names["X"],
                        "player_o_name": "ממתין...",
                        "player_x_joined": True,
                        "player_o_joined": False
                    })
                    st.session_state.player_side = "X"
                    st.toast(f"חדר {game_id_input} נוצר. אתה X.")
                else:
                    # הצטרפות לחדר קיים
                    data = doc.to_dict()
                    if not data.get("player_o_joined"):
                        doc_ref.update({
                            "player_o_joined": True,
                            "player_o_name": st.session_state.player_names["O"] # שולח את השם שהוגדר אצלי כ-O
                        })
                        st.session_state.player_side = "O"
                        st.toast(f"הצטרפת לחדר {game_id_input}. אתה O.")
                    else:
                        st.session_state.player_side = "Spectator"
                        st.warning("החדר מלא. אתה צופה בלבד.")
                st.rerun()

        if st.session_state.online_game_id:
            doc_ref = st.session_state.firebase_db.collection("games").document(st.session_state.online_game_id)
            doc = doc_ref.get()
            
            if doc.exists:
                server_data = doc.to_dict()
                current_server_state = json.loads(server_data["data"])
                
                # סנכרון שמות מהשרת
                p_x = server_data.get("player_x_name", "X")
                p_o = server_data.get("player_o_name", "O")
                
                st.session_state.game_state = current_server_state
                turn = current_server_state["current_turn"]
                me = st.session_state.player_side
                
                # תצוגת סטטוס
                status_cols = st.columns(3)
                status_cols[0].info(f"חדר: {st.session_state.online_game_id}")
                status_cols[1].info(f"אתה: {me}")
                status_cols[2].warning(f"תור: {p_x if turn == 'X' else p_o}")

                # רענון אוטומטי למצב אונליין
                st_autorefresh(interval=2000, key="online_sync")
                
                is_locked = (turn != me) or (me == "Spectator") or current_server_state["game_over"]
                
                # הצגת טיימר (רק ויזואלי באונליין, הניהול מורכב יותר)
                elapsed = time.time() - current_server_state["last_move_time"]
                rem = current_server_state["turn_duration"] - elapsed
                st.caption(f"זמן לתור: {int(rem)} שניות")

                # שמירת מצב לפני שינוי
                state_before = json.dumps(st.session_state.game_state)
                
                render_board(is_locked=is_locked)
                
                state_after = json.dumps(st.session_state.game_state)
                
                if state_before != state_after and not is_locked:
                    doc_ref.update({"data": state_after})
                    st.rerun()
                
                if current_server_state["winner"]:
                    w_name = p_x if current_server_state["winner"] == "X" else p_o
                    st.success(f"המנצח הוא: {w_name}!")

if __name__ == "__main__":
    main()
