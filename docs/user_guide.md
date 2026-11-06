# User Guide

## Getting Started
1. Start the backend: `run.bat` (Windows) or `./run.sh` (macOS/Linux).
2. Open the dashboard: `run.bat dashboard` / `./run.sh dashboard` (Streamlit on port 8501).
3. Or use the API directly at http://127.0.0.1:8001/docs.

## Uploading Content
- Go to Documents tab, enter a title, upload a PDF/DOCX/TXT file.
- The system parses and chunks the document with provenance (page/section).

## Generating Content
- Select a document, choose content types (summary, flashcard, MCQ, short answer, answer key).
- Click Generate. Jobs run in the background; progress is shown.

## Reviewing Items
- Use the Review Queue tab to approve, reject, or edit items.
- Editing creates a new version with lineage tracking.

## Quality Control
- Run individual QC checks or the full pipeline from the QC tab.
- Items that fail QC are marked rejected.

## Export
- Export items via `/export/{document_id}?format=json|csv|anki|qti`.

## Blind Rating Study
- Create a study via `/studies` with AI/human item pairs.
- Raters use the Rating Study tab to rate blinded items.
- View results and reports via `/studies/{id}/results` and `/studies/{id}/report`.