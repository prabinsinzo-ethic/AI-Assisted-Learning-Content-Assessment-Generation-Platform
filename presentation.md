# AI-Assisted Learning Content & Assessment Generation Platform

## Problem
- Manual creation of learning content and assessments is time-consuming
- Inconsistent quality and coverage across instructors
- Need factual grounding and alignment to learning objectives
- Difficulty scaling to large textbooks/syllabi

## Solution
- AI pipeline ingests textbooks, notes, syllabus units
- Generates summaries, flashcards, MCQs, short-answer questions, answer keys
- Quality control: grounding, dedup, ambiguity, Bloom mapping, filtering
- Human-in-the-loop review and export
- Blind evaluation study vs human-written items

## Architecture
- Frontend: Streamlit dashboard (teacher + rater UI)
- Backend: FastAPI with async job orchestration
- Ingestion: parse, clean, chunk, embed
- Generation: LLM with versioned prompt templates
- Quality Control: multi-stage verification pipeline
- Storage: SQLite/PostgreSQL + vector embeddings

## Generated Content Types
- Summaries (with key points)
- Flashcards (front/back/tags)
- MCQs (stem, 4 options, answer, explanation, distractor rationale)
- Short-answer questions (question, model answer, rubric, max points)
- Answer keys for all item types

## Quality Control Pipeline
- Factual grounding (claim extraction + NLI/LLM entailment)
- Duplicate removal (semantic similarity)
- Ambiguity detection (LLM-as-judge)
- Bloom's Taxonomy mapping (6 levels + confidence)
- Heuristic filters (length, structure, leakage, triviality)
- LLM quality scoring (clarity, relevance, difficulty)
- Answer-key consistency check
- Regeneration loop with drop-on-failure

## Bloom's Taxonomy Mapping
- Remember, Understand, Apply, Analyze, Evaluate, Create
- Classifier with confidence score
- Target distribution enforcement per assessment
- Low-confidence items flagged for human review

## Blind Rating Study
- Pair AI-generated items with human-written items
- Blinded labels (A/B) randomized per rater
- Criteria: accuracy, clarity, difficulty, distractor quality, Bloom alignment, overall
- Inter-rater reliability (ICC, Krippendorff's alpha)
- Statistical analysis and parity report

## Tech Stack
- Backend: Python, FastAPI, SQLAlchemy, SQLite/PostgreSQL
- Frontend: Streamlit
- LLM: OpenAI-compatible (with mock mode)
- Parsing: pypdf, python-docx
- Jobs: background tasks with progress/cancellation
- Auth: JWT-like tokens with RBAC

## Implementation Phases
- Phase 0: Foundations
- Phase 1: Core generation
- Phase 2: Quality control
- Phase 3: Review UI, export
- Phase 4: Evaluation study
- Phase 5: Hardening, pilot, documentation

## Demo Flow
- Upload a textbook chapter (PDF/TXT)
- Generate MCQs and flashcards
- Run QC pipeline
- Review and approve items
- Export to QTI for LMS import

## Conclusion
- End-to-end AI assessment generation with strong quality control
- Human-in-the-loop review preserves educator oversight
- Evaluation study validates AI vs human parity
- Extensible: OCR, multilingual, adaptive difficulty (v1.1+)