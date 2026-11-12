"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  KeyRound,
  RefreshCw,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { useAuth } from "@/components/auth/AuthProvider";
import { ApiClientError } from "@/lib/api";
import {
  OperationalStatusData,
  SecurityAuditLogOut,
  UserOut,
  UserRole,
} from "@/lib/types";
import { opsService } from "@/services/opsService";
import { userService } from "@/services/userService";

export default function AdminWorkspacePage() {
  return (
    <RoleGuard allowedRoles={["administrator"]} sectionTitle="Administration & Security">
      <AdminWorkspaceContent />
    </RoleGuard>
  );
}

function AdminWorkspaceContent() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserOut[]>([]);
  const [opsStatus, setOpsStatus] = useState<OperationalStatusData | null>(null);
  const [auditLogs, setAuditLogs] = useState<SecurityAuditLogOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("counsellor");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersRes, opsRes, auditRes] = await Promise.all([
        userService.listUsers(),
        opsService.getOperationalStatus(),
        opsService.listSecurityAuditLogs({ limit: 30 }),
      ]);
      setUsers(usersRes.data.items);
      setOpsStatus(opsRes.data);
      setAuditLogs(auditRes.data.items);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Failed to load administration data."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function handleCreateUser(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await userService.createUser({
        username: username.trim(),
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        password,
        is_active: true,
      });
      setFeedback(`Created user '${res.data.username}' with role '${res.data.role}'.`);
      setUsername("");
      setEmail("");
      setFullName("");
      setPassword("");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Unable to create user.");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(target: UserOut) {
    setError(null);
    setFeedback(null);
    try {
      const res = await userService.updateUser(target.id, { is_active: !target.is_active });
      setFeedback(
        `User '${res.data.username}' is now ${res.data.is_active ? "active" : "disabled"}.`
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Unable to update user status.");
    }
  }

  async function handleRoleChange(target: UserOut, nextRole: UserRole) {
    if (target.role === nextRole) return;
    setError(null);
    setFeedback(null);
    try {
      const res = await userService.updateUser(target.id, { role: nextRole });
      setFeedback(`Updated '${res.data.username}' role to '${res.data.role}'.`);
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Unable to update user role.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Administration & Security Audit</h1>
          <p className="text-sm text-slate-600">
            Manage platform accounts, operational telemetry, and security event logs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadAll()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {feedback && (
        <div
          role="status"
          className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
        >
          {feedback}
        </div>
      )}

      {/* Operational Health Telemetry */}
      {opsStatus && (
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Activity className="h-4 w-4 text-slate-700" />
            <h2 className="text-sm font-semibold text-slate-900">Operational Telemetry</h2>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6 text-xs">
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Environment</p>
              <p className="mt-1 font-semibold text-slate-900">{opsStatus.environment}</p>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Database</p>
              <p className="mt-1 font-semibold text-slate-900">
                {opsStatus.database_connected ? "Connected" : "Offline"} (
                {opsStatus.database_dialect})
              </p>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Active Sessions</p>
              <p className="mt-1 font-semibold text-slate-900">
                {opsStatus.active_sessions_count}
              </p>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Failed Logins (24h)</p>
              <p className="mt-1 font-semibold text-slate-900">{opsStatus.failed_logins_24h}</p>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Model Artifact</p>
              <p className="mt-1 font-semibold text-slate-900">
                {opsStatus.model_artifact_available
                  ? opsStatus.active_model_version || "Ready"
                  : "Missing"}
              </p>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-slate-500">Email Transport</p>
              <p className="mt-1 font-semibold text-slate-900">{opsStatus.email_transport}</p>
            </div>
          </div>
        </section>
      )}

      {/* User Management */}
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-1">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <UserPlus className="h-4 w-4 text-slate-700" />
            <h2 className="text-sm font-semibold text-slate-900">Provision Account</h2>
          </div>
          <form onSubmit={handleCreateUser} className="mt-4 space-y-3 text-xs">
            <div>
              <label htmlFor="new-username" className="block font-medium text-slate-700">
                Username
              </label>
              <input
                id="new-username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="counsellor.alex"
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </div>
            <div>
              <label htmlFor="new-email" className="block font-medium text-slate-700">
                Institutional Email
              </label>
              <input
                id="new-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex@university.edu"
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </div>
            <div>
              <label htmlFor="new-fullname" className="block font-medium text-slate-700">
                Full Name
              </label>
              <input
                id="new-fullname"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alex Rivera"
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </div>
            <div>
              <label htmlFor="new-role" className="block font-medium text-slate-700">
                Role
              </label>
              <select
                id="new-role"
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              >
                <option value="counsellor">Counsellor</option>
                <option value="viewer">Viewer (Cohort Read-Only)</option>
                <option value="administrator">Administrator</option>
              </select>
            </div>
            <div>
              <label htmlFor="new-password" className="block font-medium text-slate-700">
                Temporary Password (min 8 chars, mixed classes)
              </label>
              <input
                id="new-password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </div>
            <button
              type="submit"
              disabled={creating}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-60"
            >
              <KeyRound className="h-3.5 w-3.5" />
              {creating ? "Creating..." : "Create Account"}
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Users className="h-4 w-4 text-slate-700" />
            <h2 className="text-sm font-semibold text-slate-900">
              Platform Accounts ({users.length})
            </h2>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-2 pr-3 font-medium">User</th>
                  <th className="py-2 pr-3 font-medium">Role</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5 pr-3">
                      <p className="font-semibold text-slate-900">{u.username}</p>
                      <p className="text-slate-500">
                        {u.full_name} · {u.email}
                      </p>
                    </td>
                    <td className="py-2.5 pr-3">
                      <select
                        aria-label={`Role for ${u.username}`}
                        value={u.role}
                        onChange={(e) => void handleRoleChange(u, e.target.value as UserRole)}
                        disabled={currentUser?.id === u.id}
                        className="rounded border border-slate-300 px-2 py-1 text-xs disabled:bg-slate-100"
                      >
                        <option value="administrator">administrator</option>
                        <option value="counsellor">counsellor</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          u.is_active
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="py-2.5">
                      <button
                        type="button"
                        disabled={currentUser?.id === u.id}
                        onClick={() => void handleToggleActive(u)}
                        className="rounded border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {u.is_active ? "Disable" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Security Audit Logs */}
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Shield className="h-4 w-4 text-slate-700" />
          <h2 className="text-sm font-semibold text-slate-900">
            Security Audit Log (Recent {auditLogs.length})
          </h2>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-2 pr-3 font-medium">Timestamp</th>
                <th className="py-2 pr-3 font-medium">Event</th>
                <th className="py-2 pr-3 font-medium">Actor</th>
                <th className="py-2 pr-3 font-medium">Summary</th>
                <th className="py-2 font-medium">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {auditLogs.map((log) => (
                <tr key={log.id}>
                  <td className="py-2 pr-3 whitespace-nowrap text-slate-500">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-3 font-mono text-[11px] font-semibold text-slate-800">
                    {log.event_type}
                  </td>
                  <td className="py-2 pr-3 text-slate-700">
                    {log.actor_username || "system"}{" "}
                    {log.actor_role ? `(${log.actor_role})` : ""}
                  </td>
                  <td className="py-2 pr-3 text-slate-800">{log.summary}</td>
                  <td className="py-2 font-mono text-[11px] text-slate-500">
                    {log.ip_address || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

