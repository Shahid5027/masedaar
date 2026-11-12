"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GraduationCap,
  Award,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Search,
  BookOpen,
  ArrowRight,
  TrendingUp,
  FileText
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";

export default function StudentResultPage() {
  const [studentId, setStudentId] = useState<string>("EDU_STU_2026_014");
  const [submissionData, setSubmissionData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchStudentReport = async (id: string) => {
    try {
      setLoading(true);
      const res = await fetch(`http://localhost:8000/api/ps2/submissions?student_id=${encodeURIComponent(id)}`);
      const json = await res.json();
      if (json.data && json.data.length > 0) {
        setSubmissionData(json.data[0]);
      } else {
        setSubmissionData(null);
      }
    } catch (e) {
      console.error(e);
      setSubmissionData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudentReport(studentId);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchStudentReport(studentId);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Student Grade & Formative Feedback</h1>
          <p className="text-xs text-slate-500 mt-1">
            Student evaluation portal utilizing the shared <code className="font-mono text-emerald-600 bg-emerald-50 px-1 py-0.5 rounded">student_id</code> schema
          </p>
        </div>

        {/* Student ID Switcher */}
        <form onSubmit={handleSearch} className="flex items-center space-x-2">
          <input
            type="text"
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            placeholder="Enter student_id..."
            className="px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-medium transition-colors"
          >
            Load Report
          </button>
        </form>
      </div>

      {/* Preset Student IDs */}
      <div className="flex items-center space-x-2 text-xs text-slate-500">
        <span>Quick switch demo IDs:</span>
        <button
          onClick={() => { setStudentId("EDU_STU_2026_014"); fetchStudentReport("EDU_STU_2026_014"); }}
          className="font-mono text-[11px] bg-white border border-slate-200 px-2 py-0.5 rounded hover:bg-slate-50 text-slate-700"
        >
          EDU_STU_2026_014 (High Score)
        </button>
        <button
          onClick={() => { setStudentId("EDU_STU_2026_042"); fetchStudentReport("EDU_STU_2026_042"); }}
          className="font-mono text-[11px] bg-white border border-slate-200 px-2 py-0.5 rounded hover:bg-slate-50 text-slate-700"
        >
          EDU_STU_2026_042 (Moderated)
        </button>
      </div>

      {loading ? (
        <div className="bg-white p-12 text-center text-slate-400 rounded-2xl border border-slate-200 text-sm">
          Loading student report card...
        </div>
      ) : !submissionData ? (
        <div className="bg-white p-12 text-center text-slate-500 rounded-2xl border border-slate-200 text-sm">
          No submission found for student ID &quot;{studentId}&quot;. Ensure the ID matches or submission is recorded.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Card */}
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 text-white p-7 rounded-2xl shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div className="space-y-2">
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <GraduationCap className="w-3.5 h-3.5" />
                <span>Formative Assessment Report</span>
              </span>
              <h2 className="text-2xl font-bold tracking-tight">{submissionData.student_name}</h2>
              <p className="text-xs text-slate-300 font-mono">
                Shared Student ID: {submissionData.student_id} • Status: {submissionData.status}
              </p>
            </div>

            <div className="bg-slate-800/90 border border-slate-700 p-4 rounded-xl text-center sm:text-right min-w-[160px]">
              <span className="text-xs text-slate-400 uppercase tracking-wider block">Total Awarded</span>
              <div className="text-3xl font-extrabold text-emerald-400 mt-1">
                {submissionData.total_score || "N/A"} <span className="text-sm font-normal text-slate-400">/ 50 pts</span>
              </div>
              <span className="text-[11px] text-emerald-300 font-medium mt-1 inline-block">
                Passed Formative Threshold
              </span>
            </div>
          </div>

          {/* Detailed Question Answers & Formative Breakdown */}
          <div className="space-y-6">
            {submissionData.answers?.map((ans: any, idx: number) => {
              const ev = ans.evaluations || {};
              return (
                <div key={idx} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Question #{idx + 1}
                    </span>
                    <div className="flex items-center space-x-2">
                      {ev.is_moderated && (
                        <span className="text-xs text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200 flex items-center space-x-1 font-medium">
                          <ShieldCheck className="w-3.5 h-3.5" />
                          <span>Instructor Calibrated</span>
                        </span>
                      )}
                      <span className="font-bold text-slate-900 text-sm">
                        {ev.moderation?.adjusted_score || ev.ai_score || 0} / {ev.max_score || 25} pts
                      </span>
                    </div>
                  </div>

                  {/* Student Answer Extract */}
                  <div>
                    <p className="text-xs font-semibold text-slate-600 mb-1">Your Submitted Response:</p>
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-700 italic leading-relaxed">
                      &quot;{ans.student_answer_text}&quot;
                    </div>
                  </div>

                  {/* Formative Feedback Narrative */}
                  {ev.feedback && (
                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                      <p className="font-semibold text-slate-700">Formative Assessment Evaluation:</p>
                      <p className="text-slate-600 leading-relaxed">{ev.feedback}</p>
                    </div>
                  )}

                  {/* Strengths & Improvements */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {ev.strengths?.length > 0 && (
                      <div className="p-3.5 bg-emerald-50/50 border border-emerald-200/60 rounded-xl">
                        <span className="text-xs font-semibold text-emerald-800 flex items-center space-x-1 mb-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>What you did well:</span>
                        </span>
                        <ul className="text-xs text-emerald-900 space-y-1 list-disc list-inside">
                          {ev.strengths.map((s: string, i: number) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {ev.areas_for_improvement?.length > 0 && (
                      <div className="p-3.5 bg-amber-50/50 border border-amber-200/60 rounded-xl">
                        <span className="text-xs font-semibold text-amber-800 flex items-center space-x-1 mb-1.5">
                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                          <span>Areas to improve for mastery:</span>
                        </span>
                        <ul className="text-xs text-amber-900 space-y-1 list-disc list-inside">
                          {ev.areas_for_improvement.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Instructor Moderation Rationale Note */}
                  {ev.moderation?.reason && (
                    <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-xs text-purple-900">
                      <span className="font-semibold">Instructor Moderation Note: </span>
                      {ev.moderation.reason}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

