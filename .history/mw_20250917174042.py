# make_spelling_audio.py
# Creates one MP3 per word using Google Text-to-Speech (no API key needed).

from gtts import gTTS
from pathlib import Path
import time

# Your list (from the photo)
WORDS = [
    "fit", "him", "is", "it", "pin", "sip", "an", "cat", "nap", "pan",
    "and", "find", "for", "just", "many", "one", "she", "then"
]

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