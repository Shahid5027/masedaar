import { apiRequest, ApiResult } from "@/lib/api";
import {
  RiskLevel,
  StudentDetailData,
  StudentExplanationData,
  StudentInterventionsData,
  StudentListData,
} from "@/lib/types";

export interface StudentQueryParams {
  limit?: number;
  offset?: number;
  page?: number;
  page_size?: number;
  is_synthetic?: boolean;
  search?: string;
  risk_level?: RiskLevel | "unscored";
  min_attendance?: number;
  max_attendance?: number;
  min_failures?: number;
  predicted_from?: string;
  predicted_to?: string;
  sort_by?:
    | "student_id"
    | "updated_at"
    | "attendance_rate"
    | "average_grade"
    | "missing_assignments"
    | "previous_failure_count"
    | "risk_score"
    | "predicted_at";
  sort_order?: "asc" | "desc";
}

export const studentService = {
  listStudents(params: StudentQueryParams = {}): Promise<ApiResult<StudentListData>> {
    return apiRequest<StudentListData>("/students", {
      query: { ...params },
    });
  },

  getStudentDetail(studentId: string): Promise<ApiResult<StudentDetailData>> {
    return apiRequest<StudentDetailData>(`/students/${encodeURIComponent(studentId)}`);
  },

  getStudentExplanation(studentId: string): Promise<ApiResult<StudentExplanationData>> {
    return apiRequest<StudentExplanationData>(
      `/students/${encodeURIComponent(studentId)}/explanation`
    );
  },

  getStudentInterventions(studentId: string): Promise<ApiResult<StudentInterventionsData>> {
    return apiRequest<StudentInterventionsData>(
      `/students/${encodeURIComponent(studentId)}/interventions`
    );
  },
};

