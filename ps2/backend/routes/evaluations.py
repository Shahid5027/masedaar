import uuid
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status

from ..models.schemas import (
    EvaluationResult,
    EvaluationTriggerRequest,
    APIResponse,
    RubricScoreItem
)
from ..services.semantic_matcher import SemanticMatcher
from ..services.rubric_grader import RubricGrader
from ..services.feedback_generator import FeedbackGenerator
from .assessments import _ASSESSMENTS_STORE
from .submissions import _SUBMISSIONS_STORE


router = APIRouter(tags=["Evaluations"])

# Initialize services
_matcher = SemanticMatcher()
_grader = RubricGrader(semantic_matcher=_matcher)
_feedback_gen = FeedbackGenerator()

_EVALUATIONS_STORE: dict[str, dict] = {}


def _populate_initial_evaluations():
    for sub in _SUBMISSIONS_STORE.values():
        for ans in sub.get("answers", []):
            eval_data = ans.get("evaluations")
            if eval_data:
                eval_id = f"eval-{ans.get('question_id')}-{sub.get('id')}"
                if eval_id not in _EVALUATIONS_STORE:
                    is_mod = eval_data.get("is_moderated", False)
                    mod_info = eval_data.get("moderation")
                    status_val = "faculty_reviewed" if is_mod else "ai_suggested"
                    final_val = mod_info.get("adjusted_score") if mod_info else None
                    history = []
                    if mod_info:
                        history.append({
                            "reviewed_by": mod_info.get("moderator_id", "FAC_PROF_SHARMA"),
                            "original_suggested_marks": eval_data.get("ai_score"),
                            "final_marks": mod_info.get("adjusted_score"),
                            "moderation_reason": mod_info.get("reason", "Partial credit awarded"),
                            "status": "faculty_reviewed",
                            "reviewed_at": datetime.now(timezone.utc).isoformat()
                        })

                    _EVALUATIONS_STORE[eval_id] = {
                        "id": eval_id,
                        "submission_id": sub.get("id"),
                        "question_id": ans.get("question_id"),
                        "student_id": sub.get("student_id"),
                        "student_name": sub.get("student_name"),
                        "ai_score": eval_data.get("ai_score"),
                        "suggested_marks": eval_data.get("ai_score"),
                        "max_score": eval_data.get("max_score", 25.0),
                        "confidence_score": eval_data.get("confidence_score", 0.90),
                        "semantic_similarity": eval_data.get("semantic_similarity", 0.85),
                        "rubric_scores": eval_data.get("rubric_scores", []),
                        "feedback": eval_data.get("feedback", ""),
                        "strengths": eval_data.get("strengths", []),
                        "areas_for_improvement": eval_data.get("areas_for_improvement", []),
                        "identified_concepts": eval_data.get("strengths", []),
                        "missing_concepts": eval_data.get("areas_for_improvement", []),
                        "supporting_evidence": [ans.get("student_answer_text", "")[:120]],
                        "grading_method": "deterministic_rubric_v3",
                        "status": status_val,
                        "is_moderated": is_mod,
                        "final_score": final_val,
                        "final_marks": final_val,
                        "reviewed_by": mod_info.get("moderator_id") if mod_info else None,
                        "moderation_reason": mod_info.get("reason") if mod_info else None,
                        "moderation_history": history,
                        "evaluated_at": datetime.now(timezone.utc).isoformat()
                    }


_populate_initial_evaluations()


@router.get("/evaluations", response_model=APIResponse)
def list_evaluations(
    submission_id: Optional[str] = Query(None, description="Filter by submission ID"),
    is_moderated: Optional[bool] = Query(None, description="Filter by moderation status")
):
    """
    List evaluation results with optional filtering.
    """
    _populate_initial_evaluations()
    results = list(_EVALUATIONS_STORE.values())

    if submission_id:
        results = [e for e in results if e.get("submission_id") == submission_id]
    if is_moderated is not None:
        results = [e for e in results if e.get("is_moderated") == is_moderated]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(results)} evaluations",
        data=results
    )


@router.post("/submissions/{submission_id}/evaluate", response_model=APIResponse, status_code=status.HTTP_200_OK)
def evaluate_submission(submission_id: str):
    """
    Core Phase 3 Grading Engine: Evaluates a student submission against the assessment's rubrics,
    calculates sentence embeddings, applies transparent criteria heuristic, and returns explainable results.
    Guarded against empty or unreadable submissions.
    """
    _populate_initial_evaluations()
    submission = _SUBMISSIONS_STORE.get(submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found."
        )

    # 1. Guard against empty or unreadable submissions
    extraction_status = submission.get("extraction_status", "success")
    extracted_text = submission.get("corrected_extracted_text") or submission.get("extracted_text") or ""

    # If root extracted_text is not set, check answers list
    if not extracted_text.strip() and submission.get("answers"):
        extracted_text = "\n\n".join(
            ans.get("student_answer_text", "")
            for ans in submission.get("answers", [])
            if ans.get("student_answer_text")
        )

    if extraction_status in ("empty", "unreadable") or not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Never grade an empty or unreadable submission. Please upload a readable file or provide corrected text."
        )

    assessment_id = submission.get("assessment_id")
    assessment = _ASSESSMENTS_STORE.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated assessment '{assessment_id}' not found."
        )

    # If the submission has no per-question partitioned answers, use extracted_text against the questions
    questions = assessment.questions
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment contains no questions to evaluate against."
        )

    evaluated_records = []
    total_eval_score = 0.0

    # Evaluate each question in the assessment
    for q in questions:
        # Determine the student answer text for this question
        # If answers list is populated, match by question_id; else use full extracted text
        q_answer_text = extracted_text
        for ans in submission.get("answers", []):
            if ans.get("question_id") == q.id and ans.get("student_answer_text"):
                q_answer_text = ans.get("student_answer_text")
                break

        rubric_payload = [r.model_dump() for r in q.rubrics]
        grade_res = _grader.grade_answer(
            student_answer=q_answer_text,
            model_answer=q.model_answer,
            key_concepts=q.key_concepts,
            rubrics=rubric_payload,
            max_marks=q.max_marks,
            required_concepts=q.required_concepts,
            optional_concepts=q.optional_concepts
        )

        feedback_res = _feedback_gen.generate_feedback(
            student_answer=q_answer_text,
            model_answer=q.model_answer,
            grading_result=grade_res
        )

        eval_id = f"eval-{q.id}-{submission_id}"
        record = {
            "id": eval_id,
            "submission_id": submission_id,
            "question_id": q.id,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "student_id": submission.get("student_id"),
            "student_name": submission.get("student_name"),
            "student_answer": q_answer_text,
            "model_answer": q.model_answer,
            "ai_score": grade_res["ai_score"],
            "suggested_marks": grade_res["suggested_marks"],
            "final_score": None,
            "final_marks": None,
            "max_score": grade_res["max_score"],
            "confidence_score": grade_res["confidence_score"],
            "semantic_similarity": grade_res["semantic_similarity"],
            "rubric_scores": grade_res["rubric_scores"],
            "identified_concepts": grade_res["identified_concepts"],
            "missing_concepts": grade_res["missing_concepts"],
            "incorrect_concepts": grade_res["incorrect_concepts"],
            "supporting_evidence": grade_res["supporting_evidence"],
            "feedback": feedback_res["feedback"],
            "strengths": feedback_res["strengths"],
            "areas_for_improvement": feedback_res["areas_for_improvement"],
            "how_to_improve": feedback_res["how_to_improve"],
            "revision_topics": feedback_res["revision_topics"],
            "warnings": grade_res["warnings"],
            "grading_method": grade_res["grading_method"],
            "status": "ai_suggested",
            "is_moderated": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "moderation_reason": None,
            "moderation_history": [],
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }

        _EVALUATIONS_STORE[eval_id] = record
        evaluated_records.append(record)
        total_eval_score += grade_res["suggested_marks"]

    # Update submission object
    submission["status"] = "evaluated"
    submission["total_score"] = round(total_eval_score, 2)
    submission["updated_at"] = datetime.now(timezone.utc).isoformat()

    return APIResponse(
        success=True,
        message=f"AI evaluation successfully completed for submission '{submission_id}'.",
        data={
            "submission_id": submission_id,
            "total_score": round(total_eval_score, 2),
            "evaluations": evaluated_records
        }
    )


@router.post("/evaluations/trigger", response_model=APIResponse)
def trigger_evaluation_alias(payload: EvaluationTriggerRequest):
    """
    Alias endpoint for triggering evaluation from existing Phase 1 clients.
    """
    return evaluate_submission(payload.submission_id)


@router.get("/evaluations/{evaluation_id}", response_model=APIResponse)
def get_evaluation(evaluation_id: str):
    """
    Get explainable evaluation record by ID.
    """
    _populate_initial_evaluations()
    record = _EVALUATIONS_STORE.get(evaluation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation with ID '{evaluation_id}' not found."
        )
    return APIResponse(
        success=True,
        message="Evaluation record found",
        data=record
    )
