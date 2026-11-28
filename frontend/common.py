import os
import requests
import streamlit as st

API = os.getenv("API_URL", "http://127.0.0.1:8001")


def api_health():
    try:
        r = requests.get(f"{API}/health", timeout=3)
        return r.ok
    except Exception:
        return False


def render_item(it):
    p = it.get("payload", {})
    t = it.get("item_type")
    status = it.get("status", "draft")
    st.markdown(f"**{t.upper()}** — _{status}_")
    if t == "summary":
        st.markdown(f"**Summary:** {p.get('summary','')}")
        for k in p.get("key_points", []):
            st.markdown(f"- {k}")
    elif t == "flashcard":
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Front**"); st.info(p.get("front", ""))
        with c2:
            st.markdown("**Back**"); st.success(p.get("back", ""))
        if p.get("tags"):
            st.caption("Tags: " + ", ".join(p["tags"]))
    elif t == "mcq":
        st.markdown(f"**Question:** {p.get('stem','')}")
        for i, o in enumerate(p.get("options", [])):
            if o.get("is_correct"):
                st.success(f"✅ {chr(65+i)}. {o.get('text','')}")
            else:
                st.write(f"• {chr(65+i)}. {o.get('text','')}")
        if p.get("explanation"):
            st.caption(f"Explanation: {p.get('explanation')}")
    elif t == "short_answer":
        st.markdown(f"**Question:** {p.get('question','')}")
        st.markdown(f"**Model answer:** {p.get('model_answer','')}")
        for r in p.get("rubric", []):
            st.markdown(f"- {r.get('criterion')} ({r.get('points')} pts)")
        st.caption(f"Max points: {p.get('max_points')}")
    elif t == "answer_key":
        st.markdown(f"**Item #{p.get('item_id')} — Answer:** {p.get('answer','')}")
        if p.get("grading_notes"):
            st.caption(f"Grading notes: {p.get('grading_notes')}")
    else:
        st.json(p)
    st.caption(f"Bloom: {it.get('bloom_level')} | Quality: {it.get('quality_score')} | Model: {it.get('model')}")


def empty_state(msg, hint=""):
    st.markdown(f"<div style='text-align:center;padding:40px;color:#888;'><h3>{msg}</h3><p>{hint}</p></div>",
                unsafe_allow_html=True)


def sidebar():
    st.sidebar.title("📚 AI Learning")
    st.sidebar.caption("Content & Assessment Platform")
    st.sidebar.divider()
    st.sidebar.markdown("**Connection**")
    if api_health():
        st.sidebar.success("API connected")
    else:
        st.sidebar.error("API unreachable")
    api_url = st.sidebar.text_input("API URL", value=API)
    if api_url != API:
        os.environ["API_URL"] = api_url
        # update module global
        import common
        common.API = api_url
    st.sidebar.divider()
    dark = st.sidebar.toggle("🌙 Dark mode", value=st.session_state.get("dark_mode", False))
    st.session_state["dark_mode"] = dark
    if dark:
        st.markdown("""<style>
            .stApp { background-color: #0e1117; color: #fafafa; }
            h1,h2,h3 { color: #fafafa; }
        </style>""", unsafe_allow_html=True)