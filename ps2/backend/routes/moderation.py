from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status

from ..models.schemas import ModerationRequest, ModerationRecord, APIResponse
from .evaluations import _EVALUATIONS_STORE
from .submissions import _SUBMISSIONS_STORE


router = APIRouter(prefix="/moderation", tags=["Moderation"])

_MODERATION_RECORDS_STORE: dict[str, ModerationRecord] = {}


@router.get("/queue", response_model=APIResponse)
def get_moderation_queue(
    confidence_threshold: float = Query(0.80, description="Items with confidence below this threshold")
):
    """
    Retrieve evaluations requiring faculty review (low confidence, flagged, or unreviewed).
    """
    queue_items = []
    for eval_item in _EVALUATIONS_STORE.values():
        conf = eval_item.get("confidence_score", 1.0)
        is_mod = eval_item.get("is_moderated", False)
        if conf <= confidence_threshold or not is_mod:
            queue_items.append(eval_item)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(queue_items)} items requiring review",
        data=queue_items
    )


@router.post("/override", response_model=APIResponse)
def apply_moderation_override(payload: ModerationRequest):
    """
    Faculty human-in-the-loop override: adjust AI score, input rationale, and confirm moderation.
    """
    eval_item = _EVALUATIONS_STORE.get(payload.evaluation_id)
    if not eval_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {payload.evaluation_id} not found"
        )

    original_score = eval_item.get("ai_score", 0.0)
    delta = payload.adjusted_score - original_score

    record = ModerationRecord(
        evaluation_id=payload.evaluation_id,
        moderator_id=payload.moderator_id,
        moderator_name=payload.moderator_name or payload.moderator_id,
        original_score=original_score,
        adjusted_score=payload.adjusted_score,
        score_delta=round(delta, 2),
        moderation_reason=payload.moderation_reason,
        faculty_feedback=payload.faculty_feedback,
        status=payload.status
    )
    _MODERATION_RECORDS_STORE[record.id] = record

    # Update evaluation entry
    eval_item["is_moderated"] = True
    eval_item["final_score"] = payload.adjusted_score
    eval_item["moderation"] = record.model_dump()

    # If submission exists, update total score accordingly
    sub_id = eval_item.get("submission_id")
    if sub_id and sub_id in _SUBMISSIONS_STORE:
        sub = _SUBMISSIONS_STORE[sub_id]
        if sub.get("total_score") is not None:
            sub["total_score"] = round(sub["total_score"] + delta, 2)
            sub["status"] = "evaluated"

    return APIResponse(
        success=True,
        message="Moderation override saved successfully",
        data=record.model_dump()
    )


@router.get("/records", response_model=APIResponse)
def list_moderation_records():
    """
    List historical moderation logs.
    """
    records = list(_MODERATION_RECORDS_STORE.values())
    return APIResponse(
        success=True,
        message=f"Retrieved {len(records)} moderation logs",
        data=[r.model_dump() for r in records]
    )

