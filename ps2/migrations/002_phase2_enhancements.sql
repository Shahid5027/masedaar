-- =============================================================================
-- EDUCORE AI - PS2: Phase 2 Database Enhancements
-- Document Processing, Concepts Taxonomy, and Extracted Text Corrections
-- =============================================================================

-- Add required and optional concepts breakdown to questions table
ALTER TABLE public.questions 
ADD COLUMN IF NOT EXISTS required_concepts JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS optional_concepts JSONB DEFAULT '[]'::jsonb;

-- Add document metadata, extraction details, and faculty correction fields to submissions
ALTER TABLE public.submissions
ADD COLUMN IF NOT EXISTS file_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS file_size INTEGER,
ADD COLUMN IF NOT EXISTS file_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(50) DEFAULT 'success' 
    CHECK (extraction_status IN ('success', 'warning', 'empty', 'error', 'unreadable')),
ADD COLUMN IF NOT EXISTS extraction_warnings JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS original_extracted_text TEXT,
ADD COLUMN IF NOT EXISTS corrected_extracted_text TEXT,
ADD COLUMN IF NOT EXISTS is_text_corrected BOOLEAN DEFAULT FALSE;

-- Create submission text edit audit history table
CREATE TABLE IF NOT EXISTS public.submission_edit_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    previous_text TEXT NOT NULL,
    updated_text TEXT NOT NULL,
    editor_id VARCHAR(100) NOT NULL, -- Faculty identifier
    edit_reason TEXT,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edit_history_submission 
ON public.submission_edit_history(submission_id);

