import streamlit as st
import random
import json
import time

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore

# --- הגדרות עמוד ועיצוב ---
st.set_page_config(page_title="איקס עיגול אולטימטיבי", layout="wide", initial_sidebar_state="expanded")

# הזרקת CSS לעיצוב רספונסיבי כפוי (Grid) ותמיכה בעברית
st.markdown("""
    <style>
    /* כיוון כללי לימין-שמאל */
    .stApp {
        direction: rtl;
        text-align: right;
    }
    
    /* --- תיקון קריטי למובייל: כפיית תצוגת גריד --- */
    /* זה מכריח את העמודות בתוך הלוח לא להישבר לשורות במובייל */
    div[data-testid="column"] {
        width: 33.33% !important;
        flex: 1 1 33.33% !important;
        min-width: 0 !important;
        padding: 1px !important;
    }

    /* עיצוב כפתורי המשחק */
    button {
        padding: 0px !important;
        min-height: 40px !important;
        height: 100%;
        width: 100%;
        font-size: 16px !important;
        font-weight: bold !important;
        margin: 0px !important;
        border-radius: 4px !important;
        border: 1px solid #ccc !important;
    }
    
    /* צבעים לניצחונות בלוחות קטנים */
    .won-box {
        height: 120px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 3em;
        font-weight: bold;
        border-radius: 8px;
    }
    .won-x { background-color: #ffcccc; color: #cc0000; }
    .won-o { background-color: #ccefff; color: #0066cc; }
    
    /* --- סימון לוח פעיל --- */
    /* אנו נשתמש ב-st.container עם border, אבל נוסיף צבע רקע דרך CSS ספציפי אם צריך */
    
    /* הסתרת אלמנטים מיותרים של הסטרים-ליט כדי לחסוך מקום */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 1rem;
    }
    
    /* התאמות למסכים קטנים מאוד */
    @media only screen and (max-width: 400px) {
        button {
            min-height: 30px !important;
            font-size: 12px !important;
        }
        .won-box {
            height: 90px;
            font-size: 2em;
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
    # שורות ועמודות
    for i in range(3):
        if board_grid[i][0] == board_grid[i][1] == board_grid[i][2] and board_grid[i][0] != "":
            return board_grid[i][0]
        if board_grid[0][i] == board_grid[1][i] == board_grid[2][i] and board_grid[0][i] != "":
            return board_grid[0][i]
    # אלכסונים
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
        "next_board": None, # None = בחירה חופשית
        "winner": None,
        "game_over": False
    }

def handle_move(state, big_r, big_c, small_r, small_c):
    if state["game_over"]:
        return False
    
    # בדיקת חוקיות הלוח הגדול
    if state["next_board"] is not None:
        req_r, req_c = state["next_board"]
        if (big_r, big_c) != (req_r, req_c):
            return False
    
    # אם הלוח הגדול כבר מנוצח, אי אפשר לשחק בו (אלא אם חוקים אחרים, כאן זה חוסם)
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
    
    # אם הלוח שאליו נשלחנו מלא או מנוצח -> בחירה חופשית
    if state["macro_board"][target_r][target_c] != "" or is_board_full(state["board"][target_r][target_c]):
        state["next_board"] = None
    else:
        state["next_board"] = (target_r, target_c)

    # החלפת תור
    state["current_turn"] = "O" if player == "X" else "X"
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

def render_board(is_locked=False):
    st_state = st.session_state.game_state
    
    # אנו בונים את הגריד הראשי ידנית כדי לשלוט בעיצוב
    # לולאה חיצונית: שורות של לוחות גדולים
    for br in range(3):
        # יצירת 3 עמודות ללוחות הגדולים
        big_cols = st.columns(3)
        
        for bc in range(3):
            with big_cols[bc]:
                # בדיקה האם הלוח הזה פעיל
                is_active_board = False
                if not st_state["game_over"] and st_state["macro_board"][br][bc] == "":
                    if st_state["next_board"] == (br, bc) or st_state["next_board"] is None:
                        is_active_board = True
                
                # קביעת כותרת או סטטוס ללוח
                status_text = "🔒"
                if is_active_board:
                    status_text = "🟢 פעיל"
                elif st_state["macro_board"][br][bc] != "":
                    status_text = "🏆 הושלם"
                
                # שימוש ב-container עם מסגרת כדי ליצור הפרדה ברורה
                # אם הלוח פעיל, נשתמש בטריק של כותרת צבעונית או פשוט נסמוך על הכיתוב
                border_color = "red" if is_active_board else "grey"
                
                with st.container(border=True):
                    # כותרת קטנה מעל כל לוח 3X3
                    if is_active_board:
                        st.markdown(f"<div style='text-align:center; color:green; font-size:0.8em; font-weight:bold;'>{status_text}</div>", unsafe_allow_html=True)
                    
                    winner = st_state["macro_board"][br][bc]
                    
                    if winner:
                        # הצגת ריבוע ניצחון גדול
                        color_class = "won-x" if winner == "X" else "won-o"
                        st.markdown(f'<div class="won-box {color_class}">{winner}</div>', unsafe_allow_html=True)
                    else:
                        # ציור הלוח הקטן 3X3
                        for sr in range(3):
                            # כאן הקסם: העמודות הפנימיות יקבלו את ה-CSS של 33% רוחב
                            row_cols = st.columns(3)
                            for sc in range(3):
                                cell_val = st_state["board"][br][bc][sr][sc]
                                key = f"{br}-{bc}-{sr}-{sc}"
                                
                                # האם הכפתור פעיל?
                                disabled = is_locked or cell_val != "" or st_state["game_over"] or not is_active_board
                                
                                # אם הכפתור לא פעיל, נציג אותו אבל כבוי
                                # אם הוא פעיל, הוא יהיה לחיץ
                                
                                if row_cols[sc].button(cell_val if cell_val else " ", key=key, disabled=disabled, use_container_width=True):
                                    handle_move(st_state, br, bc, sr, sc)
                                    st.rerun()

# --- אפליקציה ראשית ---

def main():
    st.title("🏆 איקס עיגול אולטימטיבי")

    # --- סרגל צד (הגדרות) ---
    st.sidebar.header("תפריט משחק")
    
    # שמות שחקנים
    if "player_names" not in st.session_state:
        st.session_state.player_names = {"X": "שחקן X", "O": "שחקן O"}

    with st.sidebar.expander("שמות שחקנים", expanded=False):
        st.session_state.player_names["X"] = st.text_input("שם לשחקן X", st.session_state.player_names["X"])
        st.session_state.player_names["O"] = st.text_input("שם לשחקן O", st.session_state.player_names["O"])

    # בחירת מצב משחק
    modes = ["משחק מקומי (2 שחקנים)", "נגד המחשב"]
    if st.session_state.firebase_enabled:
        modes.append("משחק אונליין")
    else:
        st.sidebar.warning("מצב אונליין לא זמין (חסרים מפתחות)")
        
    mode = st.sidebar.radio("בחר מצב משחק:", modes)
    
    if st.sidebar.button("התחל משחק חדש", type="primary"):
        st.session_state.game_state = init_game_state()
        st.session_state.online_game_id = None
        st.rerun()

    # אתחול מצב אם חסר
    if "game_state" not in st.session_state:
        st.session_state.game_state = init_game_state()

    current_turn_symbol = st.session_state.game_state['current_turn']
    current_player_name = st.session_state.player_names[current_turn_symbol]

    # --- תצוגת סטטוס עליונה ---
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.subheader(f"תור: {current_player_name} ({current_turn_symbol})")
    with status_col2:
        if st.session_state.game_state["next_board"]:
            r, c = st.session_state.game_state["next_board"]
            # המרה לטקסט ידידותי (למשל: עליון-שמאל)
            row_names = ["עליון", "אמצע", "תחתון"]
            col_names = ["שמאל", "מרכז", "ימין"]
            st.info(f"יש לשחק בלוח: {row_names[r]}-{col_names[c]}")
        else:
            st.success("בחירה חופשית! שחק בכל לוח פנוי.")

    # --- מצב: מקומי ---
    if mode == "משחק מקומי (2 שחקנים)":
        render_board()
        
        if st.session_state.game_state["winner"]:
            winner_sym = st.session_state.game_state['winner']
            st.balloons()
            st.success(f"🎉 המנצח הוא: {st.session_state.player_names[winner_sym]}!")

    # --- מצב: נגד המחשב ---
    elif mode == "נגד המחשב":
        # האדם הוא X, המחשב הוא O
        is_ai_turn = current_turn_symbol == "O" and not st.session_state.game_state["game_over"]
        
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
                time.sleep(0.5)
                move = get_ai_move(st.session_state.game_state)
                if move:
                    br, bc, sr, sc = move
                    handle_move(st.session_state.game_state, br, bc, sr, sc)
                    st.rerun()

    # --- מצב: אונליין ---
    elif mode == "משחק אונליין":
        st.markdown("---")
        if "online_game_id" not in st.session_state:
            st.session_state.online_game_id = None
            st.session_state.player_side = None

        if not st.session_state.online_game_id:
            c1, c2 = st.columns([3, 1])
            game_id_input = c1.text_input("הכנס קוד חדר (למשל: room1)")
            if c2.button("הצטרף / צור"):
                if game_id_input:
                    st.session_state.online_game_id = game_id_input
                    doc_ref = st.session_state.firebase_db.collection("games").document(game_id_input)
                    doc = doc_ref.get()
                    
                    if not doc.exists:
                        # יצירת חדר חדש
                        new_state = init_game_state()
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
                        # הצטרפות
                        data = doc.to_dict()
                        if not data.get("player_o_joined"):
                            doc_ref.update({
                                "player_o_joined": True,
                                "player_o_name": st.session_state.player_names["O"]
                            })
                            st.session_state.player_side = "O"
                            st.toast(f"הצטרפת לחדר {game_id_input}. אתה O.")
                        else:
                            st.session_state.player_side = "Spectator"
                            st.warning("החדר מלא. אתה צופה בלבד.")
                    st.rerun()

        else:
            # משחק פעיל אונליין
            if st.button("יציאה מהחדר"):
                st.session_state.online_game_id = None
                st.rerun()

            doc_ref = st.session_state.firebase_db.collection("games").document(st.session_state.online_game_id)
            doc = doc_ref.get()
            
            if doc.exists:
                server_data = doc.to_dict()
                current_server_state = json.loads(server_data["data"])
                
                p_x = server_data.get("player_x_name", "X")
                p_o = server_data.get("player_o_name", "O")
                
                st.session_state.game_state = current_server_state
                turn = current_server_state["current_turn"]
                me = st.session_state.player_side
                
                st.info(f"חדר: {st.session_state.online_game_id} | אתה: {me} | יריב: {p_o if me=='X' else p_x}")
                
                # כפתור רענון ידני (במקום אוטומטי כבד)
                if st.button("🔄 רענן לוח"):
                    st.rerun()

                is_locked = (turn != me) or (me == "Spectator") or current_server_state["game_over"]
                
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
