"""
Content Builder Agent - Streamlit Web Interface

This Streamlit UI calls the FastAPI backend (your content builder agent service).
It displays:
- assistant response text
- links to generated markdown + images served by FastAPI (/files)
"""

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import requests
import streamlit as st

# FastAPI base URL
API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000").rstrip("/")

SERVICE_ROOT_PATH = os.getenv("TFY_SERVICE_ROOT_PATH", "").rstrip("/")

def api(path: str) -> str:
    """Build URL to FastAPI endpoints considering optional root_path."""
    if SERVICE_ROOT_PATH:
        return f"{API_URL}{SERVICE_ROOT_PATH}{path}"
    return f"{API_URL}{path}"

st.set_page_config(page_title="Content Builder Agent", layout="wide")
st.title("📝 Content Builder Agent")

# Session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {role, content, meta}

with st.sidebar:
    st.header("Backend")
    st.caption("FastAPI URL")
    st.code(api(""), language="text")
    st.divider()

    st.header("Output type")
    platform = st.selectbox("Platform", ["linkedin", "blogs", "tweets"], index=0)
    st.caption("This is used to construct expected output paths for preview.")

    st.divider()
    if st.button("New conversation"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.history = []
        st.rerun()

# Main input
user_task = st.text_area(
    "What do you want to create?",
    value="Create a LinkedIn post about AI agents (and save it).",
    height=120,
)

colA, colB = st.columns([1, 1])
with colA:
    slug = st.text_input(
        "Slug (must match what the agent uses)",
        value="ai-agents",
        help="Your agent tools save to <platform>/<slug>/post.md and images to blogs/<slug>/hero.png or <platform>/<slug>/image.png",
    )

with colB:
    st.caption("Tip: Make the model deterministic by including in your prompt: "
               f'“Use platform={platform} and slug={slug} when calling write_file / generate_*”.')

run = st.button("Run agent", type="primary", use_container_width=True)

def call_agent(task: str):
    payload = {
        "thread_id": st.session_state.thread_id,
        "user_input": task,
    }
    resp = requests.post(api("/run_agent"), json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()

def file_url(rel_path: str) -> str:
    # FastAPI serves StaticFiles at /files
    return api(f"/files/{rel_path}")

if run:
    # Save user message
    st.session_state.history.append({"role": "user", "content": user_task})

    with st.spinner("Running agent..."):
        try:
            data = call_agent(user_task)

            # ---- Adjust these keys if your FastAPI response differs ----
            assistant_text = data.get("final_text") or data.get("response") or ""
            # ------------------------------------------------------------

            st.session_state.history.append({"role": "assistant", "content": assistant_text, "meta": data})

        except Exception as e:
            st.session_state.history.append({
                "role": "assistant",
                "content": f"Error calling backend: {e}"
            })

    st.rerun()

# Render conversation
st.subheader("Conversation")
for msg in st.session_state.history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"])

st.divider()
st.subheader("Outputs preview (from FastAPI /files)")

# We can't always know the slug/platform the agent used unless you enforce it.
# This section assumes you provide them (sidebar inputs).
md_rel = f"{platform}/{slug}/post.md"
md_link = file_url(md_rel)

# Blog hero image is fixed to blogs/<slug>/hero.png in your tool
hero_rel = f"blogs/{slug}/hero.png"
hero_link = file_url(hero_rel)

# Social image is <platform>/<slug>/image.png
social_rel = f"{platform}/{slug}/image.png"
social_link = file_url(social_rel)

c1, c2 = st.columns(2)
with c1:
    st.markdown("### Markdown")
    st.markdown(f"- **Expected path:** `{md_rel}`")
    st.markdown(f"- **Link:** {md_link}")

    # Try to fetch and render markdown
    try:
        r = requests.get(md_link, timeout=10)
        if r.status_code == 200 and r.text.strip():
            st.markdown(r.text)
        else:
            st.info("Markdown not found yet (or empty). Make sure the agent called write_file with the same platform/slug.")
    except Exception:
        st.info("Could not fetch markdown. Is the FastAPI server reachable and serving /files?")

with c2:
    st.markdown("### Images")

    st.markdown(f"- Blog hero: {hero_link}")
    try:
        r = requests.get(hero_link, timeout=5)
        if r.status_code == 200:
            st.image(hero_link, caption=f"{hero_rel}", use_container_width=True)
        else:
            st.caption("No hero image found.")
    except Exception:
        st.caption("Could not fetch hero image.")

    st.markdown(f"- Social image: {social_link}")
    try:
        r = requests.get(social_link, timeout=5)
        if r.status_code == 200:
            st.image(social_link, caption=f"{social_rel}", use_container_width=True)
        else:
            st.caption("No social image found.")
    except Exception:
        st.caption("Could not fetch social image.")

