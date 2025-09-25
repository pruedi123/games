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
import os
from pathlib import Path

import streamlit as st


# Optional TTS (online): gTTS creates an mp3 we can play via st.audio
try:
    from gtts import gTTS  # type: ignore
    HAS_GTTS = True
except Exception:
    HAS_GTTS = False

# Simple pronunciation overrides for tricky words
PRONUN_OVERRIDES = {
    "one": "wun",    # avoid "wuan"; closer to US school pronunciation
    "and": "ay-nd",  # exaggerate for clarity so it doesn't sound like "an"
    "pin": "pihn",   # exaggerate short /ɪ/ so it doesn't sound like "pen"
}

def pron_text(word: str) -> str:
    return PRONUN_OVERRIDES.get(word.lower(), word)

# Toggle-aware pronunciation helper
def effective_pron_text(word: str) -> str:
    """Return pronunciation text honoring the 'disable_phonetic_overrides' toggle."""
    if st.session_state.get("disable_phonetic_overrides"):
        return word
    return pron_text(word)

# Simple sentence overrides/templates for first graders
SENTENCE_OVERRIDES = {
    # Sight words / function words
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

    # Concrete nouns / verbs from your list
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
    # Prefer explicit, kid‑friendly overrides
    if w in SENTENCE_OVERRIDES:
        return SENTENCE_OVERRIDES[w]

    # Words that should not take an article before them
    no_article_words = {
        "many", "few", "some", "none", "one", "two", "three",
        "she", "he", "they", "we", "it", "and", "or", "for", "then", "is"
    }
    if w in no_article_words:
        # Generic simple pattern that keeps grammar correct without showing the word oddly
        return f"We can use the word '{word}'."

    # Default: treat as a noun and use an a/an pattern
    art = a_or_an(w)
    return f"I see {art} {word}."

# -------------- Local Audio Overrides --------------
PRON_DIR = Path(__file__).parent / "pron"

def local_audio_path(word: str) -> str | None:
    if not st.session_state.get("use_local_audio"):
        return None
    try:
        for ext in (".mp3", ".wav", ".m4a"):
            p = PRON_DIR / f"{word.lower()}{ext}"
            if p.exists():
                return str(p)
    except Exception:
        return None
    return None

def play_audio_file(path: str):
    # Use HTML audio to ensure autoplay
    st.components.v1.html(
        f"""
        <audio autoplay>
          <source src="file://{path}" type="audio/mpeg">
        </audio>
        """,
        height=0,
    )

# -------------- Local Audio Download Helpers --------------

def ensure_pron_dir() -> None:
    PRON_DIR.mkdir(parents=True, exist_ok=True)

def download_url_to_file(url: str, dest_path: Path) -> bool:
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.content:
            dest_path.write_bytes(r.content)
            return True
    except Exception:
        return False
    return False

# -------------- Merriam-Webster Batch Prefetch --------------

def prefetch_mw_audio(words: list[str], api_key: str) -> tuple[int, list[str]]:
    """Download MW audio for the given words into pron/*.mp3. Returns (downloaded_count, misses)."""
    ensure_pron_dir()
    downloaded = 0
    misses: list[str] = []
    for w in words:
        url = mw_fetch_audio_url(w, api_key)
        if not url:
            misses.append(w)
            continue
        ok = download_url_to_file(url, PRON_DIR / f"{w.lower()}.mp3")
        if ok:
            downloaded += 1
        else:
            misses.append(w)
    return downloaded, misses

# -------------- Utilities --------------

def parse_words(raw: str) -> List[str]:
    if not raw:
        return []
    # split on commas/newlines, strip spaces, filter simple alphabetic words
    parts = [p.strip() for p in raw.replace(",", "\n").splitlines()]
    words = [p.lower() for p in parts if p and all(ch.isalpha() or ch in "-" for ch in p)]
    return words


def tts_bytes(word: str, lang: str = "en", slow: bool = False) -> bytes | None:
    """Return MP3 bytes for the word using gTTS, or None if unavailable."""
    if not HAS_GTTS:
        return None
    try:
        mp3 = io.BytesIO()
        gTTS(text=effective_pron_text(word), lang=lang, slow=slow).write_to_fp(mp3)
        return mp3.getvalue()
    except Exception:
        return None

def say_word_now(word: str):
    """Speak the word immediately (no extra click).
    If gTTS is available, embed an autoplaying <audio> tag with the MP3.
    Otherwise, use the browser's SpeechSynthesis API.
    """
    speak_txt = effective_pron_text(word)
    # 1) Local recorded audio override
    lp = local_audio_path(word)
    if lp:
        play_audio_file(lp)
        return
    # In Kindergarten Mode, force very slow browser speech for maximum clarity
    if st.session_state.get("kindergarten_mode"):
        st.components.v1.html(
            f"""
            <script>
              const utter = new SpeechSynthesisUtterance({speak_txt!r});
              utter.lang = 'en-US';
              utter.rate = 0.35; // slightly faster for intelligibility
              utter.pitch = 1.0;
              speechSynthesis.cancel();
              speechSynthesis.speak(utter);
            </script>
            """,
            height=0,
        )
        return
    audio = tts_bytes(speak_txt)
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
              const utter = new SpeechSynthesisUtterance({speak_txt!r});
              utter.lang = 'en-US';
              utter.rate = 0.9;
              speechSynthesis.cancel();
              speechSynthesis.speak(utter);
            </script>
            """,
            height=0,
        )


def say_word_repeat(
    word: str,
    times: int = 3,
    slow: bool = True,
    gap_ms: int = 800,
    exaggerated: bool = False,
    slow_rate: float = 0.35,
):
    """Speak the word multiple times in a row, with a gap between repetitions. Uses slow pace by default for kids.
    Exaggerated mode uses browser SpeechSynthesis with very slow rate and custom options.
    """
    speak_txt = effective_pron_text(word)
    # Local audio override for repeats (loop with gaps)
    lp = local_audio_path(word)
    if lp:
        st.components.v1.html(
            f"""
            <script>
              (function() {{
                var times = {times};
                var count = 0;
                var gap = {gap_ms};
                var audio = new Audio({repr('file://')}+{repr(lp)});
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
        return
    # In exaggerated mode, prefer browser SpeechSynthesis for fine-grained control of speaking rate
    if exaggerated:
        st.components.v1.html(
            f"""
            <script>
              (function() {{
                const word = {speak_txt!r};
                const times = {times};
                const gap = {gap_ms};
                const rate = {slow_rate};
                let i = 0;
                function speakOne() {{
                  const u = new SpeechSynthesisUtterance(word);
                  u.lang = 'en-US';
                  u.rate = rate;   // very slow for clarity
                  u.pitch = 0.9;   // slightly lower pitch for articulation
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
        return
    audio = tts_bytes(speak_txt, slow=slow)
    if audio:
        b64 = base64.b64encode(audio).decode("utf-8")
        st.components.v1.html(
            f"""
            <script>
              (function() {{
                var times = {times};
                var count = 0;
                var audio = new Audio('data:audio/mp3;base64,{b64}');
                audio.addEventListener('ended', function() {{
                  count += 1;
                  if (count < times) {{
                    setTimeout(function(){{
                      audio.currentTime = 0;
                      audio.play();
                    }}, {gap_ms});
                  }}
                }});
                audio.play();
              }})();
            </script>
            """,
            height=0,
        )
    else:
        st.components.v1.html(
            f"""
            <script>
              (function() {{
                const word = {speak_txt!r};
                const times = {times};
                let i = 0;
                function speakOne() {{
                  const u = new SpeechSynthesisUtterance(word);
                  u.lang = 'en-US';
                  u.rate = 0.7;  // slow for clarity
                  u.onend = () => {{
                    i += 1;
                    if (i < times) setTimeout(speakOne, {gap_ms});
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


# Speak a slow sentence using the word, for teacher/child
def say_slow_sentence(word: str, delay_ms: int = 0, rate: float = 0.55):
    """Speak a very slow short sentence using the word. Only shows text in Teacher view."""
    sentence_display = build_sentence(word)
    speak_sentence = sentence_display.replace(word, effective_pron_text(word))
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const sentence = {speak_sentence!r};
            const rate = {rate};
            const delay = {delay_ms};
            function speak() {{
              const u = new SpeechSynthesisUtterance(sentence);
              u.lang = 'en-US';
              u.rate = rate;  // slow for early readers
              u.pitch = 0.95;
              speechSynthesis.speak(u);
            }}
            if (delay > 0) {{
              setTimeout(speak, delay);
            }} else {{
              speak();
            }}
          }})();
        </script>
        """,
        height=0,
    )
    if st.session_state.get("reveal"):
        st.caption(f"Teacher sentence: {sentence_display}")


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
    # Initialize input nonces for safe clearing of text inputs
    if "listen_nonce" not in st.session_state:
        st.session_state.listen_nonce = 0
    if "jupiter_nonce" not in st.session_state:
        st.session_state.jupiter_nonce = 0
    # Pronunciation settings defaults
    if "pron_source" not in st.session_state:
        st.session_state.pron_source = "Merriam-Webster"
    if "mw_api_key" not in st.session_state:
        st.session_state.mw_api_key = ""


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
    st.sidebar.checkbox(
        "Kindergarten Mode (exaggerated, very slow)",
        key="kindergarten_mode",
        help="Extra slow speech and clearer phonetics for early learners.",
    )
    st.sidebar.checkbox(
        "Use recorded audio if available (pron/*.mp3)",
        key="use_local_audio",
        help="Place files like pron/and.mp3, pron/one.mp3 in the app folder.",
    )
    st.sidebar.checkbox(
        "Disable phonetic overrides (adult clarity)",
        key="disable_phonetic_overrides",
        help="Use exact word text for TTS; no 'wun'/'ay-nd' substitutions.",
    )
    st.sidebar.caption("Tip: For the clearest result, record your own MP3s for tricky words and enable 'Use recorded audio'.")

    # Pronunciation source & key
    st.sidebar.markdown("---")
    st.sidebar.subheader("Pronunciation")
    st.session_state.pron_source = st.sidebar.selectbox(
        "Source",
        ["Merriam-Webster", "Auto (Best)", "gTTS", "Browser"],
        index=["Merriam-Webster", "Auto (Best)", "gTTS", "Browser"].index(
            st.session_state.get("pron_source", "Merriam-Webster")
        ),
        help="Choose voice source. MW requires an API key.",
    )
    if st.session_state.pron_source in ("Merriam-Webster", "Auto (Best)"):
        st.session_state.mw_api_key = st.sidebar.text_input(
            "MW API Key (dictionaryapi.com)",
            value=st.session_state.get("mw_api_key", ""),
            type="password",
        )

    # --- MW Audio Download Button ---
    # Only show if MW or Auto (Best) is selected as the pron source
    if st.session_state.pron_source in ("Merriam-Webster", "Auto (Best)"):
        if st.sidebar.button("Download MW audio for this list", use_container_width=True, disabled=not bool(st.session_state.get("mw_api_key"))):
            if not st.session_state.get("mw_api_key"):
                st.warning("Please enter your Merriam-Webster API key first.")
            else:
                dl, misses = prefetch_mw_audio(words, st.session_state.get("mw_api_key"))
                st.session_state.use_local_audio = True  # prefer local once downloaded
                if dl:
                    st.success(f"Downloaded {dl} audio file(s) to pron/.")
                if misses:
                    st.info("No MW audio found for: " + ", ".join(misses))

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

    # Quick replay controls (don’t clear input)
    rc1, rc2 = st.columns(2)
    if rc1.button("🔊 Say it again", use_container_width=True):
        # In Kindergarten Mode use slower sentence follow-up
        say_word_now(target)
        if st.session_state.get("kindergarten_mode"):
            say_slow_sentence(target, delay_ms=1200, rate=0.6)
        else:
            say_slow_sentence(target, delay_ms=900, rate=float(st.session_state.get("_sentence_rate", 0.55)))
    if rc2.button("🔁 3× Slow", use_container_width=True):
        if st.session_state.get("kindergarten_mode"):
            say_word_repeat(target, times=3, exaggerated=True, slow_rate=0.25, gap_ms=1500)
            total_delay = 3 * (900 + 1500)
            say_slow_sentence(target, delay_ms=total_delay, rate=0.6)
        else:
            say_word_repeat(target, times=3, exaggerated=True, slow_rate=0.32, gap_ms=1000)
            total_delay = 3 * (900 + 1000)
            say_slow_sentence(target, delay_ms=total_delay, rate=float(st.session_state.get("_sentence_rate", 0.55)))

    # If flagged, automatically repeat the word (e.g., after "Try again")
    if st.session_state.get("_repeat_word"):
        say_word_repeat(
            target,
            times=int(st.session_state.get("_repeat_times", 3)),
            slow=bool(st.session_state.get("_repeat_slow", True)),
            gap_ms=int(st.session_state.get("_repeat_gap_ms", 800)),
            exaggerated=bool(st.session_state.get("_repeat_exaggerated", False)),
            slow_rate=float(st.session_state.get("_repeat_rate", 0.35)),
        )
        # After the repeats, speak a slow sentence that uses the word
        _times = int(st.session_state.get("_repeat_times", 3))
        _gap = int(st.session_state.get("_repeat_gap_ms", 800))
        # rough per-utterance duration cushion (ms) for slow speech
        per_play_ms = 900
        delay_ms = _times * (per_play_ms + _gap)
        say_slow_sentence(target, delay_ms=delay_ms, rate=float(st.session_state.get("_sentence_rate", 0.55)))
        st.session_state.pop("_repeat_word", None)
        st.session_state.pop("_repeat_times", None)
        st.session_state.pop("_repeat_slow", None)
        st.session_state.pop("_repeat_gap_ms", None)
        st.session_state.pop("_repeat_exaggerated", None)
        st.session_state.pop("_repeat_rate", None)

    # Safe clear: bump nonce so the widget key changes (guaranteed empty field)
    if st.session_state.get("_clear_listen", False):
        st.session_state.listen_nonce += 1
        st.session_state["_clear_listen"] = False

    # Input box (does not show correct word until submitted)
    st.markdown("**Type what you hear:**")
    with st.form(key=f"listen_form_{st.session_state.listen_nonce}"):
        guess = st.text_input("Your spelling", value="", key=f"listen_guess_{st.session_state.listen_nonce}")
        submitted = st.form_submit_button("Check ✔️")

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
            st.session_state.last_result = "lost"
            st.error("You lost 1 Jupiter Point. Do you want to try again or move to the next word?")
            # Deduct a Jupiter Point on a miss (initialize if needed)
            if st.session_state.total_points is None:
                st.session_state.total_points = len(st.session_state.words)
            if st.session_state.total_points > 0:
                st.session_state.total_points -= 1
            if st.session_state.reveal:
                st.caption(f"Teacher: the word was **{target}**")
            st.session_state["_clear_listen"] = True  # always clear typed word
            col1, col2 = st.columns(2)
            if col1.button("Try again ↻", use_container_width=True):
                st.session_state["_clear_listen"] = True
                st.session_state["_repeat_word"] = target
                st.session_state["_repeat_times"] = 3
                st.session_state["_repeat_slow"] = True
                st.session_state["_repeat_exaggerated"] = True
                if st.session_state.get("kindergarten_mode"):
                    st.session_state["_repeat_gap_ms"] = 1500
                    st.session_state["_repeat_rate"] = 0.25
                else:
                    st.session_state["_repeat_gap_ms"] = 1200
                    st.session_state["_repeat_rate"] = 0.32
                reset_round()
                st.session_state.current = target
                st.rerun()
            if col2.button("Next word ▶", use_container_width=True):
                st.session_state["_clear_listen"] = True
                reset_round()
                next_word()
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

    # Quick replay controls (don’t clear input)
    rc1, rc2 = st.columns(2)
    if rc1.button("🔊 Say it again", use_container_width=True):
        # In Kindergarten Mode use slower sentence follow-up
        say_word_now(target)
        if st.session_state.get("kindergarten_mode"):
            say_slow_sentence(target, delay_ms=1200, rate=0.6)
        else:
            say_slow_sentence(target, delay_ms=900, rate=float(st.session_state.get("_sentence_rate", 0.55)))
    if rc2.button("🔁 3× Slow", use_container_width=True):
        if st.session_state.get("kindergarten_mode"):
            say_word_repeat(target, times=3, exaggerated=True, slow_rate=0.25, gap_ms=1500)
            total_delay = 3 * (900 + 1500)
            say_slow_sentence(target, delay_ms=total_delay, rate=0.6)
        else:
            say_word_repeat(target, times=3, exaggerated=True, slow_rate=0.32, gap_ms=1000)
            total_delay = 3 * (900 + 1000)
            say_slow_sentence(target, delay_ms=total_delay, rate=float(st.session_state.get("_sentence_rate", 0.55)))

    # If flagged, automatically repeat the word (e.g., after "Try again")
    if st.session_state.get("_repeat_word"):
        say_word_repeat(
            target,
            times=int(st.session_state.get("_repeat_times", 3)),
            slow=bool(st.session_state.get("_repeat_slow", True)),
            gap_ms=int(st.session_state.get("_repeat_gap_ms", 800)),
            exaggerated=bool(st.session_state.get("_repeat_exaggerated", False)),
            slow_rate=float(st.session_state.get("_repeat_rate", 0.35)),
        )
        # After the repeats, speak a slow sentence that uses the word
        _times = int(st.session_state.get("_repeat_times", 3))
        _gap = int(st.session_state.get("_repeat_gap_ms", 800))
        per_play_ms = 900
        delay_ms = _times * (per_play_ms + _gap)
        say_slow_sentence(target, delay_ms=delay_ms, rate=float(st.session_state.get("_sentence_rate", 0.55)))
        st.session_state.pop("_repeat_word", None)
        st.session_state.pop("_repeat_times", None)
        st.session_state.pop("_repeat_slow", None)
        st.session_state.pop("_repeat_gap_ms", None)
        st.session_state.pop("_repeat_exaggerated", None)
        st.session_state.pop("_repeat_rate", None)

    # Safe clear: bump nonce so the widget key changes
    if st.session_state.get("_clear_jupiter", False):
        st.session_state.jupiter_nonce += 1
        st.session_state["_clear_jupiter"] = False

    # Input box (does not show correct word until submitted)
    st.markdown("**Type what you hear:**")
    with st.form(key=f"jupiter_form_{st.session_state.jupiter_nonce}"):
        guess = st.text_input("Your spelling", value="", key=f"jupiter_guess_{st.session_state.jupiter_nonce}")
        submitted = st.form_submit_button("Check ✔️")

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
            col1, col2 = st.columns(2)
            if col1.button("Try again ↻", use_container_width=True):
                st.session_state["_clear_jupiter"] = True
                st.session_state["_repeat_word"] = target
                st.session_state["_repeat_times"] = 3
                st.session_state["_repeat_slow"] = True
                st.session_state["_repeat_exaggerated"] = True
                if st.session_state.get("kindergarten_mode"):
                    st.session_state["_repeat_gap_ms"] = 1500
                    st.session_state["_repeat_rate"] = 0.25
                else:
                    st.session_state["_repeat_gap_ms"] = 1200
                    st.session_state["_repeat_rate"] = 0.32
                reset_round()
                st.session_state.current = target
                st.rerun()
            if col2.button("Next word ▶", use_container_width=True):
                st.session_state["_clear_jupiter"] = True
                reset_round()
                next_word()
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
