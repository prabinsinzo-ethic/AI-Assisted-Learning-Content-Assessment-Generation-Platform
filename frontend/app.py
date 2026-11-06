import os
import requests
import streamlit as st

API = os.getenv("API_URL", "http://127.0.0.1:8001")

st.set_page_config(page_title="AI Learning Content Platform", layout="wide")
st.title("AI Learning Content & Assessment Platform")

# Sidebar: API health
with st.sidebar:
    st.header("Connection")
    try:
        r = requests.get(f"{API}/health", timeout=3)
        st.success(f"API OK: {r.json()}")
    except Exception as e:
        st.error(f"API unreachable: {e}")
    api_url = st.text_input("API URL", value=API)
    if api_url != API:
        os.environ["API_URL"] = api_url
        API = api_url

tab_docs, tab_items, tab_qc = st.tabs(["Documents", "Items", "Quality Control"])

# --- Documents tab ---
with tab_docs:
    st.subheader("Upload Document")
    title = st.text_input("Title")
    uploaded = st.file_uploader("File", type=["txt", "pdf", "docx"])
    if st.button("Upload") and uploaded and title:
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")}
        r = requests.post(f"{API}/documents", data={"title": title}, files=files)
        if r.ok:
            st.success(f"Uploaded: {r.json()}")
        else:
            st.error(r.text)

    st.subheader("Documents")
    try:
        docs = requests.get(f"{API}/documents").json()
    except Exception as e:
        docs = []
        st.error(e)
    doc_map = {f"{d['id']}: {d['title']}": d["id"] for d in docs}
    selected_doc_label = st.selectbox("Select document", list(doc_map.keys())) if doc_map else None
    selected_doc = doc_map[selected_doc_label] if selected_doc_label else None

    if selected_doc:
        st.write(f"Document ID: {selected_doc}")
        # chunks
        try:
            chunks = requests.get(f"{API}/documents/{selected_doc}/chunks").json()
            st.write(f"Chunks: {len(chunks)}")
        except Exception:
            chunks = []
        # generation
        st.subheader("Generate")
        types = st.multiselect("Types", ["summary", "flashcard", "mcq", "short_answer", "answer_key"],
                               default=["summary"])
        items_per = st.number_input("Items per chunk", min_value=1, max_value=5, value=1)
        if st.button("Generate"):
            r = requests.post(f"{API}/jobs/generate", json={
                "document_id": selected_doc, "types": types, "items_per_chunk": items_per
            })
            if r.ok:
                job_id = r.json()["job_id"]
                st.info(f"Job {job_id} started")
                # poll
                import time
                progress = st.progress(0.0)
                for _ in range(60):
                    time.sleep(1)
                    s = requests.get(f"{API}/jobs/{job_id}").json()
                    progress.progress(s.get("progress", 0.0))
                    if s["status"] in ("done", "failed", "cancelled"):
                        break
                st.success(f"Job {s['status']}: {s.get('result_ids')}")
            else:
                st.error(r.text)

# --- Items tab ---
with tab_items:
    st.subheader("Items")
    did = st.number_input("Document ID", min_value=1, value=1)
    itype = st.selectbox("Type", ["", "summary", "flashcard", "mcq", "short_answer", "answer_key"])
    params = {"document_id": did}
    if itype:
        params["item_type"] = itype
    try:
        items = requests.get(f"{API}/items", params=params).json()
    except Exception as e:
        items = []
        st.error(e)
    st.write(f"Total: {len(items)}")
    for it in items:
        with st.expander(f"Item {it['id']} - {it['item_type']} ({it['status']})"):
            st.json(it["payload"])
            st.write(f"Bloom: {it.get('bloom_level')} | Quality: {it.get('quality_score')} | Model: {it.get('model')}")
            new_status = st.selectbox("Status", ["draft", "approved", "rejected"], index=["draft", "approved", "rejected"].index(it["status"]), key=f"st_{it['id']}")
            if st.button("Update status", key=f"btn_{it['id']}"):
                r = requests.patch(f"{API}/items/{it['id']}", json={"status": new_status})
                if r.ok:
                    st.success("Updated")
                else:
                    st.error(r.text)

# --- QC tab ---
with tab_qc:
    st.subheader("Run Quality Control")
    qdoc = st.number_input("Document ID (QC)", min_value=1, value=1, key="qdoc")
    col1, col2, col3 = st.columns(3)
    if col1.button("Verify (grounding)"):
        r = requests.post(f"{API}/qc/verify", json={"document_id": qdoc})
        st.json(r.json())
    if col2.button("Dedup"):
        r = requests.post(f"{API}/qc/dedup", json={"document_id": qdoc})
        st.json(r.json())
    if col3.button("Ambiguity"):
        r = requests.post(f"{API}/qc/ambiguity", json={"document_id": qdoc})
        st.json(r.json())
    col4, col5, col6 = st.columns(3)
    if col4.button("Bloom"):
        r = requests.post(f"{API}/qc/bloom", json={"document_id": qdoc})
        st.json(r.json())
    if col5.button("Heuristics"):
        r = requests.post(f"{API}/qc/heuristics", json={"document_id": qdoc})
        st.json(r.json())
    if col6.button("Quality Score"):
        r = requests.post(f"{API}/qc/quality-score", json={"document_id": qdoc})
        st.json(r.json())
    if st.button("Consistency"):
        r = requests.post(f"{API}/qc/consistency", json={"document_id": qdoc})
        st.json(r.json())
    if st.button("Run Full QC Pipeline"):
        r = requests.post(f"{API}/qc/run", json={"document_id": qdoc, "max_retries": 1})
        st.json(r.json())