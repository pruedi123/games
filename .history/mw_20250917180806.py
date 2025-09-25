# make_spelling_audio.py
# Creates one MP3 per word using Google Text-to-Speech (no API key needed).

from gtts import gTTS
from pathlib import Path
import time
from pathlib import Path
import os

# Your list (from the photo)
WORDS = [
    "fit", "him", "is", "it", "pin", "sip", "an", "cat", "nap", "pan",
    "and", "find", "for", "just", "many", "one", "she", "then"
]

# ---------------------- Local Audio (MW scraped/downloaded) ----------------------
AUDIO_DIR_DEFAULT = Path(__file__).parent / "pron"  # put your scraped MW mp3s here

def get_audio_dir() -> Path:
    # Allow changing the folder from the UI
    p = st.session_state.get("audio_dir")
    try:
        return Path(p) if p else AUDIO_DIR_DEFAULT
    except Exception:
        return AUDIO_DIR_DEFAULT

AUDIO_EXTS = (".mp3", ".wav", ".m4a")


def find_local_audio_for_word(word: str) -> Path | None:
    """Find a local audio file for the given word, using common MW scrape filenames.
    Priority:
      1) exact name: word.mp3
      2) startswith: word*.mp3 (e.g., pan00001.mp3)
      3) contains: *-word-*.mp3 (rare)
    The search is case-insensitive.
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
    # 2) startswith pattern (typical MW tokens: pan00001.mp3)
    for ext in AUDIO_EXTS:
        for p in base.glob(f"{wl}*{ext}"):
            return p
    # 3) contains pattern (fallback)
    for ext in AUDIO_EXTS:
        for p in base.glob(f"*{wl}*{ext}"):
            return p
    return None


def play_local_audio_loop(path: Path, times: int = 3, gap_ms: int = 850):
    """Loop a local audio file N times with a gap between plays."""
    mime = (
        "audio/mpeg" if path.suffix.lower() == ".mp3"
        else "audio/wav" if path.suffix.lower() == ".wav"
        else "audio/mp4"
    )
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            var times = {times};
            var count = 0;
            var gap = {gap_ms};
            var audio = new Audio("file://{path.as_posix()}");
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

# Change this if you want a different voice locale (e.g., 'en-GB')
LANG = "en"   # 'en' = US English
SLOW = False  # True speaks more slowly

out_dir = Path("audio_tts")
out_dir.mkdir(parents=True, exist_ok=True)

def speak_to_mp3(word: str, lang: str = LANG, slow: bool = SLOW) -> Path:
    safe = word.lower().strip()
    # Example: you can tweak particular tricky words if needed:
    overrides = {
        # "and": "and",       # set to "and" default; try "ay nd" if you want exaggerated clarity
        # "one": "one",
        # "pin": "pin",
    }
    text = overrides.get(safe, word)
    mp3_path = out_dir / f"{safe}.mp3"
    tts = gTTS(text=text, lang=lang, slow=slow)
    tts.save(str(mp3_path))
    return mp3_path

# Local audio settings (use your scraped MW mp3s)
st.sidebar.markdown("---")
st.sidebar.subheader("Audio Source")
st.session_state.audio_dir = st.sidebar.text_input(
    "Local audio folder (MW mp3s)",
    value=str(st.session_state.get("audio_dir", AUDIO_DIR_DEFAULT)),
)
force_local = st.sidebar.checkbox(
    "Prefer local MW audio when available",
    value=True,
    help="If a local file exists for a word, play it instead of browser speech.",
)

if __name__ == "__main__":
    made = []
    for w in WORDS:
        try:
            p = speak_to_mp3(w)
            made.append(p)
            # tiny delay helps avoid rate limiting
            time.sleep(0.4)
            print(f"✓ {w} → {p}")
        except Exception as e:
            print(f"✗ Failed for {w}: {e}")

    print("\nDone!")
    print("Saved files in:", out_dir.resolve())

# In the “Hearing controls” container, replace the body of the if cc1.button("🔊 Say 3×", ...) handler with:
        p = find_local_audio_for_word(word)
        if force_local and p is not None:
            play_local_audio_loop(p, times=3, gap_ms=850)
        else:
            say_word_repeat(word, times=3, rate=0.8, gap_ms=850)

# In the “Gentle hint row” repeat buttons at the bottom, similarly modify both handlers:
# Replace the if hr1.button("🔁 Hear again (3×): block’s body with the same local-first logic as above, and keep hr2 sentence button unchanged.

# Add auto‑play support that prefers local audio too. In the existing auto‑play block (the one that starts with # Auto play on new word if present; if not present, insert it right after word = wds[idx]), ensure it tries local first:
# Auto play on new word (once per index)
if "last_spoken_idx" not in st.session_state:
    st.session_state.last_spoken_idx = -1
if st.session_state.get("auto_play", True) and st.session_state.last_spoken_idx != idx:
    p = find_local_audio_for_word(word)
    if force_local and p is not None:
        play_local_audio_loop(p, times=3, gap_ms=850)
        total_delay = 3 * (900 + 850)
        say_sentence(word, delay_ms=total_delay, rate=0.85)
    else:
        say_word_repeat(word, times=3, rate=0.8, gap_ms=850)
        total_delay = 3 * (900 + 850)
        say_sentence(word, delay_ms=total_delay, rate=0.85)
    st.session_state.last_spoken_idx = idx

# In the retry auto-speak block (after wrong answer), also prefer local. Replace its body with:
    p = find_local_audio_for_word(word)
    if force_local and p is not None:
        play_local_audio_loop(p, times=3, gap_ms=850)
    else:
        say_word_repeat(word, times=3, rate=0.8, gap_ms=850)
    total_delay = 3 * (900 + 850)
    say_sentence(word, delay_ms=total_delay, rate=0.85)
    st.session_state._retry_speak = False