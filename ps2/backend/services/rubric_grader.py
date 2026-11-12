"""
EDUCORE AI PS2 - Rubric Grader Engine
Implements explainable criterion-level subjective grading using the transparent heuristic:
Criterion Score = Criterion Max Marks * Evidence Coverage * Correctness Factor
Extracts supporting student answer excerpts, identifies missing & contradictory concepts,
and clamps scores between 0 and maximum marks.
"""

from typing import Dict, Any, List, Optional
from .semantic_matcher import SemanticMatcher
from .text_preprocessor import TextPreprocessor


class RubricGrader:
    def __init__(self, semantic_matcher: Optional[SemanticMatcher] = None):
        self.matcher = semantic_matcher or SemanticMatcher()

    def grade_answer(
        self,
        student_answer: str,
        model_answer: str,
        key_concepts: List[str],
        rubrics: List[Dict[str, Any]],
        max_marks: float,
        required_concepts: Optional[List[str]] = None,
        optional_concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes explainable rubric evaluation for a subjective student answer.
        Never allows semantic similarity alone to determine score.
        """
        cleaned_student = TextPreprocessor.clean_text(student_answer)
        cleaned_model = TextPreprocessor.clean_text(model_answer)

        # 0. Empty submission check
        if not cleaned_student or len(cleaned_student.strip()) == 0:
            return {
                "ai_score": 0.0,
                "suggested_marks": 0.0,
                "max_score": max_marks,
                "confidence_score": 1.0,
                "semantic_similarity": 0.0,
                "rubric_scores": [],
                "identified_concepts": [],
                "missing_concepts": (required_concepts or key_concepts),
                "incorrect_concepts": [],
                "supporting_evidence": [],
                "warnings": ["Submission is empty. Zero marks allocated."],
                "grading_method": "empty_submission_guard",
            }

        # 1. Segment student answer into sentences for excerpt extraction
        student_sentences = TextPreprocessor.split_into_sentences(cleaned_student)
        model_sentences = TextPreprocessor.split_into_sentences(cleaned_model)

        # 2. Overall semantic alignment
        overall_sim_res = self.matcher.compute_similarity(cleaned_student, cleaned_model)
        overall_similarity = overall_sim_res["similarity_score"]
        grading_engine_method = overall_sim_res["method"]

        # 3. Overall Concept Coverage
        all_required = list(dict.fromkeys((required_concepts or []) + (key_concepts or [])))
        overall_concept_res = TextPreprocessor.check_concept_coverage(
            cleaned_student,
            required_concepts=all_required,
            optional_concepts=optional_concepts
        )

        all_identified_concepts = overall_concept_res["matched_concept_names"]
        all_missing_concepts = overall_concept_res["missing_required"]
        all_supporting_evidence: List[str] = []
        incorrect_concepts: List[str] = []
        warnings: List[str] = []

        # 4. Check for contradictory claims or negation confusions
        student_negations = TextPreprocessor.detect_negations(cleaned_student)
        model_negations = TextPreprocessor.detect_negations(cleaned_model)

        if student_negations:
            for neg in student_negations:
                scope_str = " ".join(neg["scope_tokens"])
                # Check if model answer affirms this scope without negation
                if scope_str and any(scope_str in ms.lower() for ms in model_sentences):
                    model_has_neg = any(
                        nw in ms.lower()
                        for ms in model_sentences
                        if scope_str in ms.lower()
                        for nw in TextPreprocessor.NEGATION_WORDS
                    )
                    if not model_has_neg:
                        contradiction_msg = f"Potential contradiction: '{neg['negation_word']} {scope_str}'"
                        if contradiction_msg not in incorrect_concepts:
                            incorrect_concepts.append(contradiction_msg)

        # 5. Criterion-Level Grading
        criterion_scores = []
        total_awarded = 0.0

        if not rubrics:
            rubrics = [{
                "criterion_name": "General Conceptual Mastery",
                "description": model_answer[:120] + "...",
                "max_points": max_marks,
                "weight": 1.0,
                "levels": []
            }]

        for idx, crit in enumerate(rubrics):
            c_name = crit.get("criterion_name", "Criterion")
            c_desc = crit.get("description", "")
            c_max = float(crit.get("max_points", max_marks / len(rubrics)))

            crit_target = f"{c_name}: {c_desc}"
            # Associate concepts with this criterion based on keyword overlap or position
            c_name_lower = c_name.lower()
            c_desc_lower = c_desc.lower()
            crit_expected = [
                c for c in all_required
                if any(w in c_name_lower or w in c_desc_lower for w in c.lower().split() if len(w) > 3)
            ]
            if not crit_expected:
                # If no direct keyword match, distribute concepts across criteria
                chunk_size = max(1, len(all_required) // len(rubrics))
                crit_expected = all_required[idx * chunk_size : (idx + 1) * chunk_size] or all_required[:1]

            # Match evidence excerpts from student sentences
            evidence_res = self.matcher.match_criterion_evidence(
                student_sentences=student_sentences,
                criterion_target=crit_target,
                expected_concepts=crit_expected
            )

            matched_excerpts = evidence_res["evidence_excerpts"]
            all_supporting_evidence.extend(matched_excerpts)
            c_identified = evidence_res["identified_concepts"]
            c_missing = evidence_res["missing_concepts"]
            c_sim = evidence_res["max_similarity"]

            # Calculate Evidence Coverage (0.0 to 1.0) strictly based on concept coverage & evidence presence
            if crit_expected:
                concept_coverage_ratio = len(c_identified) / len(crit_expected)
                evidence_coverage = round(min(1.0, max(0.0, concept_coverage_ratio)), 3)
            else:
                evidence_coverage = round(min(1.0, max(0.0, c_sim / 0.55)), 3)

            # Calculate Correctness Factor (0.0 to 1.0)
            if evidence_coverage == 0.0:
                correctness_factor = 0.0
            else:
                correctness = 0.98
                if incorrect_concepts:
                    correctness -= 0.30
                if overall_similarity < 0.25:
                    correctness -= 0.15
                correctness_factor = round(max(0.10, min(1.0, correctness)), 3)

            # TRANSPARENT HEURISTIC:
            # Criterion score = Criterion max marks * Evidence coverage * Correctness factor
            raw_score = c_max * evidence_coverage * correctness_factor
            criterion_score = round(max(0.0, min(c_max, raw_score)), 2)
            total_awarded += criterion_score

            status_desc = "Mastery demonstrated" if evidence_coverage >= 0.75 else ("Partial credit awarded" if evidence_coverage >= 0.35 else "Insufficient evidence")
            comment = (
                f"{status_desc} ({round(evidence_coverage*100)}% coverage, {round(correctness_factor*100)}% correctness). "
                f"Concepts identified: {len(c_identified)}/{len(crit_expected)}."
            )

            criterion_scores.append({
                "criterion_name": c_name,
                "assigned_points": criterion_score,
                "max_points": c_max,
                "evidence_coverage": evidence_coverage,
                "correctness_factor": correctness_factor,
                "supporting_excerpts": matched_excerpts[:2],
                "identified_concepts": c_identified,
                "missing_concepts": c_missing,
                "comment": comment,
            })

        # Cap total awarded at max_marks
        final_suggested_marks = round(max(0.0, min(max_marks, total_awarded)), 2)

        if len(student_sentences) < 2:
            warnings.append("Answer is brief; evidence extraction confidence is moderate.")
            confidence = 0.75
        elif overall_similarity >= self.matcher.high_conf_threshold:
            confidence = 0.94
        else:
            confidence = 0.86

        return {
            "ai_score": final_suggested_marks,
            "suggested_marks": final_suggested_marks,
            "max_score": max_marks,
            "confidence_score": confidence,
            "semantic_similarity": overall_similarity,
            "rubric_scores": criterion_scores,
            "identified_concepts": list(set(all_identified_concepts)),
            "missing_concepts": list(set(all_missing_concepts)),
            "incorrect_concepts": incorrect_concepts,
            "supporting_evidence": list(set(all_supporting_evidence))[:4],
            "warnings": warnings,
            "grading_method": f"{grading_engine_method} + transparent_heuristic_rubric_v3",
        }
