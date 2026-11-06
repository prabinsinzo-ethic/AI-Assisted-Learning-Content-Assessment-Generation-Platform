# AI-Assisted Learning Content & Assessment Generation Platform

## Project Plan (Planning Only — No Code Yet)

**Goal:** Build an AI system that, given textbooks, lecture notes, or syllabus units, generates
summaries, flashcards, MCQs, short-answer questions, and answer keys — with strong quality control
(factual grounding, deduplication, ambiguity filtering, Bloom's Taxonomy mapping, low-quality
filtering) and a blind human-vs-AI assessment evaluation study.

---

## 1. Problem Statement & Scope

- **Inputs:** Textbooks (PDF/DOCX/EPUB), lecture notes, syllabus units (plain text or structured).
- **Outputs:** (a) chapter/section summaries, (b) flashcards (Q/A or term/definition), (c) MCQs
  (stem + 4 options + correct answer + distractor rationale), (d) short-answer questions with
  model answer keys and rubrics, (e) answer keys for all item types.
- **Quality bar:** Every generated item must be factually grounded in the source, non-duplicate,
  unambiguous, mapped to a Bloom's level, and pass quality filters. Items that fail are
  regenerated or dropped, never silently shipped.
- **Evaluation:** Blind rating study comparing AI-generated assessments to human-written ones on
  accuracy, clarity, difficulty, distractor quality, and Bloom alignment.

### In Scope (v1)
- Single-language (English) content.
- Text-based inputs (scanned PDFs via OCR as a stretch goal).
- Teacher/admin authoring workflow with review & approval.
- Export to common formats (JSON, CSV, QTI for LMS import).

### Out of Scope (v1)
- Multilingual generation, auto-grading of student responses, adaptive difficulty, real-time
  classroom analytics.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Web App)                         │
│  Upload docs · Review/Edit items · Approve · Export · Analytics │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST/GraphQL
┌──────────────────────────────▼──────────────────────────────────┐
│                       API Gateway / Backend                     │
│  Auth · RBAC · Job orchestration · Rate limiting · Audit logs   │
└──────┬──────────────┬──────────────┬──────────────┬────────────┘
       │              │              │              │
┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼──────┐
│ Ingestion   │ │ Generation│ │ Quality   │ │ Evaluation │
│ Service     │ │ Service   │ │ Control   │ │ Service    │
│ (parse/chunk│ │ (LLM calls│ │ Service   │ │ (study mgmt│
│  + embed)   │ │  prompts) │ │ (verify)  │ │  + stats)  │
└──────┬──────┘ └─────┬─────┘ └─────┬─────┘ └─────┬──────┘
       │              │              │              │
┌──────▼──────────────▼──────────────▼──────────────▼──────┐
│  Vector Store (embeddings) · Relational DB · Object Store  │
│  (source chunks, items, versions, ratings, audit trail)     │
└────────────────────────────────────────────────────────────┘
```

### Core Services
1. **Ingestion Service** — parse documents, clean, chunk into semantically coherent units,
   embed, store with provenance (doc, page, section).
2. **Generation Service** — LLM-driven generators for each content type, with structured
   output (JSON schema), prompt templates, and retry/regeneration logic.
3. **Quality Control Service** — factual grounding verifier, duplicate detector, ambiguity
   detector, Bloom classifier, quality scorer/filter.
4. **Review Service** — human-in-the-loop approval workflow, versioning, edits.
5. **Evaluation Service** — blind study orchestration, rating collection, statistical analysis.
6. **Export Service** — JSON/CSV/QTI/Anki deck export.

---

## 3. Tech Stack (Recommended)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (React) + Tailwind + shadcn/ui | Teacher dashboard, item review UI |
| Backend | FastAPI (Python) or Node/NestJS | Python preferred for ML/NLP ecosystem |
| Task Queue | Celery + Redis (or BullMQ) | Long-running generation jobs |
| Relational DB | PostgreSQL | Items, users, versions, ratings |
| Vector DB | pgvector (or Qdrant) | Chunk embeddings + item embeddings |
| Object Storage | S3-compatible (MinIO for dev) | Source docs, exports |
| LLM | OpenAI / Anthropic / local (Ollama) | Abstract behind provider interface |
| Embeddings | OpenAI text-embedding-3-small or local | For retrieval + dedup |
| Parsing | pdfplumber, python-docx, unstructured | + OCR (Tesseract) optional |
| NLP | spaCy, sentence-transformers | Chunking, similarity |
| Observability | OpenTelemetry + structured logs | Trace LLM calls, costs |
| Auth | JWT + RBAC (teacher, reviewer, admin) | |
| Infra | Docker Compose (dev), Kubernetes (prod) | |

---

## 4. Data Model (Core Entities)

- **Document** (id, title, type, source_path, uploaded_by, created_at, status)
- **Chunk** (id, document_id, section, page_range, text, embedding, token_count, order_index)
- **ContentItem** (id, document_id, chunk_ids[], type [summary|flashcard|mcq|short_answer],
  payload JSON, bloom_level, quality_score, status [draft|approved|rejected], version,
  created_by [ai|human], parent_item_id)
- **GenerationJob** (id, document_id, requested_types, params, status, progress, error)
- **Rating** (id, study_id, rater_id, item_id, blinded_label, criteria scores, comments)
- **Study** (id, name, design, item_pairs, status)

### Payload Schemas (illustrative)
- **Summary:** `{section, text, key_points[], length_tokens}`
- **Flashcard:** `{front, back, tags[]}`
- **MCQ:** `{stem, options[4]{text, is_correct}, correct_index, explanation, distractor_rationale}`
- **ShortAnswer:** `{question, model_answer, rubric[{criterion, points}], max_points}`
- **AnswerKey:** `{item_id, answer, grading_notes}`

---

## 5. Pipelines

### 5.1 Ingestion Pipeline
1. Upload & validate (size, type, virus scan optional).
2. Parse to structured text with section headings, page numbers.
3. Clean (remove headers/footers, fix hyphenation, normalize whitespace).
4. Chunk: semantic chunking by section + token budget (e.g., 300–600 tokens, overlap 50).
   Fall back to sentence-aware splitting.
5. Embed each chunk; store with provenance.
6. Index for retrieval (vector + keyword/BM25 hybrid).

### 5.2 Generation Pipeline
For each requested content type and each chunk (or chapter aggregate):
1. Retrieve relevant context (the chunk + neighbors) — RAG grounding.
2. Build prompt from versioned template with few-shot examples.
3. Call LLM with JSON-schema constrained output (structured outputs / function calling).
4. Validate schema; on failure, retry with error feedback (max N).
5. Attach provenance (chunk_ids, source spans).
6. Hand off to Quality Control.

Prompt design principles:
- Explicit instruction to use ONLY provided context; no outside knowledge.
- Require citations (chunk IDs / quotes) for each factual claim.
- Specify Bloom target distribution (e.g., 30% Remember/Understand, 40% Apply/Analyze, 30% Evaluate/Create).
- Few-shot examples of good vs bad items.

### 5.3 Quality Control Pipeline (the core differentiator)

Run as a chain of filters; item must pass all to be "approved" (or flagged for review).

**A. Factual Grounding (RAG Verification)**
- Extract atomic claims from generated item (question + answer + options).
- For each claim, retrieve top-k source chunks and compute entailment score (NLI model or
  LLM-as-judge with rubric).
- Threshold: item passes only if all claims have entailment ≥ T (e.g., 0.8) against at least
  one source chunk. Failing items are regenerated with stricter grounding prompt or dropped.
- Store grounding score + supporting chunk references.

**B. Duplicate Removal**
- Embed each item (question text + answer).
- Compute pairwise cosine similarity within document and globally (optional).
- If similarity > threshold (e.g., 0.85) with an existing approved item, mark duplicate and
  drop (keep higher quality score).

**C. Ambiguity Detection**
- LLM-as-judge checks: Is the question stem unambiguous? Is there exactly one correct answer?
  Are options mutually exclusive and exhaustive? For MCQs, verify distractors are plausible
  but clearly wrong.
- Short-answer: check that rubric criteria are observable and non-overlapping.
- Score 1–5; drop below threshold.

**D. Bloom's Taxonomy Mapping**
- Classifier (fine-tuned or LLM prompt with definitions + examples) assigns one of six levels:
  Remember, Understand, Apply, Analyze, Evaluate, Create.
- Provide confidence score; low confidence → human review.
- Enforce target distribution per assessment (configurable).

**E. Low-Quality Filtering**
- Heuristics: length bounds, grammar/spell check, option count, no "all/none of the above"
  (configurable), no trivially true/false stems, no duplicate options, answer not in question.
- LLM-as-judge overall quality score (1–5) across clarity, relevance, difficulty appropriateness.
- Drop items below threshold; log reasons for audit.

**F. Consistency / Answer-Key Check**
- Regenerate answer independently and compare; mismatch → flag.
- For MCQ, verify correct option indeed correct and others indeed wrong via grounding.

### 5.4 Review Workflow
- Items land in "pending review" queue grouped by document/section.
- Teacher can approve, edit (creates new version, keeps lineage), reject with reason.
- Bulk actions; filters by type, Bloom level, quality score.
- Approved items become the "gold" set for export and study.

### 5.5 Evaluation (Blind Rating Study)
Design:
- Pair AI-generated items with human-written items on same source content, matched by type
  and Bloom level where possible.
- Blind labels (A/B) randomized per rater; raters (teachers/SMEs) score on rubric:
  - Factual accuracy (1–5)
  - Clarity of wording (1–5)
  - Appropriateness of difficulty (1–5)
  - Distractor quality (MCQ only, 1–5)
  - Bloom alignment (1–5: does item actually target stated level?)
  - Overall quality / would-use (1–5 + yes/no)
- Collect N raters per item (≥3) for inter-rater reliability (ICC / Krippendorff's alpha).
- Analysis: descriptive stats, paired t-tests / Wilcoxon, effect sizes, per-type breakdowns,
  failure-mode taxonomy (hallucination, ambiguity, triviality, etc.).
- Report: AI vs human parity threshold, cost/time comparison, recommendations.

---

## 6. API Surface (Sketch)

- `POST /documents` upload
- `GET /documents/{id}` status
- `POST /jobs/generate` {document_id, types[], bloom_distribution, count_per_section}
- `GET /jobs/{id}` progress
- `GET /items?document_id=&type=&status=&bloom=`
- `PATCH /items/{id}` edit/approve/reject
- `POST /items/{id}/regenerate`
- `GET /export/{document_id}?format=json|csv|qti`
- `POST /studies`, `POST /studies/{id}/ratings`, `GET /studies/{id}/results`

---

## 7. Non-Functional Requirements

- **Performance:** Generation of a 10-chapter textbook's full item set within ~minutes via
  parallel chunk processing; async jobs with progress.
- **Cost control:** Token budgets per document; caching of embeddings and LLM responses;
  model tiering (cheap model for filtering/judging where adequate).
- **Security:** Auth, RBAC, encrypted storage, no PII in logs, signed URLs for docs.
- **Auditability:** Every item traces to source chunks + generation params + QC decisions.
- **Reproducibility:** Versioned prompts, model IDs, params stored with each item.
- **Accessibility:** WCAG 2.1 AA for web UI.

---

## 8. Phased Roadmap

### Phase 0 — Setup & Foundations (Week 1–2)

**0.1 Repository & Tooling**
- Initialize monorepo (frontend/, backend/, infra/, docs/, prompts/).
- Set up linting, formatting, pre-commit hooks, conventional commits.
- Configure CI pipeline (build, test, lint) on PRs.

**0.2 Infrastructure & Environments**
- Docker Compose for local dev (Postgres + pgvector, Redis, MinIO, backend, frontend).
- Environment config management (.env templates, secrets handling).
- Staging environment skeleton.

**0.3 Database & Migrations**
- Design and create initial schema (Document, Chunk, ContentItem, GenerationJob, User).
- Migration tooling (Alembic/Prisma) with seed data.

**0.4 Authentication & RBAC**
- JWT-based auth, role definitions (teacher, reviewer, admin).
- Protected routes, permission middleware.

**0.5 Ingestion Foundations**
- Document upload endpoint + validation (size, type).
- Parsers: PDF (pdfplumber), DOCX, plain text, Markdown.
- Text cleaning (header/footer removal, hyphenation fix, whitespace normalization).
- Section/heading detection.

**0.6 Chunking & Embeddings**
- Semantic chunker (section-aware, token budget 300–600, overlap 50).
- Sentence-aware fallback splitter.
- Embedding service with provider abstraction.
- Vector + keyword (BM25) hybrid index setup.

**0.7 LLM Provider Abstraction**
- Unified client interface (chat, structured output, embeddings).
- Provider implementations (OpenAI, Anthropic, local/Ollama).
- Retry, timeout, rate-limit, cost tracking, response caching.

**0.8 Prompt Template Registry**
- Versioned prompt templates stored in repo (prompts/).
- Template rendering with variables + few-shot examples.
- Template loading/versioning at runtime.

---

### Phase 1 — Core Generation (Week 3–5)

**1.1 Summary Generator**
- Chapter/section summary generation with key points.
- Length control (short/medium/long).
- Provenance (chunk_ids, page ranges).

**1.2 Flashcard Generator**
- Term/definition and Q/A flashcard formats.
- Tagging (concept, topic).
- Dedup within generation batch.

**1.3 MCQ Generator**
- Stem + 4 options + correct answer + explanation.
- Distractor rationale generation.
- Enforce single correct answer; avoid "all/none of the above" (configurable).

**1.4 Short-Answer Generator**
- Question + model answer + rubric (criteria + points).
- Max points and grading notes.

**1.5 Answer Key Generator**
- Consolidated answer keys for all item types.
- Grading guidance and partial-credit notes.

**1.6 Structured Output & Validation**
- JSON Schema definitions per item type.
- Schema validation with auto-retry + error feedback (max N).
- Idempotent job handling.

**1.7 Provenance & Lineage**
- Attach source chunk IDs and spans to every item.
- Store generation params (model, prompt version, temperature).

**1.8 Job Orchestration**
- Async generation jobs with progress tracking.
- Parallel chunk processing with concurrency limits.
- Job status API + cancellation.

---

### Phase 2 — Quality Control (Week 6–8)

**2.1 Factual Grounding Verifier**
- Atomic claim extraction from item text.
- Claim-to-chunk retrieval (top-k).
- NLI/LLM entailment scoring per claim.
- Threshold-based pass/fail + grounding score storage.
- Regeneration with stricter grounding prompt on failure.

**2.2 Duplicate Detection**
- Item embedding (question + answer).
- Pairwise similarity within document and global corpus.
- Threshold-based duplicate flagging (keep higher quality).

**2.3 Ambiguity Detector**
- LLM-as-judge for stem clarity, single correct answer, option exclusivity/exhaustiveness.
- MCQ distractor plausibility check.
- Short-answer rubric observability check.
- Score 1–5 with drop threshold.

**2.4 Bloom's Taxonomy Classifier**
- Classifier prompt with definitions + examples for 6 levels.
- Confidence score; low confidence → human review queue.
- Target distribution enforcement per assessment.

**2.5 Heuristic Filters**
- Length bounds, grammar/spell check.
- Option count and uniqueness checks.
- Trivially-true/false stem detection.
- Answer-in-question leakage check.

**2.6 LLM Quality Scorer**
- Overall quality score (1–5): clarity, relevance, difficulty appropriateness.
- Per-criterion breakdown for audit.
- Drop below threshold; log reasons.

**2.7 Answer-Key Consistency Check**
- Independent regeneration of answer; compare.
- MCQ correct/incorrect option verification via grounding.

**2.8 Regeneration Loop & QC Orchestration**
- Chain all filters; retry generation up to N times.
- Drop item if still failing; record drop reason.
- QC decision audit trail.

---

### Phase 3 — Review UI & Export (Week 9–10)

**3.1 Teacher Dashboard**
- Document list, job status, item counts by type/Bloom.
- Filters and search across items.

**3.2 Review Queue**
- Pending items grouped by document/section.
- Approve / edit / reject with reason.
- Bulk actions.

**3.3 Editing & Versioning**
- Inline edit with version creation and lineage tracking.
- Diff view between versions.
- Re-run QC on edited items.

**3.4 Export Service**
- JSON, CSV export.
- QTI 2.1/3.0 for LMS import (Canvas/Moodle).
- Anki deck export (flashcards).
- Signed download URLs.

---

### Phase 4 — Evaluation Study (Week 11–13)

**4.1 Study Design & Protocol**
- Finalize rubric and rating criteria.
- Item pairing (AI vs human, matched by type/Bloom).
- Blinding procedure and randomization.

**4.2 Study Orchestration Backend**
- Study CRUD, item-pair management.
- Blinded label assignment (A/B) per rater.
- Rating submission API with validation.

**4.3 Rating UI**
- Rater-facing interface (separate from teacher UI).
- Criteria sliders + comments.
- Progress tracking for raters.

**4.4 Rater Recruitment & Onboarding**
- Recruit teachers/SMEs.
- Training session + pilot ratings for calibration.
- Inter-rater reliability check before full run.

**4.5 Data Collection & Monitoring**
- Collect ≥3 ratings per item.
- Monitor completion, dropouts, time-per-item.

**4.6 Statistical Analysis**
- Descriptive stats, paired tests (t-test/Wilcoxon), effect sizes.
- Per-type and per-Bloom breakdowns.
- Inter-rater reliability (ICC, Krippendorff's alpha).
- Failure-mode taxonomy coding.

**4.7 Report & Recommendations**
- AI vs human parity analysis.
- Cost/time comparison.
- Final report + recommendations for QC threshold tuning.

---

### Phase 5 — Hardening & Pilot (Week 14–16)

**5.1 Performance Optimization**
- Profiling, caching (embeddings, LLM responses).
- Concurrency tuning, batch processing.
- Latency targets for full textbook.

**5.2 Cost Optimization**
- Model tiering (cheap models for filtering/judging).
- Token budgets per document.
- Cost dashboards and alerts.

**5.3 Security Review**
- Auth/RBAC audit, input validation, file upload safety.
- Secrets management, encrypted storage.
- Penetration testing (basic).

**5.4 Accessibility & UX**
- WCAG 2.1 AA compliance.
- Keyboard navigation, screen-reader support.
- Usability polish based on feedback.

**5.5 Pilot Deployment**
- Deploy to pilot institution(s).
- Onboard real teachers; collect usage data.
- Iterate QC thresholds and prompts based on real data.

**5.6 Documentation & Handover**
- User guide, admin runbook, API docs (OpenAPI).
- Deployment and operations documentation.
- Final retrospective and roadmap for v1.1 (OCR, multilingual).

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Hallucinated facts | Strict RAG grounding + claim-level NLI verification + citations |
| Duplicate/low-value items | Semantic dedup + quality scorer + Bloom distribution control |
| Ambiguous MCQs | Dedicated ambiguity judge + human review gate |
| Cost overrun | Model tiering, caching, token budgets, batch processing |
| LLM vendor lock-in | Provider abstraction + local model fallback |
| Rater bias in study | Blinding, multiple raters, ICC reporting, balanced item pairing |
| OCR noise (scanned PDFs) | Mark as v1.1; require text PDFs in v1 |

---

## 10. Success Metrics

- **QC:** ≥95% of shipped items pass factual grounding (human spot-check); duplicate rate <5%;
  ambiguity-flag rate <10%.
- **Efficiency:** ≥10x faster than manual authoring for equivalent item counts.
- **Evaluation:** AI items achieve ≥80% of human item mean overall-quality score; no
  statistically significant deficit on factual accuracy; inter-rater reliability ICC ≥0.7.
- **Adoption:** ≥70% of generated items approved without edits in pilot.

---

## 11. Deliverables

1. `plan.md` (this document).
2. Architecture decision records (ADRs) for LLM provider, chunking strategy, QC thresholds.
3. Data model migrations + API spec (OpenAPI).
4. Prompt template library (versioned).
5. QC evaluation harness with labeled test set.
6. Blind study protocol + analysis notebook/report.
7. User guide + deployment runbook.

---

## 12. Open Questions for Stakeholders

1. Target LMS integration (Canvas/Moodle/Blackboard) → affects QTI version.
2. Preferred LLM provider / on-prem requirement (data privacy for student content).
3. Languages beyond English?
4. Who are raters in the blind study (in-house teachers vs external SMEs)?
5. Acceptable latency for a full textbook (minutes vs hours)?
6. Budget ceiling for LLM API costs per document?

---

*End of plan. No code has been written; this is a planning document only.*