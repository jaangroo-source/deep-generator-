import streamlit as st
import asyncio, os, tempfile, subprocess, urllib.parse, re, random
import requests, edge_tts
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips
from PIL import Image
import numpy as np

st.set_page_config(page_title="Deep Generator", page_icon="🎬", layout="centered")
st.title("🎬 Deep Generator")

CACHE_DIR = os.path.join(tempfile.gettempdir(), "deep_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def audio_duration(path):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path]))
    except: return 3.0

def gen_image(prompt, path):
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        r = requests.get(url, params={"width": 1280, "height": 720, "nologo": "true", "model": "flux"}, timeout=120)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    except:
        Image.new("RGB", (1280, 720), (25, 25, 45)).save(path)

async def _edge_tts(text, voice, ap):
    comm = edge_tts.Communicate(text, voice)
    with open(ap, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio": f.write(ch["data"])

def edge_tts_sync(text, voice, ap):
    asyncio.run(_edge_tts(text, voice, ap))

def ken_burns(ip, dur):
    img = Image.open(ip).convert("RGB"); iw, ih = img.size
    def frame(t):
        z = 1.0 + 0.15 * (t / dur)
        cw, ch = int(iw / z), int(ih / z)
        ox, oy = (iw - cw) // 2, (ih - ch) // 2
        return np.array(img.crop((ox, oy, ox + cw, oy + ch)).resize((1280, 720), Image.LANCZOS))
    return VideoClip(frame, duration=dur)

# --- UI ---
story = st.text_area("Story (Manual)", placeholder="Ek billi thi. Woh chhat pe gayi...")
voice = st.selectbox("Voice", ["ur-PK-AsadNeural", "en-US-AriaNeural", "hi-IN-MadhurNeural"])

if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "images" not in st.session_state:
    st.session_state.images = []

if st.button("1. Generate Images (Preview)"):
    if not story.strip():
        st.error("Story likhein!")
    else:
        with st.spinner("Images ban rahi hain..."):
            sents = [s.strip() for s in re.split(r'(?<=[.!?।])\s+', story) if s.strip()][:10]
            st.session_state.scenes = [{"text": s, "image_prompt": f"{s}, storybook illustration, no text"} for s in sents]
            st.session_state.images = []
            wd = tempfile.mkdtemp()
            for i, sc in enumerate(st.session_state.scenes):
                p = os.path.join(wd, f"p{i}.jpg")
                gen_image(sc["image_prompt"], p)
                st.session_state.images.append(p)
            st.success(f"{len(st.session_state.scenes)} images ready!")

if st.session_state.images:
    st.image(st.session_state.images, width=300, caption=[f"Scene {i+1}" for i in range(len(st.session_state.images))])

if st.button("2. Render Video", type="primary"):
    if not st.session_state.scenes:
        st.error("Pehle Images generate karein (Step 1)!")
    else:
        with st.spinner("Video ban rahi hai... (Thoda waqt lagega)"):
            wd = tempfile.mkdtemp()
            clips = []
            for i, sc in enumerate(st.session_state.scenes):
                ap = os.path.join(wd, f"a{i}.mp3")
                edge_tts_sync(sc["text"], voice, ap)
                dur = max(2.0, audio_duration(ap))
                clip = ken_burns(st.session_state.images[i], dur).with_audio(AudioFileClip(ap))
                clips.append(clip)
            final = concatenate_videoclips(clips, method="compose").with_fps(24)
            raw = os.path.join(wd, "final.mp4")
            final.write_videofile(raw, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
            
            st.success("Video Ready!")
            st.video(raw)
