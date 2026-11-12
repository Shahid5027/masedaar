"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Trash2,
  ArrowLeft,
  Check,
  Sparkles,
  AlertCircle,
  HelpCircle,
  Layers,
  Tag,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import { createAssessment } from "@/lib/api";

interface RubricLevelInput {
  name: string;
  points: number;
  descriptor: string;
}

interface RubricCriterionInput {
  criterion_name: string;
  description: string;
  max_points: number;
  weight: number;
  levels: RubricLevelInput[];
}

interface QuestionInput {
  question_number: number;
  question_text: string;
  max_marks: number;
  model_answer: string;
  key_concepts_raw: string;
  required_concepts_raw: string;
  optional_concepts_raw: string;
  rubrics: RubricCriterionInput[];
}

export default function CreateAssessmentPage() {
  const router = useRouter();
  const [title, setTitle] = useState("Operating Systems Memory & Virtualization");
  const [courseCode, setCourseCode] = useState("CS-302");
  const [courseName, setCourseName] = useState("Operating Systems");
  const [facultyId, setFacultyId] = useState("FAC_PROF_SHARMA");
  const [description, setDescription] = useState(
    "Formative subjective assessment testing student understanding of paging, TLB caching, and page fault resolution."
  );
  const [duration, setDuration] = useState(60);

  const [questions, setQuestions] = useState<QuestionInput[]>([
    {
      question_number: 1,
      question_text:
        "Explain the hardware and OS sequence during a Page Fault. Detail the role of the TLB, Page Table, swap space, and page replacement algorithm.",
      max_marks: 25,
      model_answer:
        "When an address translation fails in the TLB and the Page Table Entry has Present=0, the MMU signals a Page Fault trap to the OS kernel. The OS inspects the backing swap store, locates a free physical frame (or executes page replacement e.g. Clock/LRU if memory is full, evicting a dirty page to disk), issues disk I/O to read the required page into the frame, writes the new physical address and Present=1 into the PTE, updates the TLB, and returns from the trap, restarting the faulting instruction.",
      key_concepts_raw: "page fault trap, TLB miss, present bit, free frame allocation, page replacement, swap I/O, restart instruction",
      required_concepts_raw: "page fault trap, TLB miss, present bit, swap I/O, restart instruction",
      optional_concepts_raw: "Clock algorithm, dirty bit writeback, inverted page table",
      rubrics: [
        {
          criterion_name: "Hardware Trap & MMU Detection",
          description: "Understanding of TLB check, PTE present bit, and kernel trap",
          max_points: 10,
          weight: 1.0,
          levels: [
            { name: "Exemplary", points: 10, descriptor: "Full MMU translation sequence with present bit detection." },
            { name: "Proficient", points: 7, descriptor: "Correct trap sequence with minor gap in MMU register flags." },
            { name: "Developing", points: 4, descriptor: "Mentions page fault without hardware mechanism." },
          ],
        },
        {
          criterion_name: "Eviction & Swap I/O Resolution",
          description: "Page replacement and disk fetch sequence",
          max_points: 15,
          weight: 1.0,
          levels: [
            { name: "Exemplary", points: 15, descriptor: "Details swap fetch, eviction if full, PTE update, and instruction restart." },
            { name: "Proficient", points: 11, descriptor: "Mentions swap and replacement but misses instruction restart." },
            { name: "Developing", points: 6, descriptor: "Vaguely mentions loading from disk." },
          ],
        },
      ],
    },
  ]);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Compute total assessment marks from questions
  const totalAssessmentMarks = questions.reduce((acc, q) => acc + (Number(q.max_marks) || 0), 0);

  // Rubric validation helper
  const getQuestionRubricSum = (q: QuestionInput) => {
    return q.rubrics.reduce((acc, r) => acc + (Number(r.max_points) || 0), 0);
  };

  const hasRubricErrors = questions.some((q) => {
    if (q.rubrics.length === 0) return false;
    const sum = getQuestionRubricSum(q);
    return Math.abs(sum - Number(q.max_marks)) > 0.01;
  });

  const addQuestion = () => {
    const nextNum = questions.length + 1;
    setQuestions([
      ...questions,
      {
        question_number: nextNum,
        question_text: "",
        max_marks: 20,
        model_answer: "",
        key_concepts_raw: "",
        required_concepts_raw: "",
        optional_concepts_raw: "",
        rubrics: [
          {
            criterion_name: "Core Concept Accuracy",
            description: "Thorough understanding of fundamental principles",
            max_points: 20,
            weight: 1.0,
            levels: [
              { name: "Exemplary", points: 20, descriptor: "Accurate, comprehensive, and well-articulated." },
              { name: "Developing", points: 10, descriptor: "Basic understanding with gaps." },
            ],
          },
        ],
      },
    ]);
  };

  const removeQuestion = (idx: number) => {
    if (questions.length <= 1) return;
    const updated = questions.filter((_, i) => i !== idx).map((q, i) => ({ ...q, question_number: i + 1 }));
    setQuestions(updated);
  };

  const addRubricCriterion = (qIdx: number) => {
    const updated = [...questions];
    updated[qIdx].rubrics.push({
      criterion_name: "New Criterion",
      description: "Criterion description",
      max_points: 5,
      weight: 1.0,
      levels: [
        { name: "Exemplary", points: 5, descriptor: "Full criterion coverage." },
        { name: "Developing", points: 2, descriptor: "Partial criterion coverage." },
      ],
    });
    setQuestions(updated);
  };

  const removeRubricCriterion = (qIdx: number, rIdx: number) => {
    const updated = [...questions];
    if (updated[qIdx].rubrics.length <= 1) return;
    updated[qIdx].rubrics.splice(rIdx, 1);
    setQuestions(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (hasRubricErrors) {
      setFeedbackMsg({
        type: "error",
        text: "Cannot save: Please fix rubric mark discrepancies so criterion sums equal question max marks.",
      });
      return;
    }

    setIsSubmitting(true);
    setFeedbackMsg(null);

    const payload = {
      title,
      course_code: courseCode,
      course_name: courseName,
      faculty_id: facultyId,
      description,
      max_score: totalAssessmentMarks,
      passing_score: Math.round(totalAssessmentMarks * 0.4),
      duration_minutes: Number(duration),
      status: "published",
      questions: questions.map((q) => ({
        question_number: q.question_number,
        question_text: q.question_text,
        max_marks: Number(q.max_marks),
        model_answer: q.model_answer,
        key_concepts: q.key_concepts_raw.split(",").map((s) => s.trim()).filter(Boolean),
        required_concepts: q.required_concepts_raw.split(",").map((s) => s.trim()).filter(Boolean),
        optional_concepts: q.optional_concepts_raw.split(",").map((s) => s.trim()).filter(Boolean),
        rubrics: q.rubrics.map((r) => ({
          criterion_name: r.criterion_name,
          description: r.description,
          max_points: Number(r.max_points),
          weight: Number(r.weight),
          levels: r.levels,
        })),
      })),
    };

    try {
      const data = await createAssessment(payload);
      if (data.success) {
        setFeedbackMsg({ type: "success", text: "Assessment & rubrics saved and published successfully!" });
        setTimeout(() => {
          router.push("/");
        }, 1200);
      } else {
        throw new Error(data.error || "Failed to save assessment");
      }
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: err.message || "Failed to save assessment. Ensure FastAPI backend is active.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors space-x-1"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
        <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full font-medium">
          Faculty Assessment & Rubric Builder
        </span>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
        <div className="border-b border-slate-100 pb-5 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Create Subjective Assessment</h1>
            <p className="text-xs text-slate-500 mt-1">
              Configure subjective prompts, required/optional concepts taxonomy, and weighted rubric criteria.
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-400 block uppercase font-semibold">Total Calculated Marks</span>
            <span className="text-2xl font-black text-slate-800">{totalAssessmentMarks} pts</span>
          </div>
        </div>

        {feedbackMsg && (
          <div
            className={`p-4 rounded-xl text-sm mb-6 flex items-center space-x-2.5 ${
              feedbackMsg.type === "success"
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-rose-50 text-rose-800 border border-rose-200"
            }`}
          >
            {feedbackMsg.type === "success" ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{feedbackMsg.text}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Metadata Section */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Assessment Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Course Code & Name</label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  required
                  value={courseCode}
                  onChange={(e) => setCourseCode(e.target.value)}
                  placeholder="e.g. CS-302"
                  className="w-1/3 px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none uppercase font-mono"
                />
                <input
                  type="text"
                  value={courseName}
                  onChange={(e) => setCourseName(e.target.value)}
                  placeholder="Subject / Course Name"
                  className="w-2/3 px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Faculty ID</label>
              <input
                type="text"
                required
                value={facultyId}
                onChange={(e) => setFacultyId(e.target.value)}
                className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Duration (Minutes)</label>
              <input
                type="number"
                min="5"
                required
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Assessment Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          {/* Question & Rubric Editor */}
          <div className="pt-6 border-t border-slate-200 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-800 text-sm">Questions & Rubric Breakdown</h3>
                <p className="text-xs text-slate-500">
                  Each question requires reference answers, concept tags, and balanced rubrics.
                </p>
              </div>
              <button
                type="button"
                onClick={addQuestion}
                className="inline-flex items-center space-x-1.5 text-xs font-semibold text-emerald-700 hover:text-emerald-800 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 rounded-lg border border-emerald-200 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Question</span>
              </button>
            </div>

            {questions.map((q, qIdx) => {
              const rubricSum = getQuestionRubricSum(q);
              const isRubricBalanced = Math.abs(rubricSum - Number(q.max_marks)) <= 0.01;

              return (
                <div key={qIdx} className="bg-slate-50 border border-slate-200 p-6 rounded-2xl space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
                    <div className="flex items-center space-x-3">
                      <span className="w-8 h-8 rounded-lg bg-slate-900 text-white font-bold text-xs flex items-center justify-center">
                        Q{q.question_number}
                      </span>
                      <span className="font-semibold text-slate-800 text-sm">Question #{q.question_number}</span>
                    </div>

                    <div className="flex items-center space-x-3">
                      <div className="flex items-center space-x-1 text-xs">
                        <span className="font-medium text-slate-600">Max Marks:</span>
                        <input
                          type="number"
                          min="1"
                          required
                          value={q.max_marks}
                          onChange={(e) => {
                            const updated = [...questions];
                            updated[qIdx].max_marks = Number(e.target.value);
                            setQuestions(updated);
                          }}
                          className="w-16 px-2 py-1 text-xs font-bold border border-slate-300 rounded bg-white text-center"
                        />
                      </div>

                      {questions.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeQuestion(qIdx)}
                          className="text-rose-600 hover:text-rose-800 p-1 text-xs flex items-center space-x-1"
                          title="Delete question"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Question Prompt</label>
                    <textarea
                      rows={2}
                      required
                      value={q.question_text}
                      onChange={(e) => {
                        const updated = [...questions];
                        updated[qIdx].question_text = e.target.value;
                        setQuestions(updated);
                      }}
                      placeholder="Enter subjective prompt..."
                      className="w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Model Reference Answer (Evaluator Ground Truth)
                    </label>
                    <textarea
                      rows={3}
                      required
                      value={q.model_answer}
                      onChange={(e) => {
                        const updated = [...questions];
                        updated[qIdx].model_answer = e.target.value;
                        setQuestions(updated);
                      }}
                      placeholder="Comprehensive theoretical solution..."
                      className="w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    />
                  </div>

                  {/* Required and Optional Concepts */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-white p-4 rounded-xl border border-slate-200">
                    <div>
                      <label className="block text-xs font-semibold text-slate-800 mb-1 flex items-center space-x-1">
                        <Tag className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Required Concepts (Must be mentioned)</span>
                      </label>
                      <input
                        type="text"
                        value={q.required_concepts_raw}
                        onChange={(e) => {
                          const updated = [...questions];
                          updated[qIdx].required_concepts_raw = e.target.value;
                          setQuestions(updated);
                        }}
                        placeholder="Comma-separated (e.g. TLB miss, swap I/O, restart)"
                        className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-800 mb-1 flex items-center space-x-1">
                        <Tag className="w-3.5 h-3.5 text-indigo-600" />
                        <span>Optional / Bonus Concepts</span>
                      </label>
                      <input
                        type="text"
                        value={q.optional_concepts_raw}
                        onChange={(e) => {
                          const updated = [...questions];
                          updated[qIdx].optional_concepts_raw = e.target.value;
                          setQuestions(updated);
                        }}
                        placeholder="Comma-separated (e.g. Clock algorithm, dirty bit)"
                        className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  {/* Rubric Criteria Sub-section */}
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Layers className="w-4 h-4 text-slate-600" />
                        <h4 className="font-semibold text-slate-800 text-xs">Rubric Criteria</h4>
                        {/* Rubric Validation Indicator */}
                        {isRubricBalanced ? (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-medium bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">
                            <Check className="w-3 h-3 text-emerald-600" />
                            <span>Sum: {rubricSum} / {q.max_marks} pts (Balanced)</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-medium bg-rose-50 text-rose-700 px-2 py-0.5 rounded-full border border-rose-200">
                            <AlertTriangle className="w-3 h-3 text-rose-600" />
                            <span>
                              Sum: {rubricSum} / {q.max_marks} pts (Discrepancy: {rubricSum - Number(q.max_marks)} pts)
                            </span>
                          </span>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => addRubricCriterion(qIdx)}
                        className="text-xs font-medium text-emerald-700 hover:text-emerald-900 flex items-center space-x-1"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add Criterion</span>
                      </button>
                    </div>

                    <div className="space-y-2">
                      {q.rubrics.map((rubric, rIdx) => (
                        <div
                          key={rIdx}
                          className="bg-white p-3.5 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                        >
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center space-x-2">
                              <input
                                type="text"
                                required
                                value={rubric.criterion_name}
                                onChange={(e) => {
                                  const updated = [...questions];
                                  updated[qIdx].rubrics[rIdx].criterion_name = e.target.value;
                                  setQuestions(updated);
                                }}
                                placeholder="Criterion Name"
                                className="font-medium text-xs text-slate-800 border-b border-transparent hover:border-slate-300 focus:border-emerald-500 focus:outline-none w-1/2"
                              />
                            </div>
                            <input
                              type="text"
                              value={rubric.description}
                              onChange={(e) => {
                                const updated = [...questions];
                                updated[qIdx].rubrics[rIdx].description = e.target.value;
                                setQuestions(updated);
                              }}
                              placeholder="Brief description of expectations"
                              className="text-[11px] text-slate-500 w-full border-b border-transparent hover:border-slate-300 focus:border-emerald-500 focus:outline-none"
                            />
                          </div>

                          <div className="flex items-center space-x-3">
                            <div className="flex items-center space-x-1 text-xs">
                              <span className="text-slate-500 text-[11px]">Points:</span>
                              <input
                                type="number"
                                min="0.5"
                                step="0.5"
                                required
                                value={rubric.max_points}
                                onChange={(e) => {
                                  const updated = [...questions];
                                  updated[qIdx].rubrics[rIdx].max_points = Number(e.target.value);
                                  setQuestions(updated);
                                }}
                                className="w-14 px-1.5 py-1 text-xs font-bold border border-slate-200 rounded text-center"
                              />
                            </div>

                            {q.rubrics.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeRubricCriterion(qIdx, rIdx)}
                                className="text-slate-400 hover:text-rose-600 transition-colors p-1"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Submit Actions */}
          <div className="pt-4 border-t border-slate-200 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {hasRubricErrors ? (
                <span className="text-rose-600 font-medium flex items-center space-x-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Cannot submit: One or more questions have rubric mark discrepancies.</span>
                </span>
              ) : (
                <span className="text-emerald-700 font-medium flex items-center space-x-1">
                  <Check className="w-3.5 h-3.5" />
                  <span>All rubric criterion sums match question maximum marks.</span>
                </span>
              )}
            </div>

            <div className="flex items-center space-x-3">
              <Link
                href="/"
                className="px-4 py-2 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={isSubmitting || hasRubricErrors}
                className="inline-flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-5 py-2 rounded-lg text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-4 h-4" />
                <span>{isSubmitting ? "Publishing Assessment..." : "Publish Assessment"}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
