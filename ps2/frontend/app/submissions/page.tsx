"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  Play,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  Sparkles,
  ArrowRight,
  Eye,
  Edit3,
  Save,
  X,
  FileCheck,
  FileWarning,
  Clock,
  History,
  AlertCircle,
  FileUp,
} from "lucide-react";
import {
  fetchSubmissions,
  fetchAssessments,
  uploadSubmission,
  updateExtractedText,
  SubmissionItem,
  AssessmentItem,
} from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/utils";

export default function StudentSubmissionsPage() {
  const [submissions, setSubmissions] = useState<SubmissionItem[]>([]);
  const [assessments, setAssessments] = useState<AssessmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadAssessmentId, setUploadAssessmentId] = useState("");
  const [uploadStudentId, setUploadStudentId] = useState("EDU_STU_2026_099");
  const [uploadStudentName, setUploadStudentName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Extraction Preview / Edit state
  const [inspectSubmission, setInspectSubmission] = useState<SubmissionItem | null>(null);
  const [editedText, setEditedText] = useState("");
  const [editReason, setEditReason] = useState("Corrected OCR symbol transcription");
  const [isSavingText, setIsSavingText] = useState(false);
  const [saveToast, setSaveToast] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Grading trigger state
  const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [subData, assData] = await Promise.all([
        fetchSubmissions(),
        fetchAssessments(),
      ]);
      setSubmissions(subData);
      setAssessments(assData);
      if (assData.length > 0 && !uploadAssessmentId) {
        setUploadAssessmentId(assData[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openInspector = (sub: SubmissionItem) => {
    setInspectSubmission(sub);
    setEditedText(sub.corrected_extracted_text || sub.extracted_text || "");
    setSaveToast(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "pdf" && ext !== "txt") {
        setUploadError("Invalid file type. Only PDF (.pdf) and Plain Text (.txt) files are supported.");
        setSelectedFile(null);
        return;
      }
      if (file.size > 15 * 1024 * 1024) {
        setUploadError("File size exceeds 15MB limit.");
        setSelectedFile(null);
        return;
      }
      setUploadError(null);
      setSelectedFile(file);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError("Please select a valid PDF or TXT file.");
      return;
    }
    if (!uploadAssessmentId) {
      setUploadError("Please select an assessment.");
      return;
    }

    try {
      setIsUploading(true);
      setUploadError(null);

      const formData = new FormData();
      formData.append("student_id", uploadStudentId.trim());
      if (uploadStudentName.trim()) {
        formData.append("student_name", uploadStudentName.trim());
      }
      formData.append("file", selectedFile);

      const res = await uploadSubmission(uploadAssessmentId, formData);
      if (res.success) {
        setShowUploadModal(false);
        setSelectedFile(null);
        await loadData();
        // Immediately open inspection preview for the newly uploaded submission
        if (res.data) {
          openInspector(res.data);
        }
        setToastMsg(`Submission uploaded successfully! Document extracted via PyMuPDF/TXT.`);
      } else {
        throw new Error(res.error || "Upload failed");
      }
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload and process file.");
    } finally {
      setIsUploading(false);
      setTimeout(() => setToastMsg(null), 5000);
    }
  };

  const handleSaveCorrectedText = async () => {
    if (!inspectSubmission) return;
    if (!editedText.trim()) {
      setSaveToast({ type: "error", text: "Extracted text cannot be empty. Never grade an empty submission." });
      return;
    }

    try {
      setIsSavingText(true);
      setSaveToast(null);

      const res = await updateExtractedText(
        inspectSubmission.id,
        editedText.trim(),
        "FAC_PROF_SHARMA",
        editReason
      );

      if (res.success) {
        setSaveToast({ type: "success", text: "Corrected text saved and audit history logged!" });
        // Update local submission state
        const updatedList = submissions.map((s) => {
          if (s.id === inspectSubmission.id) {
            return {
              ...s,
              extracted_text: editedText.trim(),
              corrected_extracted_text: editedText.trim(),
              is_text_corrected: true,
              extraction_status: "success",
            };
          }
          return s;
        });
        setSubmissions(updatedList);
        setInspectSubmission({
          ...inspectSubmission,
          extracted_text: editedText.trim(),
          corrected_extracted_text: editedText.trim(),
          is_text_corrected: true,
          extraction_status: "success",
        });
      } else {
        throw new Error(res.error || "Failed to save corrected text");
      }
    } catch (err: any) {
      setSaveToast({ type: "error", text: err.message || "Failed to save text" });
    } finally {
      setIsSavingText(false);
      setTimeout(() => setSaveToast(null), 4000);
    }
  };

  const triggerEvaluation = async (submissionId: string, assessmentId: string) => {
    try {
      setEvaluatingId(submissionId);
      const res = await fetch("http://localhost:8000/api/ps2/evaluations/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submission_id: submissionId, assessment_id: assessmentId }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setToastMsg(`Evaluation completed! Score: ${data.data.total_score} pts`);
        await loadData();
      } else {
        alert("Evaluation failed: " + (data.error || "Unknown error"));
      }
    } catch (err: any) {
      alert("Error triggering evaluation: " + err.message);
    } finally {
      setEvaluatingId(null);
      setTimeout(() => setToastMsg(null), 5000);
    }
  };

  const filtered = submissions.filter((s) => {
    const q = searchQuery.toLowerCase();
    return (
      s.student_id?.toLowerCase().includes(q) ||
      s.student_name?.toLowerCase().includes(q) ||
      s.file_name?.toLowerCase().includes(q) ||
      s.id?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Student Submissions & Processing</h1>
          <p className="text-xs text-slate-500 mt-1">
            PyMuPDF digital text extraction, TXT parsing, extraction preview, and faculty transcription editor
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Submission (PDF/TXT)</span>
          </button>
          <button
            onClick={loadData}
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 rounded-xl text-slate-600 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {toastMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-medium flex items-center space-x-2 shadow-sm">
          <Sparkles className="w-4 h-4 text-emerald-600" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search by student_id, name, or file..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <div className="text-xs text-slate-500 font-medium">
          Showing {filtered.length} of {submissions.length} submissions
        </div>
      </div>

      {/* Main Submissions Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
            Loading submissions...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            No submissions found. Click &quot;Upload Submission&quot; to test PDF or TXT extraction.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase border-b border-slate-200 font-medium">
                <tr>
                  <th className="px-6 py-3.5">Student Info</th>
                  <th className="px-6 py-3.5">Shared Student ID</th>
                  <th className="px-6 py-3.5">Document Details</th>
                  <th className="px-6 py-3.5">Extraction Status</th>
                  <th className="px-6 py-3.5">Score</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((s) => {
                  const extStatus = s.extraction_status || "success";
                  const isUnreadable = extStatus === "empty" || extStatus === "unreadable";

                  return (
                    <tr key={s.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-800">{s.student_name || "Student"}</div>
                        <div className="text-xs text-slate-400 font-mono mt-0.5">#{s.id.slice(0, 8)}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded border border-slate-200">
                          {s.student_id}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-2 text-xs text-slate-700 font-medium">
                          <FileText className="w-4 h-4 text-slate-400" />
                          <span className="truncate max-w-[150px]">{s.file_name || "script.pdf"}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {s.file_type || "application/pdf"} • {formatDateTime(s.submitted_at)}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-1.5">
                          {extStatus === "success" ? (
                            <span className="inline-flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              Extracted
                            </span>
                          ) : extStatus === "warning" ? (
                            <span className="inline-flex items-center text-xs font-medium text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              Short Text
                            </span>
                          ) : (
                            <span className="inline-flex items-center text-xs font-medium text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
                              <FileWarning className="w-3 h-3 mr-1" />
                              {extStatus.toUpperCase()}
                            </span>
                          )}
                          {s.is_text_corrected && (
                            <span className="text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded border border-purple-200">
                              Edited
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {s.total_score !== undefined && s.total_score !== null ? (
                          <span className="font-bold text-slate-900">{s.total_score} pts</span>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Ungraded</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => openInspector(s)}
                            className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors"
                            title="Preview extracted text"
                          >
                            <Eye className="w-3.5 h-3.5 text-slate-500" />
                            <span>Preview</span>
                          </button>
                          <button
                            onClick={() => triggerEvaluation(s.id, s.assessment_id)}
                            disabled={evaluatingId === s.id || isUnreadable}
                            title={isUnreadable ? "Cannot grade empty or unreadable submission" : "Trigger AI grading"}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            <Play className={`w-3 h-3 ${evaluatingId === s.id ? "animate-spin" : ""}`} />
                            <span>{evaluatingId === s.id ? "Grading..." : "Evaluate"}</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: Upload Student Submission (PDF / TXT) */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Upload Student Submission</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  PyMuPDF extraction engine for digital PDF and direct TXT
                </p>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {uploadError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Assessment</label>
                <select
                  value={uploadAssessmentId}
                  onChange={(e) => setUploadAssessmentId(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                >
                  {assessments.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.course_code} - {a.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Shared Student ID <span className="text-emerald-600">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={uploadStudentId}
                    onChange={(e) => setUploadStudentId(e.target.value)}
                    placeholder="EDU_STU_2026_xxx"
                    className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Student Name (Optional)</label>
                  <input
                    type="text"
                    value={uploadStudentName}
                    onChange={(e) => setUploadStudentName(e.target.value)}
                    placeholder="e.g. Ananya Rao"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              {/* File Dropzone */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Upload Answer Document (PDF or TXT)
                </label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-300 hover:border-emerald-500 rounded-xl p-6 text-center cursor-pointer transition-colors bg-slate-50 hover:bg-emerald-50/20"
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept=".pdf,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <FileUp className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                  {selectedFile ? (
                    <div>
                      <p className="text-xs font-semibold text-slate-800">{selectedFile.name}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {Math.round(selectedFile.size / 1024)} KB • Ready to extract
                      </p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs font-medium text-slate-700">Click to browse or drag & drop</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">PDF or Plain Text (.txt) up to 15MB</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 border border-slate-300 text-xs font-medium rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !selectedFile}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm disabled:opacity-50"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{isUploading ? "Extracting Text..." : "Upload & Extract"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER / INSPECTOR: Extraction Preview & Faculty Transcription Editor */}
      {inspectSubmission && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-xs flex items-center justify-end">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-200 border-l border-slate-200">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="font-bold text-slate-900 text-base">Extraction Preview & Correction</h3>
                  {inspectSubmission.is_text_corrected ? (
                    <span className="text-[11px] bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full border border-purple-200 font-medium">
                      Faculty Corrected
                    </span>
                  ) : (
                    <span className="text-[11px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200 font-medium">
                      Digital Extraction
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Student: {inspectSubmission.student_name} ({inspectSubmission.student_id})
                </p>
              </div>
              <button
                onClick={() => setInspectSubmission(null)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {saveToast && (
                <div
                  className={`p-3.5 rounded-xl text-xs font-medium flex items-center space-x-2 border ${
                    saveToast.type === "success"
                      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                      : "bg-rose-50 text-rose-800 border-rose-200"
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{saveToast.text}</span>
                </div>
              )}

              {/* File Meta Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Filename</span>
                  <p className="text-xs font-semibold text-slate-800 truncate mt-0.5">
                    {inspectSubmission.file_name || "script.pdf"}
                  </p>
                </div>
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Type / Size</span>
                  <p className="text-xs font-semibold text-slate-800 truncate mt-0.5">
                    {inspectSubmission.file_type?.split("/")[1]?.toUpperCase() || "PDF"} •{" "}
                    {Math.round((inspectSubmission.file_size || 1024) / 1024)} KB
                  </p>
                </div>
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Status</span>
                  <p className="text-xs font-bold text-emerald-700 mt-0.5 uppercase">
                    {inspectSubmission.extraction_status || "SUCCESS"}
                  </p>
                </div>
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Character Count</span>
                  <p className="text-xs font-bold text-slate-800 mt-0.5">
                    {editedText.length} chars
                  </p>
                </div>
              </div>

              {/* Extraction Warnings Banner if any */}
              {inspectSubmission.extraction_warnings && inspectSubmission.extraction_warnings.length > 0 && (
                <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-1">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-800">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <span>Extraction Warnings Detected:</span>
                  </div>
                  <ul className="text-xs text-amber-900 list-disc list-inside space-y-0.5 pl-1">
                    {inspectSubmission.extraction_warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Empty / Unreadable Document Guard */}
              {(!editedText || editedText.trim().length === 0) && (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2.5">
                  <FileWarning className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                  <div className="text-xs text-rose-900">
                    <p className="font-bold">Never Grade an Empty or Unreadable Document</p>
                    <p className="mt-0.5">
                      No selectable text was extracted. Enter or transcribe the student response below before initiating evaluation.
                    </p>
                  </div>
                </div>
              )}

              {/* Editable Extracted Text */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                    <Edit3 className="w-3.5 h-3.5 text-slate-500" />
                    <span>Extracted Answer Content (Editable)</span>
                  </label>
                  <span className="text-[11px] text-slate-400">
                    Faculty may correct transcription or formatting
                  </span>
                </div>

                <textarea
                  rows={14}
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  placeholder="Extracted student answer text appears here..."
                  className="w-full p-4 text-xs font-mono bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none leading-relaxed"
                />
              </div>

              {/* Correction Rationale */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700">
                  Correction Reason / Audit Note
                </label>
                <input
                  type="text"
                  value={editReason}
                  onChange={(e) => setEditReason(e.target.value)}
                  placeholder="e.g. Fixed OCR character confusion on algorithmic terms"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {/* Original Text Reference if edited */}
              {inspectSubmission.is_text_corrected && inspectSubmission.original_extracted_text && (
                <details className="text-xs border border-slate-200 rounded-xl p-3 bg-slate-50">
                  <summary className="font-semibold text-slate-700 cursor-pointer">
                    View Original Unedited Extraction
                  </summary>
                  <p className="mt-2 text-slate-600 font-mono text-[11px] whitespace-pre-wrap">
                    {inspectSubmission.original_extracted_text}
                  </p>
                </details>
              )}
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
              <span className="text-[11px] text-slate-400">
                Preserves revision history in PostgreSQL
              </span>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => setInspectSubmission(null)}
                  className="px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={handleSaveCorrectedText}
                  disabled={isSavingText}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{isSavingText ? "Saving Changes..." : "Save Corrected Text"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
