"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  TrendingUp,
  RefreshCw,
  Award,
  BookOpen,
  FileText,
  Quote,
  Target,
  AlertTriangle,
  Lightbulb,
  Check,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";

interface RubricScoreItem {
  criterion_name: string;
  assigned_points: number;
  max_points: number;
  evidence_coverage?: number;
  correctness_factor?: number;
  supporting_excerpts?: string[];
  identified_concepts?: string[];
  missing_concepts?: string[];
  comment?: string;
}

interface EvaluationItem {
  id: string;
  submission_id: string;
  question_id: string;
  question_number?: number;
  question_text?: string;
  student_id: string;
  student_name: string;
  student_answer?: string;
  model_answer?: string;
  ai_score: number;
  suggested_marks?: number;
  max_score: number;
  confidence_score: number;
  semantic_similarity: number;
  rubric_scores: RubricScoreItem[];
  feedback: string;
  strengths: string[];
  areas_for_improvement: string[];
  how_to_improve?: string[];
  revision_topics?: string[];
  identified_concepts?: string[];
  missing_concepts?: string[];
  incorrect_concepts?: string[];
  supporting_evidence?: string[];
  warnings?: string[];
  grading_method?: string;
  is_moderated: boolean;
  moderation?: any;
}

export default function EvaluationResultsPage() {
  const [evaluations, setEvaluations] = useState<EvaluationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterModerated, setFilterModerated] = useState<string>("all");

  const loadEvaluations = async () => {
    try {
      setLoading(true);
      const res = await fetch("http://localhost:8000/api/ps2/evaluations", { cache: "no-store" });
      const json = await res.json();
      const data = json.data || [];
      setEvaluations(data);
      if (data.length > 0 && !expandedId) {
        setExpandedId(data[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvaluations();
  }, []);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const filtered = evaluations.filter((e) => {
    if (filterModerated === "moderated") return e.is_moderated;
    if (filterModerated === "unmoderated") return !e.is_moderated;
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">AI Evaluation & Grading Results</h1>
          <p className="text-xs text-slate-500 mt-1">
            Explainable rubric scoring: <code className="font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">Criterion Max × Coverage × Correctness</code>
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={filterModerated}
            onChange={(e) => setFilterModerated(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="all">All Evaluated Answers</option>
            <option value="unmoderated">AI Automated Only</option>
            <option value="moderated">Faculty Calibrated</option>
          </select>
          <button
            onClick={loadEvaluations}
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 rounded-lg text-slate-600 transition-colors"
            title="Refresh evaluations"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="bg-white p-12 text-center text-slate-400 rounded-xl border border-slate-200 text-sm">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
          Loading explainable evaluation matrix...
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white p-12 text-center text-slate-500 rounded-xl border border-slate-200 text-sm">
          No evaluations found. Upload a submission and click &quot;Evaluate&quot; to begin.
        </div>
      ) : (
        <div className="space-y-6">
          {filtered.map((item) => {
            const isExpanded = expandedId === item.id;
            const scoreToDisplay = item.moderation?.adjusted_score || item.suggested_marks || item.ai_score;
            const scorePercent = Math.round((scoreToDisplay / item.max_score) * 100);

            return (
              <div
                key={item.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden transition-all"
              >
                {/* Summary Strip (Clickable) */}
                <div
                  onClick={() => toggleExpand(item.id)}
                  className="p-6 cursor-pointer hover:bg-slate-50/60 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100"
                >
                  <div className="flex items-start space-x-3.5">
                    <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center font-bold text-sm shrink-0">
                      Q{item.question_number || item.question_id.slice(-1) || "1"}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-slate-900 text-sm">{item.student_name}</span>
                        <span className="font-mono text-[11px] bg-slate-100 px-2 py-0.5 rounded text-slate-600 border border-slate-200">
                          {item.student_id}
                        </span>
                        {item.is_moderated ? (
                          <span className="text-[10px] bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full border border-purple-200 font-medium">
                            Moderated
                          </span>
                        ) : (
                          <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200 font-medium">
                            AI Scored
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                        {item.question_text || "Subjective Evaluation Response"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-6 shrink-0">
                    <div className="text-right">
                      <div className="text-2xl font-black text-slate-900">
                        {scoreToDisplay} <span className="text-xs font-normal text-slate-400">/ {item.max_score} pts</span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-medium">
                        {scorePercent}% Alignment • Conf: {Math.round((item.confidence_score || 0.85) * 100)}%
                      </span>
                    </div>

                    <div className="p-1.5 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-600">
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                  </div>
                </div>

                {/* Expanded Detailed Explainable View */}
                {isExpanded && (
                  <div className="p-6 space-y-6 bg-slate-50/40 animate-in fade-in duration-150">
                    {/* Method & Confidence Metadata Pill */}
                    <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-white rounded-xl border border-slate-200 text-xs">
                      <div className="flex items-center space-x-2">
                        <Sparkles className="w-4 h-4 text-emerald-600" />
                        <span className="font-semibold text-slate-700">Grading Method:</span>
                        <span className="font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                          {item.grading_method || "Sentence Transformers (all-MiniLM-L6-v2) + Rubric Heuristic"}
                        </span>
                      </div>
                      <div className="flex items-center space-x-3 text-slate-500 text-[11px]">
                        <span>Semantic Similarity: <strong>{Math.round((item.semantic_similarity || 0.8) * 100)}%</strong></span>
                        <span>Confidence: <strong>{Math.round((item.confidence_score || 0.85) * 100)}%</strong></span>
                      </div>
                    </div>

                    {/* Side-by-side Answer Comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Student Answer */}
                      <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                            <FileText className="w-3.5 h-3.5 text-slate-500" />
                            <span>Student Submitted Answer</span>
                          </span>
                        </div>
                        <p className="text-xs text-slate-700 leading-relaxed font-mono bg-slate-50 p-3 rounded-lg border border-slate-100 whitespace-pre-wrap max-h-56 overflow-y-auto">
                          {item.student_answer || "Student answer text unavailable."}
                        </p>
                      </div>

                      {/* Reference Model Answer */}
                      <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 flex items-center space-x-1.5">
                            <Target className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Reference Model Solution (Ground Truth)</span>
                          </span>
                        </div>
                        <p className="text-xs text-slate-700 leading-relaxed bg-emerald-50/40 p-3 rounded-lg border border-emerald-100 whitespace-pre-wrap max-h-56 overflow-y-auto">
                          {item.model_answer || "Reference solution unavailable."}
                        </p>
                      </div>
                    </div>

                    {/* Criterion-Level Scoring Breakdown */}
                    <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                        <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">
                          Criterion-Level Rubric Breakdown
                        </h4>
                        <span className="text-[11px] text-slate-500">
                          Marks = Max Points × Evidence Coverage × Correctness
                        </span>
                      </div>

                      <div className="space-y-3">
                        {item.rubric_scores?.map((crit, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3"
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                              <div>
                                <span className="font-bold text-xs text-slate-800">{crit.criterion_name}</span>
                                <p className="text-xs text-slate-500 mt-0.5">{crit.comment}</p>
                              </div>
                              <div className="text-right shrink-0">
                                <span className="text-sm font-bold text-slate-900">
                                  {crit.assigned_points} / {crit.max_points} pts
                                </span>
                                {crit.evidence_coverage !== undefined && (
                                  <div className="text-[10px] text-slate-400">
                                    Cov: {Math.round(crit.evidence_coverage * 100)}% • Corr: {Math.round((crit.correctness_factor || 1.0) * 100)}%
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Supporting Excerpts */}
                            {crit.supporting_excerpts && crit.supporting_excerpts.length > 0 && (
                              <div className="bg-white p-3 rounded-lg border border-slate-200 text-xs">
                                <span className="text-[10px] font-semibold text-slate-400 uppercase block mb-1 flex items-center space-x-1">
                                  <Quote className="w-3 h-3" />
                                  <span>Supporting Student Answer Excerpt:</span>
                                </span>
                                <p className="text-slate-700 italic text-[11px]">
                                  &quot;{crit.supporting_excerpts[0]}&quot;
                                </p>
                              </div>
                            )}

                            {/* Concepts identified vs missing */}
                            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px]">
                              {crit.identified_concepts?.map((c, i) => (
                                <span key={i} className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded border border-emerald-200 flex items-center space-x-1">
                                  <Check className="w-3 h-3" />
                                  <span>{c}</span>
                                </span>
                              ))}
                              {crit.missing_concepts?.map((c, i) => (
                                <span key={i} className="bg-rose-50 text-rose-700 px-2 py-0.5 rounded border border-rose-200 flex items-center space-x-1">
                                  <AlertCircle className="w-3 h-3" />
                                  <span>Missing: {c}</span>
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Formative Feedback Narrative */}
                    <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                      <div className="border-b border-slate-100 pb-3">
                        <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">
                          Formative Pedagogical Feedback
                        </h4>
                        <p className="text-xs text-slate-700 mt-2 bg-slate-50 p-3.5 rounded-lg border border-slate-100 leading-relaxed">
                          {item.feedback}
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {/* What was explained correctly */}
                        <div className="bg-emerald-50/40 border border-emerald-200 rounded-xl p-4">
                          <span className="text-xs font-bold text-emerald-800 flex items-center space-x-1.5 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            <span>What Was Explained Correctly:</span>
                          </span>
                          <ul className="text-xs text-emerald-900 space-y-1 list-disc list-inside">
                            {item.strengths?.map((s, idx) => (
                              <li key={idx}>{s}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Missing & Improvement */}
                        <div className="bg-amber-50/40 border border-amber-200 rounded-xl p-4">
                          <span className="text-xs font-bold text-amber-800 flex items-center space-x-1.5 mb-2">
                            <Lightbulb className="w-4 h-4 text-amber-600" />
                            <span>How to Improve & Missing Concepts:</span>
                          </span>
                          <ul className="text-xs text-amber-900 space-y-1 list-disc list-inside">
                            {item.areas_for_improvement?.map((a, idx) => (
                              <li key={idx}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      {/* Revision Topics */}
                      {item.revision_topics && item.revision_topics.length > 0 && (
                        <div className="pt-2 flex items-center space-x-2 text-xs">
                          <span className="font-semibold text-slate-600">Recommended Revision Topics:</span>
                          <div className="flex flex-wrap gap-1.5">
                            {item.revision_topics.map((t, idx) => (
                              <span key={idx} className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-[11px] font-medium border border-indigo-200">
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end space-x-3 pt-2">
                      <Link
                        href="/moderation"
                        className="text-xs font-medium text-slate-700 hover:text-slate-900 px-4 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-xs"
                      >
                        Open Faculty Calibration
                      </Link>
                      <Link
                        href="/student-result"
                        className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 px-4 py-2 rounded-lg bg-emerald-50 hover:bg-emerald-100 transition-colors"
                      >
                        View Student Card
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
