# EDUCORE AI – PS2: Automated Formative Assessment & Intelligent Subjective Grading Assistant

> **Member 3 (PS2) Foundation** | Hackathon Architecture & Implementation

## 1. Problem Statement
**"Automated Formative Assessment and Intelligent Subjective Grading Assistant for Higher Education."**

Higher education institutions face significant bottlenecks in providing rapid, granular, and pedagogically meaningful formative feedback on open-ended subjective assessments. PS2 delivers an automated subjective evaluation engine combining:
1. **Semantic Text Matching**: Sentence Transformers embeddings (`all-MiniLM-L6-v2`) and exact vector cosine similarity against model solutions.
2. **Transparent Rubric Heuristic**:
   $$\text{Criterion Score} = \text{Criterion Maximum Marks} \times \text{Evidence Coverage} \times \text{Correctness Factor}$$
3. **Explainable Findings**: Extracts supporting student answer excerpts, identifies verified missing concepts, and checks for contradictory assertions.
4. **Formative Feedback Generation**: Automated extraction of demonstrated strengths, specific conceptual gaps, mastery suggestions, and recommended revision topics.
5. **Human-in-the-Loop Moderation**: Faculty override, score calibration, and confidence threshold routing without overwriting AI suggested marks.
6. **Shared Student Identity**: Seamless integration with the shared EDUCORE `student_id` namespace without redundant authentication.

---

## 2. Technology Stack

- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide Icons
- **Backend**: Python 3.14+, FastAPI, Uvicorn, Pydantic v2
- **Document Processing**: PyMuPDF (`pymupdf`/`fitz`) digital PDF extraction, native TXT extraction with paragraph preservation, empty & unreadable document detection, OCR service interface (PaddleOCR & Tesseract).
- **Database**: Supabase PostgreSQL (UUID primary keys, full relational schema, RLS, triggers, concepts taxonomy, and text edit audit history).
- **File Storage**: Supabase Storage (`ps2-submissions` bucket)
- **AI / NLP**: Modular Sentence Transformers scaffolding (`all-MiniLM-L6-v2`), N-gram token cosine vector similarity fallback, and automated formative feedback generators.

---

## 3. Directory Structure

```text
ps2/
├── backend/
│   ├── main.py                  # FastAPI application entrypoint & CORS
│   ├── config.py                # Environment and app configuration
│   ├── requirements.txt         # Python dependencies
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic data models & request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── assessments.py       # Assessment authoring & query endpoints
│   │   ├── submissions.py       # Student answer submissions & document upload
│   │   ├── evaluations.py       # AI grading trigger & evaluation results
│   │   └── moderation.py        # Faculty moderation queue & score override
│   └── services/
│       ├── __init__.py
│       ├── pdf_extractor.py     # PDF parsing via pypdf with fallback
│       ├── ocr_service.py       # OCR engine interface for scanned scripts
│       ├── text_preprocessor.py # Concept coverage & token normalization
│       ├── semantic_matcher.py  # Cosine & semantic similarity engine
│       ├── rubric_grader.py     # Multi-level rubric scoring engine
│       └── feedback_generator.py# Formative feedback and strengths synthesizer
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Global layout with persistent Sidebar & Top Navbar
│   │   ├── globals.css          # Tailwind CSS base styles
│   │   ├── page.tsx             # 1. Assessment Dashboard
│   │   ├── create-assessment/   # 2. Create Assessment & Rubric Builder
│   │   ├── submissions/         # 3. Student Submissions & Grading Trigger
│   │   ├── evaluations/         # 4. Evaluation Results & Semantic Breakdown
│   │   ├── moderation/          # 5. Faculty Moderation Queue & Overrides
│   │   └── student-result/      # 6. Student Result & Formative Feedback Card
│   ├── components/
│   │   ├── Sidebar.tsx          # Navigation sidebar
│   │   ├── Navbar.tsx           # Top status bar with live FastAPI health ping
│   │   └── StatusBadge.tsx      # Consistent status badges
│   ├── lib/
│   │   ├── api.ts               # Backend API integration client
│   │   └── utils.ts             # Tailwind class merging & date formatting
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── next.config.js
├── migrations/
│   └── 001_initial_ps2_schema.sql # Complete Supabase PostgreSQL DDL
├── sample_data/
│   ├── sample_assessment.json   # Full assessment with subjective rubrics & questions
│   ├── sample_submissions.json  # Student submissions with shared student_ids
│   └── sample_student_answer.txt# Raw text representation of student answer script
├── tests/
│   └── test_backend.py          # Pytest suite verifying health, API routes & services
├── .env.example                 # Environment configuration template
└── README.md
```

---

## 4. Setup & Running Instructions

### Backend (FastAPI)

1. **Navigate to the backend directory and activate the virtual environment**:
   ```powershell
   cd ps2
   # Windows PowerShell
   .\backend\venv\Scripts\Activate.ps1
   # (Or create new: python -m venv backend/venv && .\backend\venv\Scripts\Activate.ps1)
   ```

2. **Install requirements**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```

4. **Run the FastAPI server**:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Verify the Health-Check Endpoint**:
   - `GET http://localhost:8000/api/ps2/health`
   - Interactive Swagger Docs: `http://localhost:8000/api/ps2/docs`

---

### Frontend (Next.js)

1. **Navigate to the frontend directory**:
   ```bash
   cd ps2/frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run the development server**:
   ```bash
   npm run dev
   ```

4. **Access the application**:
   - Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### Running Automated Backend Tests

```powershell
cd ps2
.\backend\venv\Scripts\python.exe -m pytest tests -v
```

---

## 5. Database Schema & Supabase Setup

All database migrations are located in `migrations/001_initial_ps2_schema.sql`.

### Tables Designed:
1. `assessments`: Core assessment definition, course code, duration, passing score.
2. `questions`: Subjective questions, max marks, model answers, key theoretical concepts.
3. `rubric_criteria`: Criteria levels (e.g., Exemplary, Proficient, Developing) and weights.
4. `submissions`: Student submissions utilizing the cross-platform `student_id`.
5. `submission_answers`: Extracted answer text per question.
6. `evaluations`: AI score, semantic similarity, confidence metric, rubric breakdown, formative feedback.
7. `moderation_records`: Faculty calibration audit trail, delta calculation, and rationale.

### To Apply to Supabase:
1. Open your Supabase Dashboard -> **SQL Editor**.
2. Paste the contents of `migrations/001_initial_ps2_schema.sql` and click **Run**.

---

## 6. Shared Student ID Standard
PS2 does not implement a disparate student authentication silo. All student interactions, submission tracking, and grade publication rely on the shared `student_id` string (e.g. `EDU_STU_2026_014`), ensuring effortless interoperability with PS1 (Adaptive Learning) and PS3 (Dropout Prediction).

---

## 7. Phase 1 Verification Checklist
- [x] Backend folder structure matching specifications
- [x] FastAPI application configured with CORS, error handlers, and `/api/ps2` prefix
- [x] `GET /api/ps2/health` returning live JSON confirmation
- [x] 6 modular backend routes registered and functional
- [x] 6 core backend services implemented with resilient fallbacks
- [x] Next.js frontend running with responsive Sidebar, Top Navbar, and live health pill
- [x] 6 functional EdTech page structures implemented with zero dead buttons
- [x] Supabase SQL migration script with UUID primary keys & indexes
- [x] Pytest suite covering health, endpoints, and NLP grading logic (100% passing)
- [x] Clean environment variables (`.env.example`) and complete documentation

