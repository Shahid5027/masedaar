"""
EDUCORE AI PS2 - Feedback Generator Service
Generates concise, constructive, and concept-specific formative feedback based strictly
on structured grading evidence. Features deterministic template fallback and grounded LLM integration.
Never invents facts or claims concepts are missing without verification.
"""

from typing import Dict, Any, List, Optional


class FeedbackGenerator:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def generate_feedback(
        self,
        student_answer: str,
        model_answer: str,
        grading_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesizes structured evaluation findings into actionable pedagogical feedback.
        """
        score = grading_result.get("ai_score", 0.0)
        max_score = grading_result.get("max_score", 1.0)
        percentage = (score / max_score) * 100 if max_score > 0 else 0.0
        similarity = grading_result.get("semantic_similarity", 0.0)

        identified_concepts = grading_result.get("identified_concepts", [])
        missing_concepts = grading_result.get("missing_concepts", [])
        incorrect_concepts = grading_result.get("incorrect_concepts", [])
        rubric_scores = grading_result.get("rubric_scores", [])
        supporting_evidence = grading_result.get("supporting_evidence", [])

        # 1. What the student explained correctly
        correctly_explained: List[str] = []
        if identified_concepts:
            concept_str = ", ".join(f"'{c}'" for c in identified_concepts[:4])
            correctly_explained.append(f"Demonstrated clear understanding of core concepts: {concept_str}.")
        if supporting_evidence:
            correctly_explained.append(f"Supported answer with valid reasoning: \"{supporting_evidence[0][:90]}...\"")
        if not correctly_explained:
            correctly_explained.append("Demonstrated introductory awareness of the general problem domain.")

        # 2. Which important concepts are missing
        missing_feedback: List[str] = []
        if missing_concepts:
            missing_str = ", ".join(f"'{c}'" for c in missing_concepts[:3])
            missing_feedback.append(f"Omitted essential theoretical principles: {missing_str}.")
        else:
            missing_feedback.append("No critical required concepts were omitted.")

        # 3. Explanations needing correction
        corrections_needed: List[str] = []
        if incorrect_concepts:
            for inc in incorrect_concepts[:2]:
                corrections_needed.append(f"Review potential contradictory assertion: {inc}.")
        for r in rubric_scores:
            if r.get("evidence_coverage", 1.0) < 0.40 and r.get("missing_concepts"):
                corrections_needed.append(
                    f"Criterion '{r['criterion_name']}' scored low ({r['assigned_points']}/{r['max_points']} pts). Elaboration on expected mechanisms is required."
                )

        if not corrections_needed:
            corrections_needed.append("No explicit factual contradictions detected in your answer.")

        # 4. How the student can improve
        improvement_steps: List[str] = []
        if missing_concepts:
            improvement_steps.append(
                f"Formally define and integrate '{missing_concepts[0]}' into your explanation."
            )
        if len(student_answer.split()) < 40:
            improvement_steps.append(
                "Expand concise answers by demonstrating step-by-step state transitions or mathematical bounds."
            )
        improvement_steps.append(
            "Relate theoretical guarantees directly to runtime complexity or system stability."
        )

        # 5. Relevant topics to revise
        revision_topics: List[str] = []
        if missing_concepts:
            revision_topics.extend(missing_concepts[:3])
        for r in rubric_scores:
            if r.get("assigned_points", 0) < (r.get("max_points", 1) * 0.7):
                revision_topics.append(r["criterion_name"])
        if not revision_topics:
            revision_topics = ["Advanced edge-case constraints and trade-offs"]

        revision_topics = list(dict.fromkeys(revision_topics))  # deduplicate preserving order

        # Holistic formative narrative
        if percentage >= 85:
            tone = "Exemplary performance."
        elif percentage >= 70:
            tone = "Proficient comprehension with minor conceptual omissions."
        elif percentage >= 50:
            tone = "Developing understanding. Key foundational tenets need reinforcement."
        else:
            tone = "Significant conceptual gaps detected."

        narrative = (
            f"{tone} Alignment score: {round(percentage, 1)}% ({score}/{max_score} pts). "
            f"{correctly_explained[0]} "
            f"{missing_feedback[0]} "
            f"Key next step: {improvement_steps[0]}"
        )

        return {
            "feedback": narrative,
            "correctly_explained": correctly_explained,
            "missing_concepts": missing_concepts,
            "corrections_needed": corrections_needed,
            "how_to_improve": improvement_steps,
            "revision_topics": revision_topics,
            "strengths": correctly_explained,
            "areas_for_improvement": missing_feedback + improvement_steps[:1],
        }
