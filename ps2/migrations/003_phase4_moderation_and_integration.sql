-- =============================================================================
-- EDUCORE AI – PS2 Migration 003: Phase 4 Faculty Moderation & System Integration
-- =============================================================================
-- Enhances evaluation records with explicit status progression, review metadata,
-- and audit trail support for faculty moderation and PS1/PS3 platform integration.

-- 1. ENHANCE EVALUATIONS TABLE FOR WORKFLOW PROGRESSION
ALTER TABLE public.evaluations
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'ai_suggested' 
        CHECK (status IN ('ai_suggested', 'faculty_reviewed', 'finalized')),
    ADD COLUMN IF NOT EXISTS suggested_marks NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS final_marks NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS moderation_reason TEXT;

-- Initialize suggested_marks with ai_score where not set
UPDATE public.evaluations 
SET suggested_marks = ai_score 
WHERE suggested_marks IS NULL;

-- 2. ENHANCE MODERATION RECORDS TABLE
ALTER TABLE public.moderation_records
    ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS original_suggested_marks NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS final_marks NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill legacy records if any exist
UPDATE public.moderation_records
SET original_suggested_marks = original_score,
    final_marks = adjusted_score,
    reviewed_by = COALESCE(moderator_name, moderator_id),
    reviewed_at = moderated_at
WHERE original_suggested_marks IS NULL;

-- 3. INDEXES FOR CROSS-MODULE INTEGRATION (PS1 Weak Topics & PS3 Analytics)
CREATE INDEX IF NOT EXISTS idx_evaluations_status ON public.evaluations(status);
CREATE INDEX IF NOT EXISTS idx_evaluations_reviewed_at ON public.evaluations(reviewed_at);
