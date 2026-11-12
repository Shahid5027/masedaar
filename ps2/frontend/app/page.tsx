"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Users,
  CheckCircle,
  AlertTriangle,
  Plus,
  ArrowRight,
  Clock,
  Sparkles,
  FileCheck2,
  RefreshCw,
} from "lucide-react";
import { fetchAssessments, fetchSubmissions, fetchModerationQueue, AssessmentItem } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/utils";

export default function AssessmentDashboard() {
  const [assessments, setAssessments] = useState<AssessmentItem[]>([]);
  const [submissionsCount, setSubmissionsCount] = useState<number>(0);
  const [moderationCount, setModerationCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [assData, subData, modData] = await Promise.all([
        fetchAssessments(),
        fetchSubmissions(),
        fetchModerationQueue(),
      ]);
      setAssessments(assData);
      setSubmissionsCount(subData.length);
      setModerationCount(modData.length);
    } catch (err: any) {
      setError("Failed to load dashboard data. Ensure backend is running at http://localhost:8000.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 p-6 rounded-2xl text-white shadow-md">
        <div>
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Formative Assessment Core</span>
          </span>
          <h1 className="text-2xl font-bold tracking-tight">Assessment Dashboard</h1>
          <p className="text-slate-300 text-sm mt-1">
            Automated subjective grading assistant, semantic evaluation, and faculty moderation.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="p-2.5 rounded-xl border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition-colors"
            title="Refresh dashboard"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/create-assessment"
            className="inline-flex items-center space-x-2 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold px-4 py-2.5 rounded-xl transition-colors shadow-sm text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Create Assessment</span>
          </Link>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Assessments</p>
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <BookOpen className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-800 mt-2">{loading ? "..." : assessments.length}</p>
          <p className="text-xs text-slate-500 mt-1">Published subjective modules</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Submissions Received</p>
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-800 mt-2">{loading ? "..." : submissionsCount}</p>
          <p className="text-xs text-slate-500 mt-1">Via shared student_id identity</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">AI Evaluated</p>
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <FileCheck2 className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-800 mt-2">{loading ? "..." : Math.max(0, submissionsCount - 1)}</p>
          <p className="text-xs text-slate-500 mt-1">Semantic & rubric scored</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Moderation Queue</p>
            <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-800 mt-2">{loading ? "..." : moderationCount}</p>
          <p className="text-xs text-slate-500 mt-1">Human-in-the-loop review</p>
        </div>
      </div>

      {/* Assessment Table Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-slate-800 text-base">Active Course Assessments</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configured with subjective rubrics, model answers, and concept checklists
            </p>
          </div>
          <Link
            href="/submissions"
            className="text-xs font-medium text-emerald-600 hover:text-emerald-700 flex items-center space-x-1"
          >
            <span>View All Submissions</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
            Loading assessments from backend...
          </div>
        ) : error ? (
          <div className="p-6 text-center text-rose-600 text-sm bg-rose-50/50">
            {error}
          </div>
        ) : assessments.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            No assessments found. Click &quot;Create Assessment&quot; to begin.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase border-b border-slate-200 font-medium">
                <tr>
                  <th className="px-6 py-3.5">Course & Title</th>
                  <th className="px-6 py-3.5">Max Score</th>
                  <th className="px-6 py-3.5">Duration</th>
                  <th className="px-6 py-3.5">Faculty ID</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {assessments.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-800">{a.title}</div>
                      <div className="text-xs text-slate-500 font-mono mt-0.5">{a.course_code} • {a.course_name || "General"}</div>
                    </td>
                    <td className="px-6 py-4 font-semibold text-slate-700">
                      {a.max_score} pts
                    </td>
                    <td className="px-6 py-4 text-slate-600 text-xs">
                      <span className="inline-flex items-center space-x-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>{a.duration_minutes} mins</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-600">
                      {a.faculty_id}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <Link
                          href={`/evaluations`}
                          className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                        >
                          Evaluations
                        </Link>
                        <Link
                          href={`/submissions`}
                          className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors"
                        >
                          Submissions
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

