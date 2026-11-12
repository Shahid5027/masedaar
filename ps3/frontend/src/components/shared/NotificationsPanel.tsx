"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, RefreshCw, AlertCircle, Mail } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { ApiClientError } from "@/lib/api";
import { NotificationOut } from "@/lib/types";
import { notificationService } from "@/services/notificationService";

export function NotificationsPanel() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationOut[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [transport, setTransport] = useState<string>("disabled");
  const [notice, setNotice] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canUseNotifications = user?.role === "administrator" || user?.role === "counsellor";

  const loadNotifications = useCallback(async () => {
    if (!canUseNotifications) return;
    setLoading(true);
    setError(null);
    try {
      const res = await notificationService.listNotifications({ limit: 25 });
      setItems(res.data.items);
      setUnreadCount(res.data.unread_count);
      setTransport(res.data.email_transport);
      setNotice(res.data.email_verification_notice);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Unable to load notifications."
      );
    } finally {
      setLoading(false);
    }
  }, [canUseNotifications]);

  useEffect(() => {
    if (canUseNotifications) {
      void loadNotifications();
    }
  }, [canUseNotifications, loadNotifications]);

  if (!canUseNotifications) {
    return null;
  }

  async function handleScanFollowups() {
    setScanning(true);
    setError(null);
    try {
      await notificationService.scanFollowups();
      await loadNotifications();
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Failed to scan follow-ups."
      );
    } finally {
      setScanning(false);
    }
  }

  async function handleMarkRead(notificationId: number) {
    try {
      const res = await notificationService.markRead(notificationId);
      setItems((prev) =>
        prev.map((item) => (item.id === notificationId ? res.data : item))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to mark as read.");
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          const nextOpen = !open;
          setOpen(nextOpen);
          if (nextOpen) {
            void loadNotifications();
          }
        }}
        aria-label="Notifications"
        className="relative inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        <Bell className="h-4 w-4 text-slate-600" />
        <span className="hidden sm:inline">Alerts</span>
        {unreadCount > 0 && (
          <span
            data-testid="unread-notifications-badge"
            className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1.5 py-0.5 text-[10px] font-semibold text-white"
          >
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="In-app notifications"
          className="absolute right-0 z-50 mt-2 w-80 sm:w-96 rounded-lg border border-slate-200 bg-white shadow-xl"
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Intervention Alerts</h3>
              <p className="text-[11px] text-slate-500">
                Email transport: <span className="font-mono">{transport}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleScanFollowups()}
              disabled={scanning}
              className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-3 w-3 ${scanning ? "animate-spin" : ""}`} />
              Scan Due
            </button>
          </div>

          {notice && (
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-600">
              <span className="inline-flex items-center gap-1 font-medium text-slate-700">
                <Mail className="h-3 w-3" /> Email notice:
              </span>{" "}
              {notice}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 border-b border-rose-100 bg-rose-50 px-4 py-2 text-xs text-rose-800">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
            {loading && items.length === 0 ? (
              <p className="p-4 text-xs text-slate-500">Loading alerts...</p>
            ) : items.length === 0 ? (
              <p className="p-4 text-xs text-slate-500">No notifications recorded yet.</p>
            ) : (
              items.map((item) => (
                <div
                  key={item.id}
                  className={`px-4 py-3 text-xs ${
                    item.is_read ? "bg-white text-slate-600" : "bg-sky-50/50 text-slate-900"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold text-slate-900">{item.title}</p>
                    {!item.is_read && (
                      <button
                        type="button"
                        onClick={() => void handleMarkRead(item.id)}
                        className="inline-flex shrink-0 items-center gap-1 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <CheckCheck className="h-3 w-3" /> Read
                      </button>
                    )}
                  </div>
                  <p className="mt-1 text-slate-700">{item.message}</p>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400">
                    <span>
                      {item.event_type} · email: {item.email_status}
                    </span>
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

