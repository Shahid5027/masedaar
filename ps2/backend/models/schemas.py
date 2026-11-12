from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timezone
import uuid


# ---------------------------------------------------------------------------
# Generic API Envelope
# ---------------------------------------------------------------------------
class APIResponse(BaseModel):
    success: bool = True
    module: str = "ps2"
    student_id: Optional[str] = None
    message: str = "Operation successful"
    data: Optional[Any] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "EDUCORE AI - PS2 Subjective Grading Assistant"
    version: str = "2.0.0"
    environment: str = "development"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Rubric Criteria Schemas
# ---------------------------------------------------------------------------
class RubricLevel(BaseModel):
    name: str
    points: float
    descriptor: str


class RubricCriterionBase(BaseModel):
    criterion_name: str
    description: Optional[str] = None
    max_points: float
    weight: float = 1.0
    levels: List[RubricLevel] = []


class RubricCriterionCreate(RubricCriterionBase):
    pass


class RubricCriterion(RubricCriterionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Question Schemas (With Rubric Sum Validation & Concepts Breakdown)
# ---------------------------------------------------------------------------
class QuestionBase(BaseModel):
    question_number: int
    question_text: str
    max_marks: float
    model_answer: str
    key_concepts: List[str] = []
    required_concepts: List[str] = []
    optional_concepts: List[str] = []


class QuestionCreate(QuestionBase):
    rubrics: List[RubricCriterionCreate] = []

    @model_validator(mode="after")
    def validate_rubric_sum(self):
        """
        Validate that the sum of rubric criteria marks equals the question maximum marks.
        Only enforces when rubrics are provided.
        """
        if self.rubrics:
            rubric_sum = round(sum(r.max_points for r in self.rubrics), 2)
            target = round(self.max_marks, 2)
            if abs(rubric_sum - target) > 0.01:
                raise ValueError(
                    f"Validation Error: The sum of rubric criterion marks ({rubric_sum} pts) "
                    f"must equal the question maximum marks ({target} pts)."
                )
        return self


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    max_marks: Optional[float] = None
    model_answer: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    required_concepts: Optional[List[str]] = None
    optional_concepts: Optional[List[str]] = None
    rubrics: Optional[List[RubricCriterionCreate]] = None


class Question(QuestionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: Optional[str] = None
    rubrics: List[RubricCriterion] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Assessment Schemas
# ---------------------------------------------------------------------------
class AssessmentBase(BaseModel):
    title: str
    course_code: str
    course_name: Optional[str] = None
    faculty_id: str
    description: Optional[str] = None
    max_score: float = 100.0
    passing_score: float = 40.0
    duration_minutes: int = 60
    status: str = "published"  # draft, published, closed


class AssessmentCreate(AssessmentBase):
    questions: List[QuestionCreate] = []


class Assessment(AssessmentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    questions: List[Question] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Submission & Document Processing Schemas
# ---------------------------------------------------------------------------
class SubmissionAnswerInput(BaseModel):
    question_id: str
    student_answer_text: str


class SubmissionCreate(BaseModel):
    assessment_id: str
    student_id: str  # Shared EDUCORE student_id
    student_name: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    answers: List[SubmissionAnswerInput] = []


class ExtractedTextUpdatePayload(BaseModel):
    corrected_text: str
    editor_id: str = "FACULTY_EDITOR"
    edit_reason: Optional[str] = "Manual faculty transcription review"


class TextEditHistoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: str
    previous_text: str
    updated_text: str
    editor_id: str
    edit_reason: Optional[str] = None
    edited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubmissionAnswer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: Optional[str] = None
    question_id: str
    student_answer_text: str
    ocr_confidence: float = 1.0


class Submission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str
    student_id: str
    student_name: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    extracted_text: Optional[str] = None
    original_extracted_text: Optional[str] = None
    corrected_extracted_text: Optional[str] = None
    is_text_corrected: bool = False
    extraction_status: str = "success"  # success, warning, empty, error, unreadable
    extraction_warnings: List[str] = []
    status: str = "submitted"  # submitted, processing, evaluated, flagged_for_review
    total_score: Optional[float] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answers: List[SubmissionAnswer] = []
    edit_history: List[TextEditHistoryItem] = []


# ---------------------------------------------------------------------------
# Evaluation Schemas
# ---------------------------------------------------------------------------
class RubricScoreItem(BaseModel):
    criterion_name: str
    assigned_points: float
    max_points: float
    comment: str


class EvaluationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: str
    question_id: str
    ai_score: float
    suggested_marks: Optional[float] = None
    final_score: Optional[float] = None
    final_marks: Optional[float] = None
    max_score: float
    confidence_score: float = 0.85
    semantic_similarity: float = 0.80
    rubric_scores: List[RubricScoreItem] = []
    feedback: str
    strengths: List[str] = []
    areas_for_improvement: List[str] = []
    identified_concepts: List[str] = []
    missing_concepts: List[str] = []
    incorrect_concepts: List[str] = []
    supporting_evidence: List[str] = []
    grading_method: str = "deterministic_rubric_v3"
    status: str = "ai_suggested"  # ai_suggested, faculty_reviewed, finalized
    is_moderated: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    moderation_reason: Optional[str] = None
    moderation_history: List[Dict[str, Any]] = []
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationTriggerRequest(BaseModel):
    submission_id: str
    assessment_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Moderation Schemas (Phase 4 Human-in-the-Loop)
# ---------------------------------------------------------------------------
class FacultyModerationRequest(BaseModel):
    reviewed_by: str = "Faculty Reviewer"
    final_marks: float
    moderation_reason: str
    status: str = "faculty_reviewed"  # faculty_reviewed, finalized
    faculty_feedback: Optional[str] = None


class ModerationAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluation_id: str
    reviewed_by: str
    original_suggested_marks: float
    final_marks: float
    score_delta: float
    moderation_reason: str
    faculty_feedback: Optional[str] = None
    status: str = "faculty_reviewed"
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModerationRequest(BaseModel):
    evaluation_id: str
    moderator_id: str
    moderator_name: Optional[str] = None
    adjusted_score: float
    moderation_reason: str
    faculty_feedback: Optional[str] = None
    status: str = "approved"  # approved, overridden


class ModerationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluation_id: str
    moderator_id: str
    moderator_name: Optional[str] = None
    original_score: float
    adjusted_score: float
    score_delta: float
    moderation_reason: str
    faculty_feedback: Optional[str] = None
    status: str = "approved"
    moderated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
