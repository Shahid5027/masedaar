"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Edit3,
  Sliders,
  History,
  ArrowRight
} from "lucide-react";
import { fetchModerationQueue } from "@/lib/api";

export default function FacultyModerationPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const [adjustedScore, setAdjustedScore] = useState<number>(0);
  const [reason, setReason] = useState<string>("");
  const [facultyFeedback, setFacultyFeedback] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadQueue = async () => {
    try {
      setLoading(true);
      const data = await fetchModerationQueue();
      setQueue(data);
      if (data.length > 0 && !selectedItem) {
        selectForModeration(data[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const selectForModeration = (item: any) => {
    setSelectedItem(item);
    setAdjustedScore(item.moderation?.adjusted_score || item.ai_score || 0);
    setReason(item.moderation?.moderation_reason || "Awarded partial credit for conceptual coverage.");
    setFacultyFeedback(item.moderation?.faculty_feedback || "");
  };

  const handleOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem) return;

    try {
      setIsSubmitting(true);
      setToast(null);

      const payload = {
        evaluation_id: selectedItem.id,
        moderator_id: "FAC_PROF_SHARMA",
        moderator_name: "Prof. R. Sharma",
        adjusted_score: Number(adjustedScore),
        moderation_reason: reason,
        faculty_feedback: facultyFeedback,
        status: "approved"
      };

      const res = await fetch("http://localhost:8000/api/ps2/moderation/override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setToast({ type: "success", text: "Score successfully moderated and synchronized!" });
        await loadQueue();
      } else {
        throw new Error(data.error || "Failed to submit moderation");
      }
    } catch (err: any) {
      setToast({ type: "error", text: err.message || "Failed to moderate score" });
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Faculty Moderation & Review</h1>
          <p className="text-xs text-slate-500 mt-1">
            Human-in-the-loop calibration: review AI grades, adjust scores with pedagogical rationale
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadQueue}
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 rounded-lg text-slate-600 transition-colors"
            title="Refresh queue"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {toast && (
        <div
          className={`p-3.5 rounded-xl text-xs font-medium flex items-center space-x-2 border ${
            toast.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-rose-50 text-rose-800 border-rose-200"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          <span>{toast.text}</span>
        </div>
      )}

      {loading ? (
        <div className="bg-white p-12 text-center text-slate-400 rounded-xl border border-slate-200 text-sm">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
          Loading moderation queue...
        </div>
      ) : queue.length === 0 ? (
        <div className="bg-white p-12 text-center text-slate-500 rounded-xl border border-slate-200 text-sm">
          All submissions have been approved. No items currently pending faculty review.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Moderation Queue List */}
          <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 shadow-sm p-4 space-y-3">
            <div className="px-2 py-1 flex items-center justify-between border-b border-slate-100 pb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Pending Calibration ({queue.length})
              </span>
              <span className="text-[11px] text-slate-400">Select to review</span>
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {queue.map((item) => {
                const isSelected = selectedItem?.id === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => selectForModeration(item)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-purple-50/70 border-purple-300 shadow-sm"
                        : "bg-slate-50/60 border-slate-200 hover:bg-slate-100/70"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-slate-800">{item.student_name}</span>
                      <span className="text-xs font-bold text-slate-900">
                        {item.moderation?.adjusted_score || item.ai_score} / {item.max_score} pts
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500 font-mono">
                      <span>{item.student_id}</span>
                      <span className="text-amber-600 font-sans font-medium">
                        Conf: {Math.round((item.confidence_score || 0.8) * 100)}%
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Moderation Form */}
          <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-5">
            {selectedItem ? (
              <form onSubmit={handleOverride} className="space-y-5">
                <div className="border-b border-slate-100 pb-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">
                      Reviewing: {selectedItem.student_name}
                    </h3>
                    <p className="text-xs text-slate-500 font-mono mt-0.5">
                      Student ID: {selectedItem.student_id} • Question {selectedItem.question_id?.slice(-1) || "1"}
                    </p>
                  </div>
                  <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium border border-amber-200">
                    Calibration Needed
                  </span>
                </div>

                {/* AI Score vs Moderated Score */}
                <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                      Current AI Score
                    </label>
                    <div className="text-xl font-bold text-slate-700">
                      {selectedItem.ai_score} <span className="text-xs text-slate-400 font-normal">/ {selectedItem.max_score} pts</span>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-purple-700 uppercase tracking-wider mb-1">
                      Faculty Adjusted Score
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max={selectedItem.max_score}
                      value={adjustedScore}
                      onChange={(e) => setAdjustedScore(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-base font-bold text-purple-900 bg-white border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none"
                    />
                  </div>
                </div>

                {/* AI Feedback Preview */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    AI Evaluator Narrative
                  </label>
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 leading-relaxed">
                    {selectedItem.feedback}
                  </div>
                </div>

                {/* Moderation Rationale */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Faculty Moderation Rationale (Required)
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="State justification for score calibration or override..."
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>

                {/* Additional Feedback */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Custom Instructor Feedback (Optional)
                  </label>
                  <textarea
                    rows={2}
                    value={facultyFeedback}
                    onChange={(e) => setFacultyFeedback(e.target.value)}
                    placeholder="Personalized notes to append to student grade report..."
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-3">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center space-x-2 bg-purple-600 hover:bg-purple-700 text-white font-medium px-5 py-2 rounded-lg text-xs transition-colors shadow-sm disabled:opacity-50"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    <span>{isSubmitting ? "Saving Calibration..." : "Confirm & Save Override"}</span>
                  </button>
                </div>
              </form>
            ) : (
              <div className="p-12 text-center text-slate-400 text-sm">
                Select an item from the queue to calibrate.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

