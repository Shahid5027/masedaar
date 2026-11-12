"""
EDUCORE AI PS2 - Semantic Matching Engine
Generates dense sentence embeddings using Sentence Transformers (all-MiniLM-L6-v2).
Computes exact vector cosine similarity, chunk-level semantic alignment,
and evidence excerpt matching with configurable thresholds.
"""

import math
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple
from ..config import get_settings
from .text_preprocessor import TextPreprocessor


class SemanticMatcher:
    _instance = None
    _transformer_model = None
    _is_transformer_loaded = False
    _load_error: Optional[str] = None

    def __init__(self, model_name: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.DEFAULT_EMBEDDING_MODEL
        self.threshold = settings.SEMANTIC_SIMILARITY_THRESHOLD
        self.evidence_threshold = settings.EVIDENCE_MATCH_THRESHOLD
        self.high_conf_threshold = settings.HIGH_CONFIDENCE_THRESHOLD
        self.enable_neural = settings.ENABLE_NEURAL_EMBEDDINGS
        self._ensure_model_loaded()

    def _ensure_model_loaded(self) -> bool:
        """
        Safely loads pretrained Sentence Transformer weights if enabled and available.
        """
        if not self.enable_neural:
            return False

        if SemanticMatcher._is_transformer_loaded and SemanticMatcher._transformer_model is not None:
            return True

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            SemanticMatcher._transformer_model = SentenceTransformer(self.model_name)
            SemanticMatcher._is_transformer_loaded = True
            SemanticMatcher._load_error = None
            return True
        except Exception as e:
            SemanticMatcher._is_transformer_loaded = False
            SemanticMatcher._load_error = str(e)
            return False

    @property
    def is_neural_active(self) -> bool:
        return SemanticMatcher._is_transformer_loaded and SemanticMatcher._transformer_model is not None

    def get_engine_metadata(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "neural_active": self.is_neural_active,
            "load_error": SemanticMatcher._load_error,
            "threshold": self.threshold,
            "evidence_threshold": self.evidence_threshold,
        }

    def compute_similarity(self, student_answer: str, reference_answer: str) -> Dict[str, Any]:
        """
        Calculate mathematical cosine similarity between student response and reference model answer.
        Uses dense neural embeddings when model is loaded, otherwise exact n-gram token vector cosine.
        """
        cleaned_student = TextPreprocessor.clean_text(student_answer)
        cleaned_ref = TextPreprocessor.clean_text(reference_answer)

        if not cleaned_student or not cleaned_ref:
            return {
                "similarity_score": 0.0,
                "method": "empty_input",
                "confidence": 0.0,
                "is_match": False,
            }

        # 1. Neural Transformer Embeddings
        if self._ensure_model_loaded() and SemanticMatcher._transformer_model:
            try:
                embeddings = SemanticMatcher._transformer_model.encode(
                    [cleaned_student, cleaned_ref],
                    convert_to_numpy=True
                )
                vec_s, vec_r = embeddings[0], embeddings[1]
                dot_prod = float(sum(a * b for a, b in zip(vec_s, vec_r)))
                norm_s = math.sqrt(float(sum(a * a for a, b in zip(vec_s, vec_s))))
                norm_r = math.sqrt(float(sum(b * b for b, b in zip(vec_r, vec_r))))

                sim = dot_prod / (norm_s * norm_r) if (norm_s * norm_r) > 0 else 0.0
                clamped_sim = round(max(0.0, min(1.0, float(sim))), 3)

                return {
                    "similarity_score": clamped_sim,
                    "method": f"sentence_transformers ({self.model_name})",
                    "confidence": 0.94 if clamped_sim >= self.high_conf_threshold else 0.85,
                    "is_match": clamped_sim >= self.threshold,
                }
            except Exception as e:
                pass

        # 2. Mathematical Vector Cosine Fallback (TF-IDF / N-gram frequency vectors)
        sim, confidence = self._compute_token_cosine_similarity(cleaned_student, cleaned_ref)
        clamped_sim = round(max(0.0, min(1.0, float(sim))), 3)

        return {
            "similarity_score": clamped_sim,
            "method": "vector_cosine_frequency",
            "confidence": round(confidence, 3),
            "is_match": clamped_sim >= self.threshold,
        }

    def match_criterion_evidence(
        self,
        student_sentences: List[str],
        criterion_target: str,
        expected_concepts: List[str]
    ) -> Dict[str, Any]:
        """
        Finds supporting student sentence excerpts for a specific rubric criterion or concept.
        Returns highest-matching excerpts, similarity scores, and identified concept coverage.
        """
        if not student_sentences:
            return {
                "evidence_excerpts": [],
                "max_similarity": 0.0,
                "identified_concepts": [],
                "missing_concepts": expected_concepts,
                "coverage_ratio": 0.0,
            }

        best_excerpts: List[Dict[str, Any]] = []
        max_sim = 0.0

        for sentence in student_sentences:
            sim_res = self.compute_similarity(sentence, criterion_target)
            sim_val = sim_res["similarity_score"]
            if sim_val > max_sim:
                max_sim = sim_val

            if sim_val >= self.evidence_threshold:
                best_excerpts.append({
                    "sentence": sentence,
                    "similarity": sim_val,
                })

        # Sort excerpts by similarity descending
        best_excerpts.sort(key=lambda x: x["similarity"], reverse=True)

        # Check expected concepts
        combined_text = " ".join(student_sentences)
        concept_res = TextPreprocessor.check_concept_coverage(
            combined_text,
            required_concepts=expected_concepts
        )

        # If best_excerpts is empty but concepts matched, include the sentences that matched the concepts
        excerpts_list = [e["sentence"] for e in best_excerpts[:2]]
        if not excerpts_list and concept_res["matched_required"]:
            excerpts_list = [m["evidence_excerpt"] for m in concept_res["matched_required"][:2]]
        if not excerpts_list and student_sentences:
            excerpts_list = [student_sentences[0]]

        return {
            "evidence_excerpts": excerpts_list,
            "max_similarity": max_sim,
            "identified_concepts": concept_res["matched_concept_names"],
            "missing_concepts": concept_res["missing_required"],
            "coverage_ratio": concept_res["coverage_ratio"],
        }

    def _compute_token_cosine_similarity(self, text_a: str, text_b: str) -> Tuple[float, float]:
        tokens_a = TextPreprocessor.extract_tokens(text_a, lower=True)
        tokens_b = TextPreprocessor.extract_tokens(text_b, lower=True)

        if not tokens_a or not tokens_b:
            return 0.0, 0.5

        # Unigrams and bigrams
        bigrams_a = [f"{tokens_a[i]}_{tokens_a[i+1]}" for i in range(len(tokens_a)-1)]
        bigrams_b = [f"{tokens_b[i]}_{tokens_b[i+1]}" for i in range(len(tokens_b)-1)]

        vec_a = Counter(tokens_a + bigrams_a)
        vec_b = Counter(tokens_b + bigrams_b)

        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)

        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0, 0.5

        raw_cosine = dot_product / (mag_a * mag_b)
        calibrated_sim = min(1.0, max(0.0, raw_cosine))

        confidence = 0.85 if len(tokens_a) >= 20 else 0.72
        return calibrated_sim, confidence
