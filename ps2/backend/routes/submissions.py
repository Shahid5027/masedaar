import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, status

from ..models.schemas import (
    Submission,
    SubmissionCreate,
    SubmissionAnswer,
    ExtractedTextUpdatePayload,
    TextEditHistoryItem,
    APIResponse
)
from ..services.pdf_extractor import DocumentExtractorService
from ..services.text_preprocessor import TextPreprocessor


router = APIRouter(tags=["Submissions"])

_SUBMISSIONS_STORE: dict[str, dict] = {}


def _load_sample_submissions():
    sample_file = Path(__file__).resolve().parent.parent.parent / "sample_data" / "sample_submissions.json"
    if sample_file.exists() and not _SUBMISSIONS_STORE:
        try:
            with open(sample_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    # Ensure Phase 2 fields are initialized if missing
                    item.setdefault("file_name", "sample_script.pdf")
                    item.setdefault("file_type", "application/pdf")
                    item.setdefault("file_size", 10240)
                    item.setdefault("extraction_status", "success")
                    item.setdefault("extraction_warnings", [])
                    item.setdefault("original_extracted_text", item.get("extracted_text", ""))
                    item.setdefault("corrected_extracted_text", None)
                    item.setdefault("is_text_corrected", False)
                    item.setdefault("edit_history", [])
                    _SUBMISSIONS_STORE[item["id"]] = item
        except Exception as e:
            print(f"Warning: Failed loading sample submissions: {e}")


_load_sample_submissions()

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.get("/submissions", response_model=APIResponse)
def list_submissions(
    assessment_id: Optional[str] = Query(None, description="Filter by assessment ID"),
    student_id: Optional[str] = Query(None, description="Filter by shared EDUCORE student ID"),
    status_filter: Optional[str] = Query(None, alias="status")
):
    """
    List submissions with optional filtering by assessment, student_id, or status.
    """
    _load_sample_submissions()
    items = list(_SUBMISSIONS_STORE.values())

    if assessment_id:
        items = [s for s in items if s.get("assessment_id") == assessment_id]
    if student_id:
        items = [s for s in items if s.get("student_id") == student_id]
    if status_filter:
        items = [s for s in items if s.get("status") == status_filter]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(items)} submissions",
        data=items
    )


@router.post("/assessments/{assessment_id}/submissions", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_assessment_submission(
    assessment_id: str,
    student_id: str = Form(..., description="Shared EDUCORE student ID"),
    student_name: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """
    Upload and process student submission (PDF or TXT) for a specified assessment.
    Performs digital text extraction, validation, empty document detection, and prepares extraction preview.
    """
    filename = file.filename or "uploaded_file"
    ext = os.path.splitext(filename)[1].lower()

    # 1. Extension Validation
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only PDF (.pdf) and Plain Text (.txt) files are accepted."
        )

    # 2. Read File Bytes & Validate Size
    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes). Never grade an empty submission."
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 15MB. (Uploaded: {round(file_size/(1024*1024), 2)}MB)"
        )

    file_type = file.content_type or ("application/pdf" if ext == ".pdf" else "text/plain")

    # 3. Extract Document Text using PyMuPDF / Direct Text
    extraction_res = DocumentExtractorService.extract_document(contents, filename)
    extracted_text = extraction_res.get("extracted_text", "")
    extraction_status = extraction_res.get("status", "success")
    warnings = extraction_res.get("warnings", [])

    if not extraction_res.get("success") and extraction_status in ("empty", "unreadable", "error"):
        # Flag appropriately but store record so faculty can review & correct if needed
        submission_status = "flagged_for_review"
    else:
        submission_status = "submitted"

    # 4. Create and persist submission
    new_sub = Submission(
        assessment_id=assessment_id,
        student_id=student_id.strip(),
        student_name=student_name.strip() if student_name else f"Student {student_id.strip()}",
        file_name=filename,
        file_size=file_size,
        file_type=file_type,
        file_url=f"/storage/submissions/{assessment_id}/{filename}",
        extracted_text=extracted_text,
        original_extracted_text=extracted_text,
        corrected_extracted_text=None,
        is_text_corrected=False,
        extraction_status=extraction_status,
        extraction_warnings=warnings,
        status=submission_status,
        answers=[]
    )

    sub_dict = new_sub.model_dump()
    _SUBMISSIONS_STORE[new_sub.id] = sub_dict

    return APIResponse(
        success=True,
        message=f"File '{filename}' uploaded and processed ({extraction_status})",
        data=sub_dict
    )


@router.get("/submissions/{submission_id}", response_model=APIResponse)
def get_submission(submission_id: str):
    """
    Retrieve single submission by UUID, including document metadata, extraction preview,
    and edit history.
    """
    _load_sample_submissions()
    sub = _SUBMISSIONS_STORE.get(submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission with ID {submission_id} not found"
        )
    return APIResponse(
        success=True,
        message="Submission found",
        data=sub
    )


@router.put("/submissions/{submission_id}/extracted-text", response_model=APIResponse)
def update_extracted_text(submission_id: str, payload: ExtractedTextUpdatePayload):
    """
    Allows faculty to manually correct or transcribe extracted text.
    Preserves audit history of changes and updates active extracted text.
    """
    _load_sample_submissions()
    sub = _SUBMISSIONS_STORE.get(submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission with ID {submission_id} not found"
        )

    previous_text = sub.get("corrected_extracted_text") or sub.get("extracted_text") or ""
    new_text = payload.corrected_text.strip()

    if not new_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrected text cannot be empty. Never grade an empty submission."
        )

    # Create history entry
    history_entry = TextEditHistoryItem(
        submission_id=submission_id,
        previous_text=previous_text,
        updated_text=new_text,
        editor_id=payload.editor_id,
        edit_reason=payload.edit_reason or "Faculty manual transcription review",
        edited_at=datetime.now(timezone.utc)
    )

    sub["corrected_extracted_text"] = new_text
    sub["extracted_text"] = new_text
    sub["is_text_corrected"] = True
    sub["extraction_status"] = "success"  # Mark as resolved/valid
    sub.setdefault("edit_history", []).append(history_entry.model_dump())
    sub["updated_at"] = datetime.now(timezone.utc).isoformat()

    return APIResponse(
        success=True,
        message="Extracted text successfully updated and logged in audit history",
        data={
            "submission_id": submission_id,
            "corrected_text": new_text,
            "is_text_corrected": True,
            "history_count": len(sub["edit_history"])
        }
    )
