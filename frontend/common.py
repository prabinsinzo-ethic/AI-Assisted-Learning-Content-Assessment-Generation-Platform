import os
import requests
import streamlit as st

if "API_URL" not in st.session_state:
    st.session_state["API_URL"] = os.getenv("API_URL", "http://127.0.0.1:8001")
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
if "mode" not in st.session_state:
    st.session_state["mode"] = "Learner"

API = st.session_state["API_URL"]


def get_api():
    return st.session_state.get("API_URL", "http://127.0.0.1:8001")


def api_health():
    try:
        r = requests.get(f"{get_api()}/health", timeout=3)
        return r.ok
    except Exception:
        return False


def render_item(it):
    p = it.get("payload", {})
    t = it.get("item_type")
    status = it.get("status", "draft")
    st.markdown(f"**{t.upper().replace('_',' ')}** — _{status}_")
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
    # source traceability
    src = it.get("source_document")
    if src:
        with st.expander("📎 View source excerpt"):
            st.write(f"Document: **{src}**")
            if it.get("source_section"):
                st.write(f"Section: {it.get('source_section')}")
            if it.get("source_pages"):
                st.write(f"Pages: {it.get('source_pages')}")
            # fetch chunk text
            try:
                chunks = requests.get(f"{get_api()}/documents/{it['document_id']}/chunks").json()
                ids = it.get("chunk_ids", [])
                for cid in ids:
                    ch = next((c for c in chunks if c["id"] == cid), None)
                    if ch:
                        st.code(ch["text"][:500], language=None)
            except Exception:
                pass
    st.caption(f"Bloom: {it.get('bloom_level')} | Quality: {it.get('quality_score')} | Model: {it.get('model')}")


def empty_state(msg, hint=""):
    st.markdown(f"<div style='text-align:center;padding:40px;color:#888;'><h3>{msg}</h3><p>{hint}</p></div>",
                unsafe_allow_html=True)


def sidebar():
    st.sidebar.title("📚 AI Learning")
    st.sidebar.caption("Content & Assessment Platform")
    st.sidebar.divider()
    mode = st.sidebar.radio("Mode", ["Learner", "Creator / Reviewer"], index=0 if st.session_state["mode"]=="Learner" else 1)
    st.session_state["mode"] = mode
    st.sidebar.divider()
    if st.session_state["mode"] == "Creator / Reviewer":
        nav = ["🏠 Dashboard", "📄 Documents", "✅ Review Queue", "📚 Items", "🧪 Rating Study", "📖 Study Mode", "📊 Analytics", "⚙️ Settings"]
    else:
        nav = ["🏠 Dashboard", "📖 Study Mode", "📊 Analytics", "⚙️ Settings"]
    page = st.sidebar.radio("Navigate", nav, label_visibility="collapsed")
    st.session_state["page"] = page.split(" ", 1)[1]
    st.sidebar.divider()
    if api_health():
        st.sidebar.success("API connected")
    else:
        st.sidebar.error("API unreachable")