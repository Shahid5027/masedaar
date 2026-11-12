import { apiRequest, ApiResult } from "@/lib/api";
import { NotificationListData, NotificationOut, NotificationScanData } from "@/lib/types";

export const notificationService = {
  listNotifications(params?: {
    unread_only?: boolean;
    limit?: number;
  }): Promise<ApiResult<NotificationListData>> {
    return apiRequest<NotificationListData>("/notifications", {
      query: {
        unread_only: params?.unread_only,
        limit: params?.limit ?? 50,
      },
    });
  },

  markRead(notificationId: number): Promise<ApiResult<NotificationOut>> {
    return apiRequest<NotificationOut>(`/notifications/${notificationId}/read`, {
      method: "PATCH",
    });
  },

  scanFollowups(): Promise<ApiResult<NotificationScanData>> {
    return apiRequest<NotificationScanData>("/notifications/scan-followups", {
      method: "POST",
    });
  },

  retryNotification(notificationId: number): Promise<ApiResult<NotificationOut>> {
    return apiRequest<NotificationOut>(`/notifications/${notificationId}/retry`, {
      method: "POST",
    });
  },
};

