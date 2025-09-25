# mw.py — Streamlit "Jupiter Points" Spelling Game (Kindergarten‑friendly)
# ------------------------------------------------------------------------
# Starts with Jupiter Points = (# of words) × 1.
# For each word, the app:
#   1) Says the word 3× (local MW mp3 if available, else browser speech), then
#   2) Says a short slow sentence using the word,
#   3) Lets the child type the spelling.
# Scoring rules:
#   • You can only lose at most 1 point per word (on the first wrong try).
#   • Keep trying until correct; when correct, if you had lost 1 point on that word,
#     you recover that 1 point immediately. Then we move to the next word.
#   • Points never go above the starting total.
#
# Run:  streamlit run mw.py

from __future__ import annotations
from typing import List
from pathlib import Path
import streamlit as st
import base64

# ---------------------- UI Config ----------------------
st.set_page_config(page_title="Jupiter Points — Spelling Game", page_icon="🪐", layout="centered")

# ---------------------- Defaults ----------------------
DEFAULT_WORDS: List[str] = [
    "fit", "him", "is", "it", "pin", "sip", "an", "cat",
    "nap", "pan", "and", "find", "for", "just", "many", "one", "she", "then"
]

# ---------------------- Local Audio (MW scraped/downloaded) ----------------------
AUDIO_DIR_DEFAULT = Path(__file__).parent / "audio_tts"  # put your scraped MW mp3s here
AUDIO_EXTS = (".mp3", ".wav", ".m4a")

def get_audio_dir() -> Path:
    # Allow changing the folder from the UI
    p = st.session_state.get("audio_dir")
    try:
        return Path(p) if p else AUDIO_DIR_DEFAULT
    except Exception:
        return AUDIO_DIR_DEFAULT

def find_local_audio_for_word(word: str) -> Path | None:
    """Find a local audio file for the given word, using common MW scrape filenames.
    Priority: (case‑insensitive)
      1) exact name: word.mp3
      2) startswith: word*.mp3 (e.g., pan00001.mp3)
      3) contains: *word*.mp3
    """
    base = get_audio_dir()
    if not base.exists():
        return None
    wl = word.lower()
    # 1) exact
    for ext in AUDIO_EXTS:
        p = base / f"{wl}{ext}"
        if p.exists():
            return p
    # 2) startswith
    for ext in AUDIO_EXTS:
        for p in base.glob(f"{wl}*{ext}"):
            return p
    # 3) contains
    for ext in AUDIO_EXTS:
        for p in base.glob(f"*{wl}*{ext}"):
            return p
    return None

def play_local_audio_loop(path: Path, times: int = 3, gap_ms: int = 850, playback_rate: float = 1.0):
    """Loop a local audio file N times with a gap between plays (embeds data: URI)."""
    ext = path.suffix.lower()
    mime = (
        "audio/mpeg" if ext == ".mp3" else
        "audio/wav"  if ext == ".wav" else
        "audio/mp4"
    )
    try:
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        st.warning(f"Couldn't read audio file: {path}")
        return
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            var times = {times};
            var count = 0;
            var gap = {gap_ms};
            var rate = {playback_rate};
            var src = 'data:{mime};base64,{b64}';
            var audio = new Audio(src);
            audio.playbackRate = rate;
            audio.addEventListener('ended', function() {{
              count += 1;
              if (count < times) {{
                setTimeout(function() {{ audio.currentTime = 0; audio.play(); }}, gap);
              }}
            }});
            audio.play();
          }})();
        </script>
        """,
        height=0,
    )

# ---------------------- Sentence Helpers ----------------------
SENTENCE_OVERRIDES = {
    "is": "It is big.",
    "and": "We play and run.",
    "for": "This is for you.",
    "she": "She can hop.",
    "then": "We ate, then we ran.",
    "one": "I have one dog.",
    "an": "I see an ant.",
    "it": "It is red.",
    "him": "I can see him.",
    "many": "I have many books.",
    "just": "I just won.",
    "cat": "The cat sat.",
    "nap": "I take a nap.",
    "pan": "The pan is hot.",
    "pin": "I use a pin.",
    "sip": "Take a sip.",
    "fit": "I can fit the lid.",
    "find": "I can find it.",
}

def a_or_an(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"

def build_sentence(word: str) -> str:
    w = word.lower()
    if w in SENTENCE_OVERRIDES:
        return SENTENCE_OVERRIDES[w]
    no_article = {"many", "few", "some", "none", "one", "two", "three", "she", "he", "they", "we", "it", "and", "or", "for", "then", "is"}
    if w in no_article:
        return f"We can use the word '{word}'."
    return f"I see {a_or_an(w)} {word}."

# --- Browser SpeechSynthesis fallbacks ---

def say_word_repeat(word: str, times: int = 3, rate: float = 0.8, gap_ms: int = 850):
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const txt = {word!r};
            const times = {times};
            const gap = {gap_ms};
            const rate = {rate};
            let i = 0;
            function speakOne() {{
              const u = new SpeechSynthesisUtterance(txt);
              u.lang = 'en-US';
              u.rate = rate;
              u.pitch = 1.0;
              u.onend = () => {{
                i += 1;
                if (i < times) setTimeout(speakOne, gap);
              }};
              speechSynthesis.speak(u);
            }}
            speechSynthesis.cancel();
            speakOne();
          }})();
        </script>
        """,
        height=0,
    )

def say_sentence(word: str, delay_ms: int = 0, rate: float = 0.85):
    sentence = build_sentence(word)
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const sentence = {sentence!r};
            const delay = {delay_ms};
            const rate = {rate};
            function speak() {{
              const u = new SpeechSynthesisUtterance(sentence);
              u.lang = 'en-US';
              u.rate = rate;
              u.pitch = 0.95;
              speechSynthesis.speak(u);
            }}
            speechSynthesis.cancel();
            if (delay > 0) setTimeout(speak, delay); else speak();
          }})();
        </script>
        """,
        height=0,
    )

# ---------------------- State -------------------------

def init_state():
    ss = st.session_state
    if "words" not in ss:
        ss.words = DEFAULT_WORDS.copy()
    if "idx" not in ss:
        ss.idx = 0
    if "attempted_penalty" not in ss:
        ss.attempted_penalty = False
    if "total_points" not in ss:
        ss.total_points = len(ss.words)
    if "current_points" not in ss:
        ss.current_points = ss.total_points
    if "listen_nonce" not in ss:
        ss.listen_nonce = 0
    if "last_feedback" not in ss:
        ss.last_feedback = ""
    if "auto_play" not in ss:
        ss.auto_play = True
    if "last_spoken_idx" not in ss:
        ss.last_spoken_idx = -1
    if "_retry_speak" not in ss:
        ss._retry_speak = False

init_state()

# ---------------------- Sidebar -----------------------
st.sidebar.header("Spelling List (Teacher)")
raw = st.sidebar.text_area(
    "Paste words (one per line or commas)",
    value="\n".join(st.session_state.words),
    height=160,
)

def parse_words(raw: str) -> List[str]:
    parts = [p.strip() for p in raw.replace(",", "\n").splitlines()]
    return [p for p in parts if p]

col_a, col_b = st.sidebar.columns(2)
if col_a.button("Load list", use_container_width=True):
    st.session_state.words = parse_words(raw)
    st.session_state.idx = 0
    st.session_state.total_points = len(st.session_state.words)
    st.session_state.current_points = st.session_state.total_points
    st.session_state.attempted_penalty = False
    st.session_state.last_feedback = ""
    st.session_state.last_spoken_idx = -1
    st.session_state._retry_speak = False
    st.session_state.listen_nonce += 1
if col_b.button("Restart", use_container_width=True):
    st.session_state.idx = 0
    st.session_state.current_points = st.session_state.total_points
    st.session_state.attempted_penalty = False
    st.session_state.last_feedback = ""
    st.session_state.last_spoken_idx = -1
    st.session_state._retry_speak = False
    st.session_state.listen_nonce += 1

st.sidebar.markdown("---")
st.sidebar.caption("Tip: Use local MW mp3s for best clarity.")
st.session_state.audio_dir = st.sidebar.text_input(
    "Local audio folder (MW mp3s)",
    value=str(st.session_state.get("audio_dir", AUDIO_DIR_DEFAULT)),
)
force_local = st.sidebar.checkbox(
    "Prefer local MW audio when available",
    value=True,
    help="If a local file exists for a word, play it instead of browser speech.",
)
st.sidebar.checkbox("Auto play each word (3× then sentence)", value=st.session_state.auto_play, key="auto_play")
kinder = st.sidebar.checkbox("Kindergarten Mode (very slow)", value=False, help="Speak extra-slow like to a 5-year-old.")

# ---------------------- Main UI -----------------------
st.title("🪐 Jupiter Points — Spelling Game")
st.caption("Words are spoken; the child types the spelling. Lose at most 1 point per word; recover it when correct.")

wds = st.session_state.words
N = len(wds)
idx = st.session_state.idx
points = st.session_state.current_points
start_points = st.session_state.total_points

st.markdown(f"**Word:** {idx+1} / {N}  &nbsp;|&nbsp;  **Jupiter Points:** {points} / {start_points}")

# Show which local file will be used (if any)
p_preview = find_local_audio_for_word(word) if idx < N else None
if p_preview is not None:
    st.caption(f"Using local audio: {p_preview.name}")

if idx >= N:
    st.success("All words complete! 🎉")
    st.balloons()
    st.stop()

word = wds[idx]

# Auto play on new word (once per index)
if st.session_state.auto_play and st.session_state.last_spoken_idx != idx:
    p = find_local_audio_for_word(word)
    if force_local and p is not None:
        play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
    else:
        say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
    total_delay = 3 * (900 + 850)
    say_sentence(word, delay_ms=total_delay, rate=(0.6 if kinder else 0.85))
    st.session_state.last_spoken_idx = idx

# Hearing controls
with st.container(border=True):
    cc1, cc2 = st.columns(2)
    if cc1.button("🔊 Say 3×", use_container_width=True):
        p = find_local_audio_for_word(word)
        if force_local and p is not None:
            play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
        else:
            say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
    if cc2.button("🔊 Sentence", use_container_width=True):
        say_sentence(word, delay_ms=0, rate=0.85)

# Input and checking
st.markdown("**Type the word you heard:**")
with st.form(key=f"listen_form_{st.session_state.listen_nonce}"):
    guess = st.text_input("Your spelling", value="", key=f"guess_{st.session_state.listen_nonce}")
    submitted = st.form_submit_button("Check ✔️")

if submitted:
    g = (guess or "").strip().lower()
    target = word.lower()
    if g == target:
        if st.session_state.attempted_penalty:
            st.session_state.current_points = min(start_points, st.session_state.current_points + 1)
        st.session_state.attempted_penalty = False
        st.session_state.last_feedback = "✅ You were right! (Moving to next word.)"
        st.session_state._retry_speak = False
        st.session_state.idx += 1
        st.session_state.listen_nonce += 1
    else:
        if not st.session_state.attempted_penalty:
            st.session_state.current_points = max(0, st.session_state.current_points - 1)
            st.session_state.attempted_penalty = True
        st.session_state.last_feedback = "❌ Not yet. Try again — you can earn the point back when you get it right!"
        st.session_state._retry_speak = True
        st.session_state.listen_nonce += 1

# Auto speak again on retry (after a wrong answer)
if st.session_state._retry_speak and idx < N:
    p = find_local_audio_for_word(word)
    if force_local and p is not None:
        play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
    else:
        say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
    total_delay = 3 * (900 + 850)
    say_sentence(word, delay_ms=total_delay, rate=(0.6 if kinder else 0.85))
    st.session_state._retry_speak = False

# Feedback banner
if st.session_state.last_feedback:
    st.info(st.session_state.last_feedback)

# Quick repeats
hr1, hr2 = st.columns(2)
if hr1.button("🔁 Hear again (3×)"):
    p = find_local_audio_for_word(word)
    if force_local and p is not None:
        play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
    else:
        say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
if hr2.button("🗣️ Sentence again"):
    say_sentence(word, delay_ms=0, rate=0.85)