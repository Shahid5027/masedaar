import { apiRequest, ApiResult } from "@/lib/api";
import { OperationalStatusData, SecurityAuditListData } from "@/lib/types";

export const opsService = {
  getOperationalStatus(): Promise<ApiResult<OperationalStatusData>> {
    return apiRequest<OperationalStatusData>("/ops/status");
  },

  listSecurityAuditLogs(params?: {
    limit?: number;
    offset?: number;
    event_type?: string;
  }): Promise<ApiResult<SecurityAuditListData>> {
    return apiRequest<SecurityAuditListData>("/audit/security", {
      query: {
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
        event_type: params?.event_type || undefined,
      },
    });
  },
};

