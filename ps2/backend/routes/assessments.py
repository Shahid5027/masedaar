import json
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..models.schemas import (
    Assessment,
    AssessmentCreate,
    Question,
    QuestionCreate,
    QuestionUpdate,
    RubricCriterion,
    APIResponse,
)


router = APIRouter(prefix="/assessments", tags=["Assessments"])

_ASSESSMENTS_STORE: dict[str, Assessment] = {}


def _load_sample_assessments():
    sample_file = Path(__file__).resolve().parent.parent.parent / "sample_data" / "sample_assessment.json"
    if sample_file.exists() and not _ASSESSMENTS_STORE:
        try:
            with open(sample_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                assessment = Assessment(**data)
                _ASSESSMENTS_STORE[assessment.id] = assessment
        except Exception as e:
            print(f"Warning: Failed loading sample assessment: {e}")


_load_sample_assessments()


@router.get("", response_model=APIResponse)
def list_assessments(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    course_code: Optional[str] = Query(None, description="Filter by course code")
):
    """
    Retrieve all published and draft subjective assessments.
    """
    _load_sample_assessments()
    items = list(_ASSESSMENTS_STORE.values())

    if faculty_id:
        items = [a for a in items if a.faculty_id == faculty_id]
    if course_code:
        items = [a for a in items if a.course_code.lower() == course_code.lower()]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(items)} assessments",
        data=[a.model_dump() for a in items]
    )


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreate):
    """
    Create a new formative subjective assessment with questions, rubric criteria,
    and required/optional concepts.
    Validates that the sum of rubric criterion marks equals question max marks.
    """
    # Validate each question's rubrics sum
    for q in payload.questions:
        if q.rubrics:
            rubric_sum = round(sum(r.max_points for r in q.rubrics), 2)
            if abs(rubric_sum - round(q.max_marks, 2)) > 0.01:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Question #{q.question_number} validation error: Sum of rubric marks ({rubric_sum} pts) "
                        f"must equal question maximum marks ({q.max_marks} pts)."
                    )
                )

    new_assessment = Assessment(**payload.model_dump())
    _ASSESSMENTS_STORE[new_assessment.id] = new_assessment

    return APIResponse(
        success=True,
        message="Assessment created and saved successfully",
        data=new_assessment.model_dump()
    )


@router.get("/{assessment_id}", response_model=APIResponse)
def get_assessment(assessment_id: str):
    """
    Fetch an assessment with all its questions and rubrics by unique UUID.
    """
    _load_sample_assessments()
    assessment = _ASSESSMENTS_STORE.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID {assessment_id} not found"
        )
    return APIResponse(
        success=True,
        message="Assessment found",
        data=assessment.model_dump()
    )


@router.post("/{assessment_id}/questions", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def add_question_to_assessment(assessment_id: str, payload: QuestionCreate):
    """
    Add a new question with rubrics and concept tags to an existing assessment.
    Validates that rubric criterion marks sum to the question maximum marks.
    """
    _load_sample_assessments()
    assessment = _ASSESSMENTS_STORE.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID {assessment_id} not found"
        )

    # Validate rubric sum
    if payload.rubrics:
        rubric_sum = round(sum(r.max_points for r in payload.rubrics), 2)
        if abs(rubric_sum - round(payload.max_marks, 2)) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Rubric validation failed: Sum of criterion marks ({rubric_sum} pts) "
                    f"must equal question max marks ({payload.max_marks} pts)."
                )
            )

    new_question = Question(
        assessment_id=assessment_id,
        question_number=payload.question_number,
        question_text=payload.question_text,
        max_marks=payload.max_marks,
        model_answer=payload.model_answer,
        key_concepts=payload.key_concepts,
        required_concepts=payload.required_concepts,
        optional_concepts=payload.optional_concepts,
        rubrics=[
            RubricCriterion(
                question_id="",
                criterion_name=r.criterion_name,
                description=r.description,
                max_points=r.max_points,
                weight=r.weight,
                levels=r.levels
            )
            for r in payload.rubrics
        ]
    )
    for r in new_question.rubrics:
        r.question_id = new_question.id

    assessment.questions.append(new_question)

    return APIResponse(
        success=True,
        message=f"Question #{new_question.question_number} added successfully",
        data=new_question.model_dump()
    )


@router.put("/{assessment_id}/questions/{question_id}", response_model=APIResponse)
def update_question(assessment_id: str, question_id: str, payload: QuestionUpdate):
    """
    Edit an existing question and its rubrics in an assessment.
    """
    _load_sample_assessments()
    assessment = _ASSESSMENTS_STORE.get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    target_q = next((q for q in assessment.questions if q.id == question_id), None)
    if not target_q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    # Update fields if provided
    if payload.question_text is not None:
        target_q.question_text = payload.question_text
    if payload.model_answer is not None:
        target_q.model_answer = payload.model_answer
    if payload.key_concepts is not None:
        target_q.key_concepts = payload.key_concepts
    if payload.required_concepts is not None:
        target_q.required_concepts = payload.required_concepts
    if payload.optional_concepts is not None:
        target_q.optional_concepts = payload.optional_concepts
    if payload.max_marks is not None:
        target_q.max_marks = payload.max_marks

    if payload.rubrics is not None:
        rubric_sum = round(sum(r.max_points for r in payload.rubrics), 2)
        if abs(rubric_sum - round(target_q.max_marks, 2)) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Sum of rubric marks ({rubric_sum}) must equal question max marks ({target_q.max_marks})."
            )
        target_q.rubrics = [
            RubricCriterion(
                question_id=target_q.id,
                criterion_name=r.criterion_name,
                description=r.description,
                max_points=r.max_points,
                weight=r.weight,
                levels=r.levels
            )
            for r in payload.rubrics
        ]

    return APIResponse(
        success=True,
        message="Question updated successfully",
        data=target_q.model_dump()
    )


@router.delete("/{assessment_id}/questions/{question_id}", response_model=APIResponse)
def delete_question(assessment_id: str, question_id: str):
    """
    Delete a question from an assessment.
    """
    _load_sample_assessments()
    assessment = _ASSESSMENTS_STORE.get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    initial_len = len(assessment.questions)
    assessment.questions = [q for q in assessment.questions if q.id != question_id]
    if len(assessment.questions) == initial_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in assessment")

    return APIResponse(
        success=True,
        message="Question deleted successfully",
        data={"deleted_question_id": question_id}
    )
