from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width = Inches(13.33)
prs.slide_height = Inches(7.5)

def add_title_slide(title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle

def add_bullet_slide(title, bullets, level=0):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    tf = slide.placeholders[1].text_frame
    tf.text = bullets[0]
    for b in bullets[1:]:
        p = tf.add_paragraph()
        p.text = b
        p.level = level

# Title
add_title_slide("AI-Assisted Learning Content & Assessment Generation Platform",
                "Generate summaries, flashcards, MCQs, short-answer questions, and answer keys from course materials")

# Problem
add_bullet_slide("Problem", [
    "Manual creation of learning content and assessments is time-consuming",
    "Inconsistent quality and coverage across instructors",
    "Need factual grounding and alignment to learning objectives",
    "Difficulty scaling to large textbooks/syllabi",
])

# Solution
add_bullet_slide("Solution", [
    "AI pipeline that ingests textbooks/notes/syllabus units",
    "Generates multiple content types with structured output",
    "Quality control: grounding, dedup, ambiguity, Bloom mapping, filtering",
    "Human-in-the-loop review and export",
    "Blind evaluation study vs human-written items",
])

# Architecture
add_bullet_slide("Architecture", [
    "Frontend: Streamlit dashboard (teacher + rater UI)",
    "Backend: FastAPI with async job orchestration",
    "Ingestion: parse, clean, chunk, embed",
    "Generation: LLM with versioned prompt templates",
    "Quality Control: multi-stage verification pipeline",
    "Storage: SQLite/PostgreSQL + vector embeddings",
])

# Content Types
add_bullet_slide("Generated Content Types", [
    "Summaries (with key points)",
    "Flashcards (front/back/tags)",
    "MCQs (stem, 4 options, answer, explanation, distractor rationale)",
    "Short-answer questions (question, model answer, rubric, max points)",
    "Answer keys for all item types",
])

# Quality Control
add_bullet_slide("Quality Control Pipeline", [
    "Factual grounding (claim extraction + NLI/LLM entailment)",
    "Duplicate removal (semantic similarity)",
    "Ambiguity detection (LLM-as-judge)",
    "Bloom's Taxonomy mapping (6 levels + confidence)",
    "Heuristic filters (length, structure, leakage, triviality)",
    "LLM quality scoring (clarity, relevance, difficulty)",
    "Answer-key consistency check",
    "Regeneration loop with drop-on-failure",
])

# Bloom
add_bullet_slide("Bloom's Taxonomy Mapping", [
    "Remember, Understand, Apply, Analyze, Evaluate, Create",
    "Classifier with confidence score",
    "Target distribution enforcement per assessment",
    "Low-confidence items flagged for human review",
])

# Evaluation
add_bullet_slide("Blind Rating Study", [
    "Pair AI-generated items with human-written items",
    "Blinded labels (A/B) randomized per rater",
    "Criteria: accuracy, clarity, difficulty, distractor quality, Bloom alignment, overall",
    "Inter-rater reliability (ICC, Krippendorff's alpha)",
    "Statistical analysis and parity report",
])

# Tech Stack
add_bullet_slide("Tech Stack", [
    "Backend: Python, FastAPI, SQLAlchemy, SQLite/PostgreSQL",
    "Frontend: Streamlit",
    "LLM: OpenAI-compatible (with mock mode)",
    "Parsing: pypdf, python-docx",
    "Jobs: background tasks with progress/cancellation",
    "Auth: JWT-like tokens with RBAC",
])

# Roadmap
add_bullet_slide("Implementation Phases", [
    "Phase 0: Foundations (ingestion, LLM, auth, prompts)",
    "Phase 1: Core generation (summary, flashcard, MCQ, short answer, answer key)",
    "Phase 2: Quality control (grounding, dedup, ambiguity, Bloom, filters, scoring)",
    "Phase 3: Review UI, export (JSON/CSV/QTI/Anki)",
    "Phase 4: Evaluation study (design, ratings, analysis, report)",
    "Phase 5: Hardening, pilot, documentation",
])

# Demo
add_bullet_slide("Demo Flow", [
    "Upload a textbook chapter (PDF/TXT)",
    "Generate MCQs and flashcards",
    "Run QC pipeline (grounding, dedup, ambiguity, Bloom)",
    "Review and approve items",
    "Export to QTI for LMS import",
])

# Conclusion
add_bullet_slide("Conclusion", [
    "End-to-end AI assessment generation with strong quality control",
    "Human-in-the-loop review preserves educator oversight",
    "Evaluation study validates AI vs human parity",
    "Extensible: OCR, multilingual, adaptive difficulty (v1.1+)",
])

prs.save("presentation.pptx")
print("Saved presentation.pptx")