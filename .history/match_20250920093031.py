# match.py — Simple Animal Memory Match (Streamlit)
# Single-tap to flip, big animal pictures, and spoken feedback.
# Sounds: "ding" on any flip; "good match" on match; "try again" on mismatch.

import random
import time
import streamlit as st

st.set_page_config(page_title="Animal Match", page_icon="🐾", layout="centered")

# ----------------------------- SETTINGS (Sidebar) -----------------------------
st.sidebar.header("Grown‑Up Settings")
pairs = st.sidebar.slider("Number of pairs", 3, 8, 6)
size_choice = st.sidebar.select_slider(
    "Card size", options=["Normal", "Large", "XL", "Huge", "Mega", "Giant"], value="Giant"
)
say_feedback = st.sidebar.checkbox("Enable spoken feedback", value=True,
    help="Uses your browser's speech to say 'good match' or 'try again'.")
play_ding = st.sidebar.checkbox("Enable ding on flip", value=True)

# Dynamic sizing for big, tap‑friendly cards
if size_choice == "Normal":
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 64, 18, 120, 12
elif size_choice == "Large":
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 110, 24, 180, 14
elif size_choice == "XL":
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 140, 26, 220, 16
elif size_choice == "Huge":
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 180, 28, 280, 18
elif size_choice == "Mega":
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 220, 32, 340, 22
else:  # Giant
    FONT_PX, PAD_PX, HEIGHT_PX, GAP_PX = 280, 36, 420, 26

# Make the emoji itself even larger than the button text
if size_choice == "Giant":
    EMOJI_PX = int(FONT_PX * 1.6)
elif size_choice == "Mega":
    EMOJI_PX = int(FONT_PX * 1.5)
elif size_choice == "Huge":
    EMOJI_PX = int(FONT_PX * 1.45)
elif size_choice == "XL":
    EMOJI_PX = int(FONT_PX * 1.35)
elif size_choice == "Large":
    EMOJI_PX = int(FONT_PX * 1.25)
else:
    EMOJI_PX = int(FONT_PX * 1.15)

# Keep buttons very large
st.markdown(
    f"""
    <style>
    /* Button container */
    div.stButton > button {{
        font-size: {FONT_PX}px !important; /* base size for fallback text */
        padding: {PAD_PX}px 0 !important;
        height: {HEIGHT_PX}px !important;
        min-height: {HEIGHT_PX}px !important;
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: visible !important;
    }}
    /* Streamlit renders button text inside a <p> tag; scale emoji much larger */
    div.stButton > button p {{
        font-size: {EMOJI_PX}px !important;
        line-height: 1 !important;
        margin: 0 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------- SIMPLE JS AUDIO / TTS -----------------------------
# We use a tiny inline JS component to play a short beep (ding) and to speak phrases.
# This avoids needing to manage separate mp3 files.

def js_beep():
    if not play_ding:
        return
    st.components.v1.html(
        """
        <script>
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.type = 'sine';
          o.frequency.value = 1100; // ding pitch
          g.gain.setValueAtTime(0.0001, ctx.currentTime);
          g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.01);
          g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.12);
          o.connect(g); g.connect(ctx.destination);
          o.start(); o.stop(ctx.currentTime + 0.12);
        } catch(e) {}
        </script>
        """,
        height=0,
    )

def js_say(text: str):
    if not say_feedback:
        return
    st.components.v1.html(
        f"""
        <script>
        try {{
          const u = new SpeechSynthesisUtterance({text!r});
          u.rate = 1.0; u.pitch = 1.0; u.lang = 'en-US';
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(u);
        }} catch(e) {{}}
        </script>
        """,
        height=0,
    )

# ----------------------------- GAME STATE -----------------------------
ANIMALS = [
    "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🦁",
    "🐷","🐸","🐵","🐮","🐯","🦒","🦓","🦊","🦝","🦘"
]

if "deck" not in st.session_state:
    st.session_state.deck = []
if "revealed" not in st.session_state:
    st.session_state.revealed = set()
if "matched" not in st.session_state:
    st.session_state.matched = set()
if "moves" not in st.session_state:
    st.session_state.moves = 0
if "finished" not in st.session_state:
    st.session_state.finished = False
if "lock" not in st.session_state:
    st.session_state.lock = False  # ignore taps during mismatch delay


def new_game():
    symbols = random.sample(ANIMALS, pairs)
    deck = symbols * 2
    random.shuffle(deck)
    st.session_state.deck = deck
    st.session_state.revealed = set()
    st.session_state.matched = set()
    st.session_state.moves = 0
    st.session_state.finished = False
    st.session_state.lock = False

# New game button
col_sb1, col_sb2 = st.sidebar.columns(2)
if col_sb1.button("New game") or not st.session_state.deck:
    new_game()

# Peek button for a quick assist
if col_sb2.button("Peek (3s)"):
    st.session_state._peek_until = time.time() + 3

peek_until = st.session_state.get("_peek_until", 0)
peeking = time.time() < peek_until

# ----------------------------- HEADER -----------------------------
st.title("🐾 Animal Match")
st.caption("Tap one time to flip a card. Find all the pairs!")
st.markdown(f"**Moves:** {st.session_state.moves}")

# ----------------------------- LAYOUT -----------------------------
# Fewer columns for bigger cards
if size_choice == "Giant":
    cols = 1
elif size_choice == "Mega":
    cols = 2
elif size_choice in ("XL", "Huge"):
    cols = 2
elif size_choice == "Large":
    cols = 3
else:
    cols = 4 if pairs >= 7 else 3
rows = (len(st.session_state.deck) + cols - 1) // cols


def is_face_up(i: int) -> bool:
    return peeking or (i in st.session_state.revealed) or (i in st.session_state.matched)


def on_card_click(i: int):
    # Ignore taps while two mismatched cards are temporarily shown
    if st.session_state.lock:
        return
    if i in st.session_state.matched or i in st.session_state.revealed or st.session_state.finished:
        return

    # Single click flips the card
    st.session_state.revealed.add(i)
    js_beep()  # ding on any flip (if enabled)

    # If two are up, evaluate
    if len(st.session_state.revealed) == 2:
        st.session_state.moves += 1
        i1, i2 = list(st.session_state.revealed)
        d = st.session_state.deck
        if d[i1] == d[i2]:
            st.session_state.matched.update(st.session_state.revealed)
            st.session_state.revealed.clear()
            js_say("good match")
            if len(st.session_state.matched) == len(d):
                st.session_state.finished = True
        else:
            # Show both briefly; then hide and speak
            st.session_state.lock = True
            js_say("try again")
            # Schedule auto-hide by storing a timestamp
            st.session_state._hide_at = time.time() + 0.85

# Handle scheduled hide for mismatches
hide_at = st.session_state.get("_hide_at", 0)
if hide_at:
    now = time.time()
    if now >= hide_at:
        st.session_state.revealed = set()
        st.session_state.lock = False
        st.session_state._hide_at = 0
        # Rerun outside of callbacks to reflect hidden cards immediately
        st.rerun()
    else:
        # Keep the UI live until it's time to hide the cards
        time.sleep(0.05)
        st.rerun()

# ----------------------------- RENDER GRID -----------------------------
idx = 0
for _ in range(rows):
    row = st.columns(cols, gap="large")
    for c in row:
        if idx >= len(st.session_state.deck):
            continue
        face = st.session_state.deck[idx] if is_face_up(idx) else "❓"
        c.button(
            face,
            key=f"card_{idx}_{st.session_state.moves}_{len(st.session_state.matched)}_{1 if peeking else 0}",
            use_container_width=True,
            on_click=on_card_click,
            args=(idx,),
        )
        c.markdown(f"<div style='height:{GAP_PX}px'></div>", unsafe_allow_html=True)
        idx += 1

# ----------------------------- FINISH -----------------------------
if st.session_state.finished:
    st.success("Great job! You matched them all! 🎉")
    st.balloons()

# Keep peek active while timer runs
if peeking:
    st.caption("👀 Showing all…")
    time.sleep(0.1)
    st.rerun()
