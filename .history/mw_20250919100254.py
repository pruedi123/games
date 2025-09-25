# mw.py — Streamlit "Jupiter Points" Spelling Game (Kindergarten‑friendly)
# ------------------------------------------------------------------------
# Starts with Jupiter Points = (# of words) × 1.
# For each word, the app:
#   1) Says the word 3× (local MW/TTS mp3 if available, else browser speech), then
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
import base64
import streamlit as st
import unicodedata
import io, csv, re

# ---------------------- UI Config ----------------------
st.set_page_config(page_title="Jupiter Points — Spelling Game", page_icon="🪐", layout="centered")

# tighten space after captions, and compact controls box/buttons
st.markdown(
    """
    <style>
    /* tighten space after captions */
    .st-emotion-cache-ue6h4q p, .stCaption, .st-emotion-cache-gi0tri { margin-bottom: 0.25rem !important; }
    /* compact controls box buttons */
    .controls-box .stButton > button { padding: 0.25rem 0.6rem !important; font-size: 0.9rem !important; line-height: 1.0 !important; }
    /* compact overall box padding */
    .controls-box { padding: 4px 6px !important; }
    /* reduce column gap inside the controls box */
    .controls-box .st-emotion-cache-ocqkz7, /* Streamlit column wrapper (may vary by version) */
    .controls-box [data-testid="stHorizontalBlock"] { gap: 0.25rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------- Defaults ----------------------
DEFAULT_WORDS: List[str] = [
    "fit", "him", "is", "it", "pin", "sip", "an", "cat",
    "nap", "pan", "and", "find", "for", "just", "many", "one", "she", "then"
]

# ---------------------- Local Audio (MW scraped/downloaded or TTS) ----------------------
AUDIO_DIR_DEFAULT = Path(__file__).parent / "audio_tts"  # default folder for your mp3s
AUDIO_EXTS = (".mp3", ".wav", ".m4a")

SENT_AUDIO_DIR_DEFAULT = Path(__file__).parent / "audio_sentences"

def get_sentence_audio_dir() -> Path:
    p = st.session_state.get("sentence_audio_dir")
    try:
        return Path(p) if p else SENT_AUDIO_DIR_DEFAULT
    except Exception:
        return SENT_AUDIO_DIR_DEFAULT

def find_local_sentence_audio(word: str) -> Path | None:
    base = get_sentence_audio_dir()
    if not base.exists():
        return None
    wl = word.lower()
    # prefer explicit "_sentence" name first
    for ext in AUDIO_EXTS:
        p = base / f"{wl}_sentence{ext}"
        if p.exists():
            return p
    # fallback to "word.ext"
    for ext in AUDIO_EXTS:
        p = base / f"{wl}{ext}"
        if p.exists():
            return p
    # looser matches
    for ext in AUDIO_EXTS:
        for p in base.glob(f"{wl}*{ext}"):
            return p
    return None

def play_local_audio_once(path: Path, playback_rate: float = 1.0):
    ext = path.suffix.lower()
    mime = (
        "audio/mpeg" if ext == ".mp3" else
        "audio/wav"  if ext == ".wav" else
        "audio/mp4"
    )
    try:
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        st.warning(f"Couldn't read sentence audio file: {path}")
        return
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            var rate = {playback_rate};
            var src = 'data:{mime};base64,{b64}';
            var audio = new Audio(src);
            audio.playbackRate = rate;
            audio.play();
          }})();
        </script>
        """,
        height=0,
    )

def get_audio_dir() -> Path:
    p = st.session_state.get("audio_dir")
    try:
        return Path(p) if p else AUDIO_DIR_DEFAULT
    except Exception:
        return AUDIO_DIR_DEFAULT

def find_local_audio_for_word(word: str) -> Path | None:
    base = get_audio_dir()
    if not base.exists():
        return None
    wl = word.lower()
    for ext in AUDIO_EXTS:
        p = base / f"{wl}{ext}"
        if p.exists():
            return p
    for ext in AUDIO_EXTS:
        for p in base.glob(f"{wl}*{ext}"):
            return p
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

# --- Browser SpeechSynthesis fallback (when no local file) ---

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
              try {{ speechSynthesis.cancel(); }} catch (e) {{}}
              speechSynthesis.speak(u);
            }}
            try {{ speechSynthesis.cancel(); }} catch (e) {{}}
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
            const delay = Math.max(30, {delay_ms});
            const rate = {rate};
            function speak() {{
              try {{ speechSynthesis.cancel(); }} catch (e) {{}}
              const u = new SpeechSynthesisUtterance(sentence);
              u.lang = 'en-US';
              u.rate = rate;   // slower for kinders if requested
              u.pitch = 0.95;
              speechSynthesis.speak(u);
            }}
            try {{ speechSynthesis.cancel(); }} catch (e) {{}}
            setTimeout(speak, delay);
          }})();
        </script>
        """,
        height=0,
    )

HAS_GTTS = False
try:
    from gtts import gTTS  # optional, only for sentence file generation
    HAS_GTTS = True
except Exception:
    HAS_GTTS = False


def say_sentence_on_click(word: str, kinder: bool):
    # If user prefers local sentence audio and a file exists, play it; else browser TTS
    if st.session_state.get("prefer_local_sentence_audio", True):
        p = find_local_sentence_audio(word)
        if p is not None:
            play_local_audio_once(p, playback_rate=(0.6 if kinder else 1.0))
            return
    # Fallback to browser TTS
    say_sentence(word, delay_ms=0, rate=(0.6 if kinder else 0.85))

# --- Short feedback speaker (browser TTS) ---


def say_feedback(text: str, kinder: bool = False):
    rate = 0.6 if kinder else 0.95
    safe = text.replace("\\", "\\\\").replace("'", "\\'")
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            try {{ speechSynthesis.cancel(); }} catch (e) {{}}
            const u = new SpeechSynthesisUtterance('{safe}');
            u.lang = 'en-US'; u.rate = {rate}; u.pitch = 1.0;
            speechSynthesis.speak(u);
          }})();
        </script>
        """,
        height=0,
    )

# --- Confetti celebration (canvas-confetti) ---

def confetti_burst():
    st.components.v1.html(
        """
        <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
        <script>
          (function() {
            try {
              // main burst
              confetti({ particleCount: 120, spread: 70, origin: { y: 0.6 } });
              // secondary burst for fuller feel
              setTimeout(() => confetti({ particleCount: 90, spread: 100, startVelocity: 45, origin: { y: 0.7 } }), 200);
            } catch (e) {}
          })();
        </script>
        """,
        height=0,
    )

# --- Super‑clear sentence helpers (word‑by‑word, optional spell‑out) ---

def _js_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")

def say_letters_word(word: str, letter_gap_ms: int = 350, rate: float = 0.35):
    letters = " ".join(list(word.upper()))
    js_text = _js_escape(letters)
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const txt = '{js_text}';
            const parts = txt.split(' ');
            const gap = {letter_gap_ms};
            const rate = {rate};
            let i = 0;
            function speakOne() {{
              if (i >= parts.length) return;
              const u = new SpeechSynthesisUtterance(parts[i]);
              u.lang = 'en-US';
              u.rate = rate;
              u.pitch = 1.0;
              u.onend = () => {{ i += 1; setTimeout(speakOne, gap); }};
              try {{ speechSynthesis.cancel(); }} catch (e) {{}}
              speechSynthesis.speak(u);
            }}
            try {{ speechSynthesis.cancel(); }} catch (e) {{}}
            speakOne();
          }})();
        </script>
        """,
        height=0,
    )

def say_super_clear_sentence(word: str, kinder: bool, gap_ms: int = 450, pre_repeat: int = 2, rate: float | None = None):
    # Speak the target word slowly a couple times, then the sentence word-by-word with short gaps
    sentence = build_sentence(word)
    tokens = sentence.split()
    r = (0.35 if kinder else 0.7) if rate is None else rate
    js_tokens = [_js_escape(t) for t in tokens]
    w = _js_escape(word)
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const gap = {gap_ms};
            const rate = {r};
            const target = '{w}';
            const tokens = {js_tokens};
            let phase = 0; // 0 = pre repeats, 1 = sentence
            let preLeft = {pre_repeat};
            let i = 0;
            function speakNext() {{
              try {{ speechSynthesis.cancel(); }} catch (e) {{}}
              if (phase === 0) {{
                if (preLeft <= 0) {{ phase = 1; return setTimeout(speakNext, gap); }}
                const u = new SpeechSynthesisUtterance(target);
                u.lang = 'en-US'; u.rate = rate; u.pitch = 1.0;
                u.onend = () => {{ preLeft--; setTimeout(speakNext, gap); }};
                speechSynthesis.speak(u);
                return;
              }}
              if (i >= tokens.length) return;
              const u = new SpeechSynthesisUtterance(tokens[i]);
              u.lang = 'en-US'; u.rate = rate; u.pitch = 1.0;
              u.onend = () => {{ i++; setTimeout(speakNext, gap); }};
              speechSynthesis.speak(u);
            }}
            speakNext();
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
        ss.attempted_penalty = False  # kept for compatibility; not used in simplified mode
    if "total_points" not in ss:
        ss.total_points = len(ss.words)
    if "current_points" not in ss:
        ss.current_points = 0
    if "listen_nonce" not in ss:
        ss.listen_nonce = 0
    if "last_feedback" not in ss:
        ss.last_feedback = ""
    if "auto_play" not in ss:
        ss.auto_play = False  # default to manual playback; Say 3× required
    if "last_spoken_idx" not in ss:
        ss.last_spoken_idx = -1
    if "_retry_speak" not in ss:
        ss._retry_speak = False  # kept for compatibility; not used in simplified mode
    if "sentence_audio_dir" not in ss:
        ss.sentence_audio_dir = str(SENT_AUDIO_DIR_DEFAULT)
    if "prefer_local_sentence_audio" not in ss:
        ss.prefer_local_sentence_audio = True
    if "suppress_autoplay_once" not in ss:
        ss.suppress_autoplay_once = False

    # Track last processed upload to avoid reprocessing on rerun
    if "last_upload_key" not in ss:
        ss.last_upload_key = None

    # Feedback/visuals flags for next render
    if "pending_feedback" not in ss:
        ss.pending_feedback = None  # 'right' | 'wrong' | None
    if "pending_confetti" not in ss:
        ss.pending_confetti = False

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
    st.session_state.current_points = 0
    st.session_state.attempted_penalty = False
    st.session_state.last_feedback = ""
    st.session_state.last_spoken_idx = -1
    st.session_state._retry_speak = False
    st.session_state.listen_nonce += 1
    st.session_state.auto_play = False
    st.rerun()
if col_b.button("Restart", use_container_width=True):
    st.session_state.idx = 0
    st.session_state.current_points = 0
    st.session_state.attempted_penalty = False
    st.session_state.last_feedback = ""
    st.session_state.last_spoken_idx = -1
    st.session_state._retry_speak = False
    st.session_state.listen_nonce += 1
    st.session_state.auto_play = False
    st.rerun()

# --- File uploader for word lists (.txt, .csv, .pdf) ---
uploaded = st.sidebar.file_uploader("Upload word list (.txt, .csv, .pdf)", type=["txt","csv","pdf"])

def parse_text_to_words(text: str):
    # Normalize: -> lower, split on non-alpha, keep short alpha tokens
    tokens = re.split(r"[^A-Za-z']+", text)
    words = []
    for t in tokens:
        if not t:
            continue
        w = t.strip().lower()
        if w.isalpha() and 1 <= len(w) <= 12:
            words.append(w)
    return words

if uploaded is not None:
    name = uploaded.name.lower()
    raw_bytes = uploaded.getvalue()
    key = (name, len(raw_bytes))

    # Avoid re-parsing the same uploaded file on rerun
    if st.session_state.get("last_upload_key") == key:
        pass  # do nothing; already loaded
    else:
        final_words = []
        try:
            if name.endswith(".txt"):
                raw = raw_bytes.decode("utf-8", errors="ignore")
                final_words = parse_text_to_words(raw)
            elif name.endswith(".csv"):
                raw = raw_bytes.decode("utf-8", errors="ignore")
                rows = list(csv.reader(io.StringIO(raw)))
                if rows:
                    # choose best column by most short word-like tokens
                    cols = list(zip(*rows))
                    best_col = None; best_score = -1
                    for col in cols:
                        s = " ".join(col)
                        ws = parse_text_to_words(s)
                        score = sum(1 for w in ws if 1 <= len(w) <= 10)
                        if score > best_score:
                            best_score = score; best_col = col
                    if best_col:
                        buf = " ".join(best_col)
                        final_words = parse_text_to_words(buf)
            elif name.endswith(".pdf"):
                text = ""
                # try pdfplumber first for better layout
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                        for page in pdf.pages:
                            text += "\n" + (page.extract_text() or "")
                except Exception:
                    try:
                        from PyPDF2 import PdfReader
                        reader = PdfReader(io.BytesIO(raw_bytes))
                        for p in reader.pages:
                            text += "\n" + (p.extract_text() or "")
                    except Exception:
                        text = ""
                final_words = parse_text_to_words(text)
        except Exception as e:
            st.sidebar.error(f"Failed to parse file: {e}")
            final_words = []

        # Dedupe while preserving order; keep first‑grade friendly length
        seen = set(); cleaned = []
        for w in final_words:
            if 1 <= len(w) <= 10 and w.isalpha() and w not in seen:
                seen.add(w); cleaned.append(w)

        if cleaned:
            st.session_state.words = cleaned
            st.session_state.idx = 0
            st.session_state.total_points = len(cleaned)
            st.session_state.current_points = 0
            st.session_state.last_feedback = ""
            st.session_state.last_spoken_idx = -1
            st.session_state.listen_nonce += 1
            st.session_state.auto_play = False
            st.session_state.suppress_autoplay_once = True  # require teacher to click Say 3×
            st.session_state.last_upload_key = key
            st.success(f"Loaded {len(cleaned)} words from {uploaded.name}")
            st.rerun()
        else:
            st.sidebar.warning("No valid words found in the uploaded file.")

st.sidebar.markdown("---")
st.sidebar.caption("Tip: After each answer, click **Say 3×** to hear the next word. The Sentence button is optional.")
st.session_state.audio_dir = st.sidebar.text_input(
    "Local audio folder (mp3s)",
    value=str(st.session_state.get("audio_dir", AUDIO_DIR_DEFAULT)),
)
force_local = st.sidebar.checkbox(
    "Prefer local audio when available",
    value=True,
    help="If a local file exists for a word, play it instead of browser speech.",
)
st.sidebar.checkbox("Auto play each word (3× then sentence)", value=st.session_state.auto_play, key="auto_play")
kinder = st.sidebar.checkbox("Kindergarten Mode (very slow)", value=False, help="Speak extra-slow like to a 5-year-old.")

st.sidebar.markdown("---")
st.sidebar.subheader("Sentence Audio")
st.session_state.sentence_audio_dir = st.sidebar.text_input(
    "Sentence audio folder",
    value=str(st.session_state.get("sentence_audio_dir", SENT_AUDIO_DIR_DEFAULT)),
)
st.sidebar.checkbox(
    "Prefer local sentence audio when available",
    value=st.session_state.get("prefer_local_sentence_audio", True),
    key="prefer_local_sentence_audio",
)
# Optional: one-click TTS generation for sentences
if HAS_GTTS and st.sidebar.button("Generate TTS sentence files for this list"):
    outdir = get_sentence_audio_dir()
    outdir.mkdir(parents=True, exist_ok=True)
    made, fails = 0, []
    for w in st.session_state.words:
        try:
            text = build_sentence(w)
            mp = outdir / f"{w.lower()}_sentence.mp3"
            gTTS(text=text, lang="en", slow=True).save(str(mp))
            made += 1
        except Exception as e:
            fails.append(w)
    if made:
        st.success(f"Generated {made} sentence file(s) in {outdir}")
    if fails:
        st.warning("Failed: " + ", ".join(fails))

st.sidebar.markdown("---")
st.sidebar.subheader("Clarity Options")
super_clear = st.sidebar.checkbox("Super‑clear sentence (word‑by‑word)", value=True,
                                  help="Repeat the target word and speak the sentence one word at a time with small pauses.")
spell_out = st.sidebar.checkbox("Spell out the target word first", value=False,
                                help="Say the word letter‑by‑letter before the sentence.")
sentence_gap = st.sidebar.number_input("Sentence word gap (ms)", min_value=200, max_value=2000, value=500, step=50)
pre_repeat = st.sidebar.number_input("Repeat target word before sentence", min_value=0, max_value=5, value=2, step=1)
# keep in session for use inside button handler above
st.session_state.sentence_gap = int(sentence_gap)
st.session_state.pre_repeat = int(pre_repeat)

# ---------------------- Main UI -----------------------
st.title("🪐 Jupiter Points — Spelling Game")
st.caption("Type the spelling and press Check. After feedback, click **Say 3×** to hear the next word.")

wds = st.session_state.words
N = len(wds)
idx = st.session_state.idx
points = st.session_state.current_points
start_points = st.session_state.total_points

st.markdown(f"**Word:** {idx+1} / {N}  &nbsp;|&nbsp;  **Jupiter Dollars:** {points} / {N}")

# --- Bucket UI and gold bar drop animation ---

def render_bucket_ui(current: int):
    # Renders a small bucket bar with count; bucket area is target for bar drop animation
    st.components.v1.html(
        f"""
        <div id=\"bucketWrap\" style=\"display:flex;align-items:center;gap:8px;margin:6px 0 10px 0;\">
          <div id=\"bucket\" style=\"position:relative;width:46px;height:46px;border-radius:6px;border:2px solid #999;background:#eaeaea;display:flex;align-items:center;justify-content:center;\">🪣</div>
          <div style=\"font-weight:600;\">Gold in bucket: {current}</div>
        </div>
        """,
        height=60,
    )

def gold_bar_drop():
    # Animates a gold bar dropping into the bucket element
    st.components.v1.html(
        """
        <style>
          @keyframes dropBar { from { transform: translateY(-120px) scale(1); opacity:0.9; } to { transform: translateY(0) scale(1); opacity:1; } }
        </style>
        <script>
          (function(){
            try {
              const bucket = document.getElementById('bucket');
              if(!bucket){ return; }
              const rect = bucket.getBoundingClientRect();
              const bar = document.createElement('div');
              bar.style.position = 'fixed';
              bar.style.left = (rect.left + rect.width/2 - 16) + 'px';
              bar.style.top = (rect.top - 20) + 'px';
              bar.style.width = '32px';
              bar.style.height = '14px';
              bar.style.borderRadius = '3px';
              bar.style.background = 'linear-gradient(180deg,#ffd54f,#fbc02d)';
              bar.style.border = '1px solid #b28900';
              bar.style.boxShadow = '0 2px 6px rgba(0,0,0,0.25)';
              bar.style.zIndex = 9999;
              document.body.appendChild(bar);
              bar.animate([{ transform:'translateY(-120px)', opacity:0.9 },{ transform:'translateY(0)', opacity:1 }], { duration: 550, easing: 'cubic-bezier(.2,.7,.2,1)' });
              setTimeout(()=>{ bar.remove(); }, 600);
            } catch(e){}
          })();
        </script>
        """,
        height=0,
    )

render_bucket_ui(points)

# Small note about audio sources
st.caption("Word uses local audio when available; Sentence uses local sentence audio (if provided) or the browser voice.")

# End-of-list summary and restart
if idx >= N:
    st.success("All words complete! 🎉")
    st.markdown(f"**Final Jupiter Dollars:** {st.session_state.current_points} / {N}")
    col_r1, col_r2 = st.columns(2)
    if col_r1.button("🔁 Try the list again", use_container_width=True):
        st.session_state.idx = 0
        st.session_state.current_points = 0
        st.session_state.last_feedback = ""
        st.session_state.last_spoken_idx = -1
        st.session_state.listen_nonce += 1
    if col_r2.button("Edit word list", use_container_width=True):
        pass  # no-op, just leaves them on the page to edit sidebar list
    st.balloons()
    st.stop()

word = wds[idx]

# Show which local file will be used (if any) — prepare text, render inside the first container to reduce spacing
p_preview = find_local_audio_for_word(word)
preview_text = f"Using local audio: {p_preview.name}" if p_preview is not None else ""


# Auto play on new word (once per index): say the word 3× only (unless suppressed once)
if st.session_state.last_spoken_idx != idx:
    if st.session_state.auto_play and not st.session_state.suppress_autoplay_once:
        p = find_local_audio_for_word(word)
        if force_local and p is not None:
            play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
        else:
            say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
    else:
        # consume the suppression for this word so future words can autoplay again
        st.session_state.suppress_autoplay_once = False
    st.session_state.last_spoken_idx = idx

# Hearing controls
with st.container(border=True):
    st.markdown("<div class='controls-box'>", unsafe_allow_html=True)
    if preview_text:
        st.caption(preview_text)
        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)
    if cc1.button("🔊 Say Next Word 3×", use_container_width=True):
        p = find_local_audio_for_word(word)
        if force_local and p is not None:
            play_local_audio_loop(p, times=3, gap_ms=850, playback_rate=(0.6 if kinder else 1.0))
        else:
            say_word_repeat(word, times=3, rate=(0.35 if kinder else 0.8), gap_ms=850)
    if cc2.button("🔊 Sentence", use_container_width=True):
        if super_clear:
            if spell_out:
                say_letters_word(word, letter_gap_ms=350, rate=(0.3 if kinder else 0.5))
            say_super_clear_sentence(
                word,
                kinder=kinder,
                gap_ms=int(st.session_state.get("sentence_gap", 500)),
                pre_repeat=int(st.session_state.get("pre_repeat", 2))
            )
        else:
            say_sentence_on_click(word, kinder)
    st.markdown("</div>", unsafe_allow_html=True)

# Input and checking
st.markdown("**Type the word you heard:**")
with st.form(key=f"listen_form_{st.session_state.listen_nonce}"):
    guess = st.text_input("Your spelling", value="", key=f"guess_{st.session_state.listen_nonce}")
    submitted = st.form_submit_button("Check ✔️")

if submitted:
    # Canonicalize input and target: normalize Unicode and remove all whitespace
    g_raw = guess or ""
    g = ''.join(unicodedata.normalize("NFKC", g_raw).split()).lower()
    target = ''.join(unicodedata.normalize("NFKC", word).split()).lower()

    correct = (g == target)
    if correct:
        # Immediate audio + confetti
        say_feedback("You got it right!", kinder)
        confetti_burst()
        gold_bar_drop()
        st.session_state.current_points += 1
        st.session_state.last_feedback = "✅ You were right!  —  Click **Say 3×** to hear the next word."
    else:
        # Immediate audio for wrong
        say_feedback("Not quite right, let's move to next word", kinder)
        st.session_state.last_feedback = "❌ Not quite right — Click **Say Next Word 3×** to hear the next word."

    # ensure no delayed playback repeats
    st.session_state.pending_feedback = None
    st.session_state.pending_confetti = False

    # Require manual playback on next word
    st.session_state.suppress_autoplay_once = True

    # Always advance to the next word
    st.session_state.idx += 1
    st.session_state.listen_nonce += 1
    st.session_state.last_spoken_idx = -1



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
    if super_clear:
        if spell_out:
            say_letters_word(word, letter_gap_ms=350, rate=(0.3 if kinder else 0.5))
        say_super_clear_sentence(
            word,
            kinder=kinder,
            gap_ms=int(st.session_state.get("sentence_gap", 500)),
            pre_repeat=int(st.session_state.get("pre_repeat", 2))
        )
    else:
        say_sentence_on_click(word, kinder)