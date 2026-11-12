import { apiRequest, ApiResult } from "@/lib/api";
import {
  InterventionArchiveRequest,
  InterventionCreateRequest,
  InterventionDetailData,
  InterventionHistoryListData,
  InterventionListData,
  InterventionPriority,
  InterventionRecordOut,
  InterventionStatus,
  InterventionUpdateRequest,
  StudentInterventionsData,
} from "@/lib/types";

export interface InterventionQueryParams {
  limit?: number;
  offset?: number;
  page?: number;
  page_size?: number;
  student_id?: string;
  status?: InterventionStatus;
  priority?: InterventionPriority;
  assigned_to?: string;
  is_demo?: boolean;
  search?: string;
  overdue_only?: boolean;
  sort_by?:
    | "created_at"
    | "updated_at"
    | "follow_up_date"
    | "priority"
    | "student_id"
    | "status";
  sort_order?: "asc" | "desc";
}

export const interventionService = {
  listInterventions(params: InterventionQueryParams = {}): Promise<ApiResult<InterventionListData>> {
    return apiRequest<InterventionListData>("/interventions", {
      query: { ...params },
    });
  },

  getInterventionDetail(interventionId: number): Promise<ApiResult<InterventionDetailData>> {
    return apiRequest<InterventionDetailData>(`/interventions/${interventionId}`);
  },

  getInterventionHistory(
    interventionId: number
  ): Promise<ApiResult<InterventionHistoryListData>> {
    return apiRequest<InterventionHistoryListData>(`/interventions/${interventionId}/history`);
  },

  createIntervention(
    payload: InterventionCreateRequest
  ): Promise<ApiResult<InterventionRecordOut>> {
    return apiRequest<InterventionRecordOut>("/interventions", {
      method: "POST",
      body: payload,
    });
  },

  updateIntervention(
    interventionId: number,
    payload: InterventionUpdateRequest
  ): Promise<ApiResult<InterventionRecordOut>> {
    return apiRequest<InterventionRecordOut>(`/interventions/${interventionId}`, {
      method: "PATCH",
      body: payload,
    });
  },

  archiveIntervention(
    interventionId: number,
    payload: InterventionArchiveRequest
  ): Promise<ApiResult<InterventionRecordOut>> {
    return apiRequest<InterventionRecordOut>(`/interventions/${interventionId}/archive`, {
      method: "POST",
      body: payload,
    });
  },

  listStudentInterventions(studentId: string): Promise<ApiResult<StudentInterventionsData>> {
    return apiRequest<StudentInterventionsData>(
      `/students/${encodeURIComponent(studentId)}/interventions`
    );
  },
};

