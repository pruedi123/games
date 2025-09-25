# memory_match.py — Streamlit Memory Matching Game (preschool-friendly)
import random, time
import streamlit as st

st.set_page_config(page_title="Memory Match", page_icon="🧠", layout="centered")

# ------------------------------- THEMES ---------------------------------
THEMES = {
    "Animals": ["🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🦁","🐷","🐸","🐵","🐮","🐯","🦒"],
    "Shapes & Colors": ["🔴","🟠","🟡","🟢","🔵","🟣","🟤","⚫️","⚪️","🟥","🟧","🟨","🟩","🟦","🟪","⬛️"],
    "Smiles": ["😀","😃","😄","😁","😆","😊","🙂","😉","😎","🤩","🥳","🤗","🤠","😺","😸","😹"],
}

# ------------------------------- SIDEBAR --------------------------------
st.sidebar.header("Grown-Up Settings")
theme = st.sidebar.selectbox("Card theme", list(THEMES.keys()), index=0)
pairs = st.sidebar.slider("Number of pairs", 3, 8, 6, help="Start small; increase as they improve.")
show_score = st.sidebar.checkbox("Show move counter", value=True)
peek_seconds = st.sidebar.slider("Peek time (seconds)", 2, 5, 3)

col_sb1, col_sb2 = st.sidebar.columns(2)
reset_clicked = col_sb1.button("New game")
peek_clicked = col_sb2.button("Show all (peek)")

# ------------------------------ STATE -----------------------------------
def new_game():
    symbols = random.sample(THEMES[theme], pairs)
    deck = symbols * 2
    random.shuffle(deck)
    st.session_state.deck = deck
    st.session_state.revealed = set()     # indexes currently face-up (max 2)
    st.session_state.matched = set()      # indexes permanently solved
    st.session_state.moves = 0
    st.session_state.pending_hide_at = 0  # timestamp when to hide a mismatch
    st.session_state.started_at = time.time()
    st.session_state.finished = False

if "deck" not in st.session_state or reset_clicked:
    new_game()

# Quick handles
deck         = st.session_state.deck
revealed     = st.session_state.revealed
matched      = st.session_state.matched
moves        = st.session_state.moves
pending_hide = st.session_state.pending_hide_at

# Handle peek (show everything briefly)
def do_peek(seconds: int):
    st.session_state._peek_until = time.time() + seconds

if peek_clicked:
    do_peek(peek_seconds)

peek_until = st.session_state.get("_peek_until", 0)
now = time.time()
peeking = now < peek_until

# If a mismatch is pending and time has passed, flip back
if pending_hide and now >= pending_hide:
    st.session_state.revealed = set()
    st.session_state.pending_hide_at = 0
    revealed = st.session_state.revealed

# ------------------------------ UI HEADERS ------------------------------
st.title("🧠 Memory Match")
st.caption("Tap two cards to find a pair!")

if show_score:
    st.markdown(f"**Moves:** {moves}")

# ------------------------------ GRID LAYOUT -----------------------------
# Choose a friendly grid: 3–4 columns keeps buttons big for little fingers
cols = 4 if pairs >= 7 else 3
rows = (len(deck) + cols - 1) // cols

def card_face(i: int) -> str:
    if peeking or (i in revealed) or (i in matched):
        return deck[i]
    return "❓"

def on_card_click(i: int):
    if i in matched or i in revealed or st.session_state.finished:
        return

    # If a mismatch is still showing, ignore taps until it flips back
    if st.session_state.pending_hide_at:
        return

    revealed.add(i)

    # When two cards are up, check match
    if len(revealed) == 2:
        st.session_state.moves += 1
        i1, i2 = list(revealed)
        if deck[i1] == deck[i2]:
            matched.update(revealed)
            revealed.clear()
            # Win?
            if len(matched) == len(deck):
                st.session_state.finished = True
        else:
            # Leave them visible briefly; then auto-hide
            st.session_state.pending_hide_at = time.time() + 0.8  # 800 ms

# ------------------------------ RENDER GRID -----------------------------
idx = 0
for _ in range(rows):
    row = st.columns(cols, gap="large")
    for c in row:
        if idx >= len(deck): 
            continue
        face = card_face(idx)
        # Big friendly buttons
        clicked = c.button(
            face,
            key=f"card_{idx}_{st.session_state.moves}_{len(matched)}_{1 if peeking else 0}",
            use_container_width=True
        )
        # Spacer for bigger touch targets
        c.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if clicked:
            on_card_click(idx)
        idx += 1

# ------------------------------ FOOTER / WIN ----------------------------
if st.session_state.finished:
    st.success("Great job! You matched them all! 🎉")
    st.balloons()
    if show_score:
        st.markdown(f"**Total moves:** {st.session_state.moves}")
    if st.button("Play again"):
        new_game()
        st.rerun()

# Keep the peek live only while active
if peeking:
    # Lightweight auto-refresh while peeking
    st.caption("👀 Showing all…")
    time.sleep(0.1)
    st.rerun()
# memory_match.py — Streamlit Memory Matching Game (preschool-friendly)
import random, time
import streamlit as st

st.set_page_config(page_title="Memory Match", page_icon="🧠", layout="centered")

