const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/ps2";

export interface RubricLevel {
  name: string;
  points: number;
  descriptor: string;
}

export interface RubricCriterion {
  id?: string;
  criterion_name: string;
  description?: string;
  max_points: number;
  weight: number;
  levels: RubricLevel[];
}

export interface QuestionItem {
  id?: string;
  question_number: number;
  question_text: string;
  max_marks: number;
  model_answer: string;
  key_concepts?: string[];
  required_concepts?: string[];
  optional_concepts?: string[];
  rubrics: RubricCriterion[];
}

export interface AssessmentItem {
  id: string;
  title: string;
  course_code: string;
  course_name?: string;
  faculty_id: string;
  description?: string;
  max_score: number;
  passing_score: number;
  duration_minutes: number;
  status: string;
  created_at: string;
  questions?: QuestionItem[];
}

export interface TextEditHistoryItem {
  id: string;
  submission_id: string;
  previous_text: string;
  updated_text: string;
  editor_id: string;
  edit_reason?: string;
  edited_at: string;
}

export interface SubmissionItem {
  id: string;
  assessment_id: string;
  student_id: string;
  student_name?: string;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  file_url?: string;
  extracted_text?: string;
  original_extracted_text?: string;
  corrected_extracted_text?: string;
  is_text_corrected?: boolean;
  extraction_status?: "success" | "warning" | "empty" | "error" | "unreadable" | string;
  extraction_warnings?: string[];
  status: string;
  total_score?: number;
  submitted_at: string;
  answers?: any[];
  edit_history?: TextEditHistoryItem[];
}

export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error("Backend offline");
    return await res.json();
  } catch (err: any) {
    return { status: "offline", error: err.message };
  }
}

export async function fetchAssessments(): Promise<AssessmentItem[]> {
  try {
    const res = await fetch(`${API_BASE}/assessments`, { cache: "no-store" });
    const json = await res.json();
    return json.data || [];
  } catch {
    return [];
  }
}

export async function fetchAssessmentById(id: string): Promise<AssessmentItem | null> {
  try {
    const res = await fetch(`${API_BASE}/assessments/${id}`, { cache: "no-store" });
    const json = await res.json();
    return json.data || null;
  } catch {
    return null;
  }
}

export async function createAssessment(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/assessments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return await res.json();
}

export async function fetchSubmissions(assessmentId?: string): Promise<SubmissionItem[]> {
  try {
    const url = assessmentId
      ? `${API_BASE}/submissions?assessment_id=${encodeURIComponent(assessmentId)}`
      : `${API_BASE}/submissions`;
    const res = await fetch(url, { cache: "no-store" });
    const json = await res.json();
    return json.data || [];
  } catch {
    return [];
  }
}

export async function fetchSubmissionById(submissionId: string): Promise<SubmissionItem | null> {
  try {
    const res = await fetch(`${API_BASE}/submissions/${submissionId}`, { cache: "no-store" });
    const json = await res.json();
    return json.data || null;
  } catch {
    return null;
  }
}

export async function uploadSubmission(
  assessmentId: string,
  formData: FormData
): Promise<any> {
  const res = await fetch(`${API_BASE}/assessments/${assessmentId}/submissions`, {
    method: "POST",
    body: formData,
  });
  return await res.json();
}

export async function updateExtractedText(
  submissionId: string,
  correctedText: string,
  editorId: string = "FAC_INSTRUCTOR",
  editReason: string = "Manual transcription review"
): Promise<any> {
  const res = await fetch(`${API_BASE}/submissions/${submissionId}/extracted-text`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      corrected_text: correctedText,
      editor_id: editorId,
      edit_reason: editReason,
    }),
  });
  return await res.json();
}

export async function fetchModerationQueue(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/moderation/queue`, { cache: "no-store" });
    const json = await res.json();
    return json.data || [];
  } catch {
    return [];
  }
}
