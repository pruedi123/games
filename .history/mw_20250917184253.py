st.markdown(f"**Word:** {idx+1} / {N}  &nbsp;|&nbsp;  **Jupiter Points:** {points} / {start_points}")

if idx >= N:
    st.success("All words complete! 🎉")
    st.balloons()
    st.stop()

# Current target word
word = wds[idx]

# Show which local file will be used (if any)
p_preview = find_local_audio_for_word(word)
if p_preview is not None:
    st.caption(f"Using local audio: {p_preview.name}")