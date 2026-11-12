import { apiRequest, ApiResult } from "@/lib/api";
import {
  PredictionListData,
  PredictionRunData,
  PredictionRunRequest,
  RiskLevel,
} from "@/lib/types";

export interface PredictionQueryParams {
  limit?: number;
  offset?: number;
  page?: number;
  page_size?: number;
  student_id?: string;
  search?: string;
  risk_level?: RiskLevel;
  model_version?: string;
  is_demo?: boolean;
  predicted_from?: string;
  predicted_to?: string;
  latest_only?: boolean;
  sort_by?: "risk_score" | "predicted_at" | "student_id";
  sort_order?: "asc" | "desc";
}

export const predictionService = {
  runPredictions(payload: PredictionRunRequest = {}): Promise<ApiResult<PredictionRunData>> {
    return apiRequest<PredictionRunData>("/predictions/run", {
      method: "POST",
      body: payload,
    });
  },

  listPredictions(params: PredictionQueryParams = {}): Promise<ApiResult<PredictionListData>> {
    return apiRequest<PredictionListData>("/predictions", {
      query: { ...params },
    });
  },
};

