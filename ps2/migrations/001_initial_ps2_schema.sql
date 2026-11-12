-- =============================================================================
-- EDUCORE AI - PS2: Automated Formative Assessment & Subjective Grading Assistant
-- Supabase PostgreSQL Database Migration 001
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. ASSESSMENTS TABLE
-- Represents a subjective/formative assessment created by faculty
CREATE TABLE IF NOT EXISTS public.assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    course_code VARCHAR(50) NOT NULL,
    course_name VARCHAR(255),
    faculty_id VARCHAR(100) NOT NULL, -- references instructor/faculty identifier
    description TEXT,
    max_score NUMERIC(5, 2) NOT NULL DEFAULT 100.00,
    passing_score NUMERIC(5, 2) DEFAULT 40.00,
    duration_minutes INTEGER DEFAULT 60,
    status VARCHAR(50) NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. QUESTIONS TABLE
-- Questions under each assessment with reference answers and concept tags
CREATE TABLE IF NOT EXISTS public.questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES public.assessments(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    max_marks NUMERIC(5, 2) NOT NULL,
    model_answer TEXT NOT NULL,
    key_concepts JSONB DEFAULT '[]'::jsonb, -- e.g. ["time complexity", "memoization"]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_assessment_question_num UNIQUE (assessment_id, question_number)
);

-- 3. RUBRIC CRITERIA TABLE
-- Fine-grained rubric scoring breakdown for subjective grading
CREATE TABLE IF NOT EXISTS public.rubric_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    criterion_name VARCHAR(150) NOT NULL, -- e.g. "Conceptual Accuracy", "Technical Depth"
    description TEXT,
    max_points NUMERIC(5, 2) NOT NULL,
    weight NUMERIC(3, 2) NOT NULL DEFAULT 1.00, -- relative weight
    levels JSONB DEFAULT '[]'::jsonb, 
    -- levels schema: [{"name": "Exemplary", "points": 10, "descriptor": "..."}, {"name": "Proficient", "points": 7, "descriptor": "..."}]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. SUBMISSIONS TABLE
-- Student submissions. Uses shared student_id without separate auth.
CREATE TABLE IF NOT EXISTS public.submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES public.assessments(id) ON DELETE CASCADE,
    student_id VARCHAR(100) NOT NULL, -- shared EDUCORE student_id cross-system
    student_name VARCHAR(255),
    file_url TEXT, -- Link to Supabase Storage PDF/document
    extracted_text TEXT, -- Parsed / OCR extracted text
    status VARCHAR(50) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'processing', 'evaluated', 'flagged_for_review')),
    total_score NUMERIC(5, 2),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. SUBMISSION ANSWERS TABLE
-- Parsed answers per question for multi-question assessments
CREATE TABLE IF NOT EXISTS public.submission_answers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    student_answer_text TEXT NOT NULL,
    ocr_confidence NUMERIC(4, 3) DEFAULT 1.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_question UNIQUE (submission_id, question_id)
);

-- 6. EVALUATIONS TABLE
-- Automated AI grading results, confidence metrics, and semantic similarity breakdown
CREATE TABLE IF NOT EXISTS public.evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    ai_score NUMERIC(5, 2) NOT NULL,
    max_score NUMERIC(5, 2) NOT NULL,
    confidence_score NUMERIC(4, 3) NOT NULL DEFAULT 0.85, -- 0.000 to 1.000
    semantic_similarity NUMERIC(4, 3) NOT NULL DEFAULT 0.80, -- Cosine similarity score
    rubric_scores JSONB DEFAULT '[]'::jsonb, -- Breakdown per rubric criterion
    feedback TEXT NOT NULL,
    strengths JSONB DEFAULT '[]'::jsonb,
    areas_for_improvement JSONB DEFAULT '[]'::jsonb,
    is_moderated BOOLEAN NOT NULL DEFAULT FALSE,
    final_score NUMERIC(5, 2), -- Reflects override if moderated, else ai_score
    evaluation_metadata JSONB DEFAULT '{}'::jsonb, -- model used, latency, token count
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_eval_submission_question UNIQUE (submission_id, question_id)
);

-- 7. MODERATION RECORDS TABLE
-- Faculty review, human-in-the-loop overrides, and calibration logs
CREATE TABLE IF NOT EXISTS public.moderation_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id UUID NOT NULL REFERENCES public.evaluations(id) ON DELETE CASCADE,
    moderator_id VARCHAR(100) NOT NULL, -- Faculty identifier
    moderator_name VARCHAR(255),
    original_score NUMERIC(5, 2) NOT NULL,
    adjusted_score NUMERIC(5, 2) NOT NULL,
    score_delta NUMERIC(5, 2) GENERATED ALWAYS AS (adjusted_score - original_score) STORED,
    moderation_reason TEXT NOT NULL,
    faculty_feedback TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'approved' CHECK (status IN ('pending', 'approved', 'overridden')),
    moderated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- INDEXES FOR HIGH-PERFORMANCE QUERYING
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_assessments_faculty ON public.assessments(faculty_id);
CREATE INDEX IF NOT EXISTS idx_questions_assessment ON public.questions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_rubric_question ON public.rubric_criteria(question_id);
CREATE INDEX IF NOT EXISTS idx_submissions_assessment ON public.submissions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student ON public.submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_submission ON public.evaluations(submission_id);
CREATE INDEX IF NOT EXISTS idx_moderation_evaluation ON public.moderation_records(evaluation_id);

-- =============================================================================
-- AUTOMATIC TIMESTAMP TRIGGER
-- =============================================================================
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_assessments_updated_at
BEFORE UPDATE ON public.assessments
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE OR REPLACE TRIGGER trg_submissions_updated_at
BEFORE UPDATE ON public.submissions
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

