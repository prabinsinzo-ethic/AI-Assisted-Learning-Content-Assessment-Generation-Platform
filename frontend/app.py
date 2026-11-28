import os
import requests
import time
import json as _json
import streamlit as st
import streamlit.components.v1 as components
from common import sidebar, render_item, empty_state

st.set_page_config(page_title="AI Learning Content Platform", layout="wide", page_icon="📚")
API = __import__("common").API

# ---------- Custom CSS ----------
st.markdown("""
<style>
    .main .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }
    h1, h2, h3 { color: #1f3864; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 10px 18px; font-weight: 600; }
    .card { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 14px;
            padding: 24px; margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .flashcard { perspective: 1000px; min-height: 200px; }
    .flashcard-inner { position: relative; width: 100%; min-height: 200px; text-align: center;
                       transition: transform 0.6s; transform-style: preserve-3d; }
    .flashcard.flipped .flashcard-inner { transform: rotateY(180deg); }
    .flashcard-front, .flashcard-back { position: absolute; width: 100%; min-height: 200px;
        backface-visibility: hidden; border-radius: 14px; padding: 24px; display: flex;
        align-items: center; justify-content: center; font-size: 1.2rem; }
    .flashcard-front { background: #e7f1ff; color: #0d6efd; }
    .flashcard-back { background: #d4edda; color: #155724; transform: rotateY(180deg); }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;
             font-weight: 600; margin-right: 6px; }
    .badge-draft { background: #fff3cd; color: #856404; }
    .badge-approved { background: #d4edda; color: #155724; }
    .badge-rejected { background: #f8d7da; color: #721c24; }
    .empty-state { text-align: center; padding: 50px; color: #888; }
    .metric-card { background: white; border-radius: 12px; padding: 14px; text-align: center;
                   border: 1px solid #eee; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

sidebar()

st.title("📚 AI Learning Content & Assessment Platform")
st.caption("Upload, generate, study, and track your learning progress.")

page = st.sidebar.radio("Navigate", [
    "🏠 Dashboard", "📄 Upload & Study", "✅ Review Queue", "📚 Items",
    "🧪 Rating Study", "📖 Study Mode", "⚙️ Settings"
])

# ---------- Dashboard ----------
if page == "🏠 Dashboard":
    st.header("Dashboard")
    try:
        docs = requests.get(f"{API}/documents").json()
        items = requests.get(f"{API}/items").json()
    except Exception:
        docs, items = [], []
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", len(docs))
    c2.metric("Total Items", len(items))
    c3.metric("Approved", sum(1 for i in items if i.get("status") == "approved"))
    c4.metric("Pending", sum(1 for i in items if i.get("status") == "draft"))
    st.divider()
    st.subheader("Quick Start")
    st.markdown("""
    - **Upload & Study**: upload files, generate content, and study in one place
    - **Review Queue**: approve or reject generated items
    - **Items**: browse, edit, view versions
    - **Rating Study**: blind evaluation
    - **Study Mode**: flashcards and quizzes
    """)
    if not docs:
        empty_state("No documents yet", "Upload your first textbook or notes to get started.")

# ---------- Upload & Study Workspace ----------
elif page == "📄 Upload & Study":
    st.header("Upload & Study Workspace")
    title = st.text_input("Title")
    uploaded = st.file_uploader("File", type=["txt", "pdf", "docx"])
    if st.button("Upload") and uploaded and title:
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")}
        r = requests.post(f"{API}/documents", data={"title": title}, files=files)
        if r.ok:
            st.success(f"Uploaded document #{r.json()['id']}")
            st.session_state["selected_doc"] = r.json()["id"]
        else:
            st.error(r.text)
    # URL/YouTube
    with st.expander("Or ingest from URL / YouTube"):
        url_title = st.text_input("Title (optional)", key="url_title")
        url_val = st.text_input("URL", key="url_val")
        c1, c2 = st.columns(2)
        if c1.button("Ingest URL"):
            r = requests.post(f"{API}/documents/url", json={"url": url_val, "title": url_title or None})
            if r.ok:
                st.success(f"Ingested document #{r.json()['id']}")
                st.session_state["selected_doc"] = r.json()["id"]
            else:
                st.error(r.text)
        if c2.button("Ingest YouTube"):
            r = requests.post(f"{API}/documents/youtube", json={"url": url_val, "title": url_title or None})
            if r.ok:
                st.success(f"Ingested document #{r.json()['id']}")
                st.session_state["selected_doc"] = r.json()["id"]
            else:
                st.error(r.text)

    st.divider()
    try:
        docs = requests.get(f"{API}/documents").json()
    except Exception as e:
        docs = []
        st.error(e)
    if not docs:
        empty_state("No documents", "Upload a file to begin.")
    else:
        doc_map = {f"{d['id']}: {d['title']}": d["id"] for d in docs}
        default_label = None
        if "selected_doc" in st.session_state:
            for lbl, did in doc_map.items():
                if did == st.session_state["selected_doc"]:
                    default_label = lbl
        selected_doc_label = st.selectbox("Select document", list(doc_map.keys()),
                                         index=list(doc_map.keys()).index(default_label) if default_label else 0)
        selected_doc = doc_map[selected_doc_label]
        try:
            chunks = requests.get(f"{API}/documents/{selected_doc}/chunks").json()
            st.info(f"{len(chunks)} chunks extracted")
        except Exception:
            chunks = []

        st.subheader("Generate Content")
        types = st.multiselect("Content types", ["summary", "flashcard", "mcq", "short_answer", "answer_key"])
        items_per = st.number_input("Items per chunk", min_value=1, max_value=5, value=1)
        if st.button("Generate"):
            if not types:
                st.warning("Select at least one content type.")
            else:
                r = requests.post(f"{API}/jobs/generate", json={
                    "document_id": selected_doc, "types": types, "items_per_chunk": items_per
                })
                if r.ok:
                    job_id = r.json()["job_id"]
                    st.info(f"Job {job_id} started")
                    progress = st.progress(0.0)
                    for _ in range(60):
                        time.sleep(1)
                        s = requests.get(f"{API}/jobs/{job_id}").json()
                        progress.progress(s.get("progress", 0.0))
                        if s["status"] in ("done", "failed", "cancelled"):
                            break
                    if s["status"] == "done":
                        st.success(f"Done! Created {len(s.get('result_ids', []))} items.")
                    else:
                        st.error(s.get("message", "Failed"))
                else:
                    st.error(r.text)

        # Study tabs
        st.divider()
        try:
            items = requests.get(f"{API}/items", params={"document_id": selected_doc}).json()
        except Exception:
            items = []
        tabs = st.tabs(["Summary", "Flashcards", "MCQ Quiz", "Short Questions", "AI Tutor"])
        with tabs[0]:
            sums = [i for i in items if i["item_type"] == "summary"]
            if not sums:
                empty_state("No summaries", "Generate summary content first.")
            for it in sums:
                render_item(it)
        with tabs[1]:
            cards = [i for i in items if i["item_type"] == "flashcard"]
            if not cards:
                empty_state("No flashcards", "Generate flashcard content first.")
            for it in cards:
                p = it["payload"]
                st.markdown(f'<div class="flashcard"><div class="flashcard-inner">'
                            f'<div class="flashcard-front">{p.get("front","")}</div>'
                            f'<div class="flashcard-back">{p.get("back","")}</div>'
                            f'</div></div>', unsafe_allow_html=True)
                st.caption("Hover to flip (CSS) — use Study Mode for interactive review.")
        with tabs[2]:
            mcqs = [i for i in items if i["item_type"] == "mcq"]
            if not mcqs:
                empty_state("No MCQs", "Generate MCQ content first.")
            for it in mcqs:
                p = it["payload"]
                st.markdown(f"**{p.get('stem','')}**")
                for i, o in enumerate(p.get("options", [])):
                    if o.get("is_correct"):
                        st.success(f"✅ {chr(65+i)}. {o.get('text','')}")
                    else:
                        st.write(f"• {chr(65+i)}. {o.get('text','')}")
                if p.get("explanation"):
                    st.caption(f"Explanation: {p.get('explanation')}")
        with tabs[3]:
            sas = [i for i in items if i["item_type"] == "short_answer"]
            if not sas:
                empty_state("No short questions", "Generate short-answer content first.")
            for it in sas:
                p = it["payload"]
                st.markdown(f"**Q:** {p.get('question','')}")
                st.markdown(f"**Model answer:** {p.get('model_answer','')}")
                ans = st.text_area("Your answer", key=f"sa_{it['id']}")
                if st.button("Grade", key=f"grade_{it['id']}"):
                    r = requests.post(f"{API}/study-suite/grade", json={
                        "question": p.get("question", ""), "model_answer": p.get("model_answer", ""),
                        "rubric": p.get("rubric", []), "max_points": p.get("max_points", 1),
                        "student_answer": ans,
                    })
                    if r.ok:
                        d = r.json()
                        st.success(f"Score: {d['score']}/{d['max_points']}")
                        st.write(d.get("feedback", ""))
                    else:
                        st.error(r.text)
        with tabs[4]:
            st.markdown("Ask questions about your uploaded material.")
            if "chat_history" not in st.session_state:
                st.session_state["chat_history"] = []
            for msg in st.session_state["chat_history"]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
            if prompt := st.chat_input("Ask the tutor..."):
                st.session_state["chat_history"].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.write(prompt)
                r = requests.post(f"{API}/study-suite/chat", json={
                    "document_id": selected_doc, "message": prompt,
                    "history": st.session_state["chat_history"][:-1],
                })
                if r.ok:
                    d = r.json()
                    reply = d.get("answer", "")
                    sources = d.get("sources", [])
                    st.session_state["chat_history"].append({"role": "assistant", "content": reply})
                    with st.chat_message("assistant"):
                        st.write(reply)
                        if sources:
                            st.caption(f"Sources: {sources}")
                else:
                    st.error(r.text)

# ---------- Review Queue ----------
elif page == "✅ Review Queue":
    st.header("Review Queue")
    rq_doc = st.number_input("Document ID", min_value=1, value=1, key="rqdoc")
    rq_type = st.selectbox("Type filter", ["", "summary", "flashcard", "mcq", "short_answer", "answer_key"], key="rqtype")
    params = {"document_id": rq_doc, "status": "draft"}
    if rq_type:
        params["item_type"] = rq_type
    try:
        pending = requests.get(f"{API}/items", params=params).json()
    except Exception as e:
        pending = []
        st.error(e)
    st.write(f"**{len(pending)}** items pending review")
    if not pending:
        empty_state("No pending items", "Generate content or change filters.")
    selected_ids = []
    for it in pending:
        with st.container():
            st.markdown(f"**Item {it['id']}** — {it['item_type']}")
            render_item(it)
            c1, c2, c3 = st.columns([1, 1, 4])
            if c1.button("✅ Approve", key=f"appr_{it['id']}"):
                requests.patch(f"{API}/items/{it['id']}", json={"status": "approved"})
                st.rerun()
            if c2.button("❌ Reject", key=f"rej_{it['id']}"):
                requests.patch(f"{API}/items/{it['id']}", json={"status": "rejected"})
                st.rerun()
            if c3.checkbox("Select", key=f"sel_{it['id']}"):
                selected_ids.append(it["id"])
    if selected_ids:
        st.divider()
        c1, c2 = st.columns(2)
        if c1.button(f"Approve {len(selected_ids)} selected"):
            for iid in selected_ids:
                requests.patch(f"{API}/items/{iid}", json={"status": "approved"})
            st.rerun()
        if c2.button(f"Reject {len(selected_ids)} selected"):
            for iid in selected_ids:
                requests.patch(f"{API}/items/{iid}", json={"status": "rejected"})
            st.rerun()

# ---------- Items ----------
elif page == "📚 Items":
    st.header("All Items")
    did = st.number_input("Document ID", min_value=1, value=1)
    itype = st.selectbox("Type", ["", "summary", "flashcard", "mcq", "short_answer", "answer_key"])
    status_f = st.selectbox("Status", ["", "draft", "approved", "rejected"])
    params = {"document_id": did}
    if itype:
        params["item_type"] = itype
    if status_f:
        params["status"] = status_f
    try:
        items = requests.get(f"{API}/items", params=params).json()
    except Exception as e:
        items = []
        st.error(e)
    st.write(f"**{len(items)}** items")
    if not items:
        empty_state("No items found", "Adjust filters or generate content.")
    for it in items:
        with st.expander(f"Item {it['id']} — {it['item_type']} ({it['status']})"):
            render_item(it)
            st.caption(f"Bloom: {it.get('bloom_level')} | Quality: {it.get('quality_score')} | Model: {it.get('model')}")
            with st.expander("Edit payload"):
                txt = st.text_area("Payload JSON", value=_json.dumps(it["payload"], indent=2), key=f"edit_{it['id']}")
                if st.button("Save (new version)", key=f"save_{it['id']}"):
                    try:
                        new_payload = _json.loads(txt)
                        r = requests.patch(f"{API}/items/{it['id']}", json={"payload": new_payload})
                        if r.ok:
                            st.success(f"New version: {r.json()}")
                        else:
                            st.error(r.text)
                    except Exception as e:
                        st.error(str(e))
            if st.button("View versions", key=f"ver_{it['id']}"):
                r = requests.get(f"{API}/items/{it['id']}/versions")
                if r.ok:
                    for v in r.json():
                        st.write(f"v{v['version']} (id {v['id']}, by {v['created_by']}, status {v['status']})")
                else:
                    st.error(r.text)

# ---------- Rating Study ----------
elif page == "🧪 Rating Study":
    st.header("Blind Rating Study")
    study_id = st.number_input("Study ID", min_value=1, value=1, key="study_id")
    rater_id = st.number_input("Rater ID", min_value=1, value=1, key="rater_id")
    if st.button("Load pairs"):
        r = requests.get(f"{API}/studies/{study_id}/pairs", params={"rater_id": rater_id})
        if r.ok:
            st.session_state["study_pairs"] = r.json()["pairs"]
            st.success(f"Loaded {len(r.json()['pairs'])} pairs")
        else:
            st.error(r.text)
    pairs = st.session_state.get("study_pairs", [])
    for pair in pairs:
        st.markdown(f"### Pair {pair['pair_id']}")
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Item A**")
            render_item(pair["A"])
        with colB:
            st.markdown("**Item B**")
            render_item(pair["B"])
        for label in ["A", "B"]:
            item_id = pair[label]["item_id"]
            with st.expander(f"Rate Item {label} (id {item_id})"):
                accuracy = st.slider("Accuracy", 1, 5, 3, key=f"acc_{pair['pair_id']}_{label}")
                clarity = st.slider("Clarity", 1, 5, 3, key=f"clar_{pair['pair_id']}_{label}")
                difficulty = st.slider("Difficulty", 1, 5, 3, key=f"diff_{pair['pair_id']}_{label}")
                distractor = st.slider("Distractor quality", 1, 5, 3, key=f"dist_{pair['pair_id']}_{label}")
                bloom = st.slider("Bloom alignment", 1, 5, 3, key=f"bloom_{pair['pair_id']}_{label}")
                overall = st.slider("Overall", 1, 5, 3, key=f"ov_{pair['pair_id']}_{label}")
                would_use = st.slider("Would use", 1, 5, 3, key=f"use_{pair['pair_id']}_{label}")
                comments = st.text_input("Comments", key=f"com_{pair['pair_id']}_{label}")
                if st.button("Submit", key=f"sub_{pair['pair_id']}_{label}"):
                    payload = {
                        "rater_id": rater_id, "pair_id": pair["pair_id"], "blinded_label": label,
                        "item_id": item_id, "accuracy": accuracy, "clarity": clarity,
                        "difficulty": difficulty, "distractor_quality": distractor,
                        "bloom_alignment": bloom, "overall": overall, "would_use": would_use,
                        "comments": comments,
                    }
                    r = requests.post(f"{API}/studies/{study_id}/ratings", json=payload)
                    (st.success("Submitted") if r.ok else st.error(r.text))

# ---------- Study Mode ----------
elif page == "📖 Study Mode":
    st.header("Student Study Mode")
    sdoc = st.number_input("Document ID", min_value=1, value=1, key="sdoc")
    if st.button("Load flashcards"):
        r = requests.get(f"{API}/items", params={"document_id": sdoc, "item_type": "flashcard"})
        st.session_state["study_cards"] = r.json() if r.ok else []
        st.session_state["card_idx"] = 0
        st.session_state["show_back"] = False
    cards = st.session_state.get("study_cards", [])
    if cards:
        idx = st.session_state.get("card_idx", 0) % len(cards)
        card = cards[idx]
        p = card["payload"]
        st.markdown(f"### Card {idx+1} of {len(cards)}")
        st.markdown(f"**Front:** {p.get('front','')}")
        if st.session_state.get("show_back"):
            st.markdown(f"**Back:** {p.get('back','')}")
        c1, c2, c3 = st.columns(3)
        if c1.button("Show/Hide"):
            st.session_state["show_back"] = not st.session_state.get("show_back", False)
        if c2.button("Next"):
            st.session_state["card_idx"] = (idx + 1) % len(cards)
            st.session_state["show_back"] = False
        if c3.button("Prev"):
            st.session_state["card_idx"] = (idx - 1) % len(cards)
            st.session_state["show_back"] = False
    else:
        empty_state("No flashcards", "Load a document with flashcards.")
    st.divider()
    st.subheader("Practice Quiz (MCQs)")
    if st.button("Load quiz"):
        r = requests.get(f"{API}/items", params={"document_id": sdoc, "item_type": "mcq"})
        st.session_state["quiz_items"] = r.json() if r.ok else []
        st.session_state["quiz_idx"] = 0
        st.session_state["quiz_score"] = 0
    qitems = st.session_state.get("quiz_items", [])
    if qitems:
        qi = st.session_state.get("quiz_idx", 0)
        if qi < len(qitems):
            q = qitems[qi]
            p = q["payload"]
            st.markdown(f"**Q{qi+1}.** {p.get('stem','')}")
            choice = st.radio("Choose", [o.get("text","") for o in p.get("options",[])], key=f"q_{q['id']}")
            if st.button("Submit", key=f"subq_{q['id']}"):
                correct = next((o.get("text") for o in p.get("options",[]) if o.get("is_correct")), None)
                if choice == correct:
                    st.success("Correct!")
                    st.session_state["quiz_score"] = st.session_state.get("quiz_score", 0) + 1
                else:
                    st.error(f"Incorrect. Correct: {correct}")
                st.session_state["quiz_idx"] = qi + 1
        else:
            st.success(f"Quiz complete! Score: {st.session_state.get('quiz_score',0)}/{len(qitems)}")
    else:
        empty_state("No MCQs", "Load a document with MCQs.")

# ---------- Settings ----------
elif page == "⚙️ Settings":
    st.header("Settings")
    st.write("API URL:", API)
    try:
        r = requests.get(f"{API}/stats/costs")
        if r.ok:
            d = r.json()
            c1, c2, c3 = st.columns(3)
            c1.metric("Documents", d.get("documents", 0))
            c2.metric("Jobs", d.get("jobs", 0))
            c3.metric("Tokens used (est.)", d.get("total_tokens_used_estimate", 0))
            st.subheader("Items by type")
            for k, v in d.get("items_by_type", {}).items():
                st.write(f"- {k}: {v}")
            st.subheader("Models")
            st.write(f"Generation model: {d.get('models', {}).get('generation')}")
            st.write(f"Quality model: {d.get('models', {}).get('cheap')}")
    except Exception as e:
        st.error(e)