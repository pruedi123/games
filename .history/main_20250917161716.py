# main.py — Streamlit Spelling Game for Early Readers
# --------------------------------------------------
# Features
# - Two modes: Hangman and Listen & Spell
# - The word is never shown to the learner (unless Teacher view is on)
# - Click “Say the word” to hear it via gTTS (if installed) or browser TTS fallback
# - Paste a custom weekly spelling list in the sidebar (newline or commas)
# - Optional hint you can type without revealing the word
# - Tracks score and attempts; kid‑friendly on‑screen keyboard
#
# How to run locally:
#   pip install streamlit gTTS
#   streamlit run main.py

from __future__ import annotations
import random
import string
from typing import List
import io
import base64

import streamlit as st

# Optional TTS (online): gTTS creates an mp3 we can play via st.audio
try:
    from gtts import gTTS  # type: ignore
    HAS_GTTS = True
except Exception:
    HAS_GTTS = False

# -------------- Utilities --------------

def parse_words(raw: str) -> List[str]:
    if not raw:
        return []
    # split on commas/newlines, strip spaces, filter simple alphabetic words
    parts = [p.strip() for p in raw.replace(",", "\n").splitlines()]
    words = [p.lower() for p in parts if p and all(ch.isalpha() or ch in "-" for ch in p)]
    return words


def tts_bytes(word: str, lang: str = "en") -> bytes | None:
    """Return MP3 bytes for the word using gTTS, or None if unavailable."""
    if not HAS_GTTS:
        return None
    try:
        mp3 = io.BytesIO()
        gTTS(text=word, lang=lang, slow=False).write_to_fp(mp3)
        return mp3.getvalue()
    except Exception:
        return None

def say_word_now(word: str):
    """Speak the word immediately (no extra click).
    If gTTS is available, embed an autoplaying <audio> tag with the MP3.
    Otherwise, use the browser's SpeechSynthesis API.
    """
    audio = tts_bytes(word)
    if audio:
        b64 = base64.b64encode(audio).decode("utf-8")
        st.components.v1.html(
            f"""
            <audio autoplay>
              <source src='data:audio/mp3;base64,{b64}' type='audio/mpeg'>
            </audio>
            """,
            height=0,
        )
    else:
        st.components.v1.html(
            f"""
            <script>
              const utter = new SpeechSynthesisUtterance({word!r});
              utter.lang = 'en-US';
              utter.rate = 0.9;
              speechSynthesis.cancel();
              speechSynthesis.speak(utter);
            </script>
            """,
            height=0,
        )


def speak_button(label: str, word: str):
    """Render a button that speaks `word`. Prefer gTTS audio; fallback to browser SpeechSynthesis."""
    col1, _ = st.columns([1, 0.0001])  # keep layout tidy
    pressed = col1.button(label, use_container_width=True)
    if pressed:
        say_word_now(word)


# -------------- Game State --------------

def init_state():
    if "words" not in st.session_state:
        st.session_state.words = []
    if "queue" not in st.session_state:
        st.session_state.queue = []  # upcoming words (shuffled)
    if "mode" not in st.session_state:
        st.session_state.mode = "Listen & Spell"
    if "current" not in st.session_state:
        st.session_state.current = None  # current target word
    if "hint" not in st.session_state:
        st.session_state.hint = ""  # optional hint typed by adult
    if "wins" not in st.session_state:
        st.session_state.wins = 0
    if "rounds" not in st.session_state:
        st.session_state.rounds = 0
    if "guesses" not in st.session_state:
        st.session_state.guesses = set()  # for Hangman
    if "lives" not in st.session_state:
        st.session_state.lives = 6
    if "reveal" not in st.session_state:
        st.session_state.reveal = False  # Teacher view
    if "total_points" not in st.session_state:
        st.session_state.total_points = None
    if "last_result" not in st.session_state:
        st.session_state.last_result = None  # 'kept' or 'lost'


def reset_round():
    st.session_state.guesses = set()
    st.session_state.lives = st.session_state.get("lives_setting", 6)
    st.session_state.current = None


def next_word():
    if not st.session_state.queue:
        # Refill from words
        st.session_state.queue = st.session_state.words[:]
        random.shuffle(st.session_state.queue)
    st.session_state.current = st.session_state.queue.pop() if st.session_state.queue else None


# -------------- UI: Sidebar Controls --------------

def sidebar_controls():
    st.sidebar.header("Spelling List (Teacher)")
    # Default list = your photo's words (Regular + Bonus)
    default_list = (
        "fit\n"
        "him\n"
        "is\n"
        "it\n"
        "pin\n"
        "sip\n"
        "an\n"
        "cat\n"
        "nap\n"
        "pan\n"
        "and\n"
        "find\n"
        "for\n"
        "just\n"
        "many\n"
        "one\n"
        "she\n"
        "then"
    )

    raw = st.sidebar.text_area(
        "Paste weekly words (one per line or commas)",
        value=st.session_state.get("raw_words", default_list),
        height=200,
    )
    st.session_state.raw_words = raw
    words = parse_words(raw)

    # Optional hint per round (e.g., picture/phonics cue). Keep it generic.
    st.session_state.hint = st.sidebar.text_input(
        "Optional hint (e.g., 'animal', 'color', 'starts with /b/')",
        value=st.session_state.get("hint", ""),
        help="Hint shows to the child, but does not reveal the word.",
    )

    mode = st.sidebar.radio("Mode", ["Listen & Spell", "Jupiter Points"], index=0, help="Choose game type")
    st.session_state.mode = mode

    # Removed the Hangman lives slider line as per instructions
    # st.session_state.lives_setting = st.sidebar.slider("Hangman lives", 3, 10, 6)

    st.sidebar.toggle("Teacher view (reveal answers)", key="reveal")

    colA, colB = st.sidebar.columns(2)
    if colA.button("Load list", use_container_width=True):
        st.session_state.words = words
        st.session_state.queue = []
        reset_round()
        st.session_state.total_points = None
    if colB.button("New round", use_container_width=True):
        reset_round()
        st.session_state.total_points = None

    # Seed the initial word list on first load
    if not st.session_state.words:
        st.session_state.words = parse_words(default_list)


# -------------- Game Logic: Listen & Spell --------------

def render_listen_and_spell():
    target: str | None = st.session_state.current
    if not target:
        next_word()
        target = st.session_state.current
        if not target:
            st.info("Add at least one word in the sidebar and click ‘Load list’.")
            return

    st.subheader("Listen & Spell")

    # Speak button & hint
    with st.container(border=True):
        speak_button("🔊 Say the word", target)
        if st.session_state.hint:
            st.caption(f"Hint: {st.session_state.hint}")
        if st.session_state.reveal:
            st.caption(f"Teacher: {target}")

    # Safe clear mechanism for the listen text input
    if st.session_state.get("_clear_listen", False):
        st.session_state.pop("listen_guess", None)
        st.session_state["_clear_listen"] = False

    # Input box (does not show correct word until submitted)
    st.markdown("**Type what you hear:**")
    guess = st.text_input("Your spelling", value="", key="listen_guess")
    submitted = st.button("Check ✔️", type="primary")

    if submitted:
        st.session_state.rounds += 1
        if guess.strip().lower() == target:
            st.success("You were right!")
            st.session_state.wins += 1
            # Ensure points are initialized and record that they kept the point
            if st.session_state.total_points is None:
                st.session_state.total_points = len(st.session_state.words)
            st.session_state.last_result = "kept"
            # Advance to next word and clear input
            st.session_state["_clear_listen"] = True
            reset_round()
            next_word()
            st.rerun()
        else:
            st.error("You lost 1 Jupiter Point.")
            # Deduct a Jupiter Point on a miss (initialize if needed)
            if st.session_state.total_points is None:
                st.session_state.total_points = len(st.session_state.words)
            if st.session_state.total_points > 0:
                st.session_state.total_points -= 1
            st.session_state.last_result = "lost"
            if st.session_state.reveal:
                st.caption(f"Teacher: the word was **{target}**")
        col1, col2, col3 = st.columns(3)
        if col1.button("Next word ▶", use_container_width=True):
            st.session_state["_clear_listen"] = True
            reset_round()
            next_word()
            st.rerun()
        if col2.button("Hear it again 🔊", use_container_width=True):
            say_word_now(target)
        if col3.button("Try same word again ↻", use_container_width=True):
            st.session_state["_clear_listen"] = True
            reset_round()
            st.session_state.current = target
            st.rerun()


# -------------- Game Logic: Jupiter Points --------------

def render_jupiter_points():
    if st.session_state.total_points is None:
        st.session_state.total_points = len(st.session_state.words)
    total_points = st.session_state.total_points
    remaining_points = total_points

    target: str | None = st.session_state.current
    if not target:
        next_word()
        target = st.session_state.current
        if not target:
            st.info("Add at least one word in the sidebar and click ‘Load list’.")
            return

    st.subheader("Jupiter Points")

    # Speak button & hint
    with st.container(border=True):
        speak_button("🔊 Say the word", target)
        if st.session_state.hint:
            st.caption(f"Hint: {st.session_state.hint}")
        if st.session_state.reveal:
            st.caption(f"Teacher: {target}")

    # Safe clear mechanism for the jupiter text input
    if st.session_state.get("_clear_jupiter", False):
        st.session_state.pop("jupiter_guess", None)
        st.session_state["_clear_jupiter"] = False

    # Input box (does not show correct word until submitted)
    st.markdown("**Type what you hear:**")
    guess = st.text_input("Your spelling", value="", key="jupiter_guess")
    submitted = st.button("Check ✔️", type="primary")

    if submitted:
        st.session_state.rounds += 1
        if guess.strip().lower() == target:
            st.success("Perfect! You spelled it correctly.")
            st.session_state.wins += 1
            st.session_state.last_result = "kept"
            st.session_state["_clear_jupiter"] = True
            reset_round()
            next_word()
            st.rerun()
        else:
            st.error("Almost! Let's practice another and try again.")
            if st.session_state.reveal:
                st.caption(f"Teacher: the word was **{target}**")
            if st.session_state.total_points > 0:
                st.session_state.total_points -= 1
            st.session_state.last_result = "lost"
        remaining_points = st.session_state.total_points

        col1, col2, col3 = st.columns(3)
        if col1.button("Next word ▶", use_container_width=True):
            st.session_state["_clear_jupiter"] = True
            reset_round()
            next_word()
            st.rerun()
        if col2.button("Hear it again 🔊", use_container_width=True):
            say_word_now(target)
        if col3.button("Try same word again ↻", use_container_width=True):
            st.session_state["_clear_jupiter"] = True
            reset_round()
            st.session_state.current = target
            st.rerun()

    st.markdown(f"**Total Jupiter Points:** {total_points}")
    st.markdown(f"**Remaining Jupiter Points:** {remaining_points}")
    if remaining_points < total_points:
        st.info("Oh no! You lost some Jupiter Points. Keep trying to earn them back!")


# -------------- Main App --------------

def main():
    st.set_page_config(page_title="Spelling Game", page_icon="📝", layout="centered")
    init_state()
    sidebar_controls()

    st.title("📝 Spelling Game for Kids")
    st.caption("Designed for early readers. Words are played aloud so nothing is given away visually.")

    # Flash last result (kept/lost Jupiter Point)
    if st.session_state.get("last_result") == "kept":
        st.success("You kept your Jupiter Point!")
        st.session_state.last_result = None
    elif st.session_state.get("last_result") == "lost":
        st.error("You lost 1 Jupiter Point.")
        st.session_state.last_result = None

    # Scoreboard
    with st.container(border=True):
        st.markdown(
            f"**Score:** {st.session_state.wins} correct out of {st.session_state.rounds} attempts"
        )

    # Game mode
    if st.session_state.mode == "Jupiter Points":
        render_jupiter_points()
    else:
        render_listen_and_spell()

    st.divider()
    with st.expander("Tips for Grown‑Ups"):
        st.markdown(
            """
            - Keep the **Teacher view** off during practice so the word is never shown.
            - Paste the weekly spelling list in the sidebar. Use short, phonics‑friendly words.
            - Add a simple hint like *"animal"*, *"color"*, or *"starts with /b/"* — hints don’t reveal the word.
            - Use **Listen & Spell** for practice, or **Jupiter Points** to make it a points game (misses subtract 1 point).
            - If gTTS is unavailable, the app will try your browser’s built‑in speech.
            """
        )


if __name__ == "__main__":
    main()
