def say_sentence(word: str, delay_ms: int = 0, rate: float = 0.85):
    sentence = build_sentence(word)
    st.components.v1.html(
        f"""
        <script>
          (function() {{
            const sentence = {sentence!r};
            const delay = Math.max(30, {delay_ms});  // ensure a tiny async delay
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