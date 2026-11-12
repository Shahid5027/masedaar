"""
EDUCORE AI PS2 - Advanced Text Preprocessor Service
Preserves technical terms, mathematical expressions, numbers, units, and negations.
Segments subjective answers into semantic sentence chunks for evidence alignment.
"""

import re
from typing import List, Dict, Set, Any, Tuple


class TextPreprocessor:
    # Common technical contractions and negation markers
    NEGATION_WORDS = {
        "not", "no", "never", "none", "neither", "nor", "cannot", "can't",
        "without", "lacks", "lacking", "fails", "failed", "failing",
        "doesn't", "don't", "didn't", "won't", "isnt", "isn't", "aren't"
    }

    # Technical abbreviations to avoid false sentence splits
    ABBREVIATIONS = (
        r"\b(?:e\.g\.|i\.e\.|etc\.|fig\.|vs\.|prof\.|dr\.|approx\.|dept\.|no\.)"
    )

    @classmethod
    def clean_text(cls, raw_text: str) -> str:
        """
        Normalize whitespace while strictly preserving technical terms, equations, and punctuation.
        """
        if not raw_text:
            return ""

        # Normalize carriage returns
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Normalize non-breaking spaces and special unicode quotes
        text = text.replace("\u00a0", " ").replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')

        # Collapse horizontal whitespace
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse excessive line breaks beyond 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def split_into_sentences(cls, text: str) -> List[str]:
        """
        Segment text into coherent sentences/chunks for evidence mapping.
        Safely protects abbreviations, numbers, and mathematical expressions like O(log n).
        """
        cleaned = cls.clean_text(text)
        if not cleaned:
            return []

        # Mask dots in common abbreviations
        masked = re.sub(
            cls.ABBREVIATIONS,
            lambda m: m.group(0).replace(".", "@@DOT@@"),
            cleaned,
            flags=re.IGNORECASE
        )

        # Mask dots in decimal numbers (e.g., 2.5, 3.14)
        masked = re.sub(r"(\d+)\.(\d+)", r"\1@@DOT@@\2", masked)

        # Split on sentence boundaries: period/exclamation/question followed by space or newline, or double newline
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n\n+", masked)

        sentences = []
        for s in raw_sentences:
            unmasked = s.replace("@@DOT@@", ".").strip()
            if unmasked and len(unmasked) > 2:
                sentences.append(unmasked)

        return sentences

    @classmethod
    def extract_tokens(cls, text: str, lower: bool = True) -> List[str]:
        """
        Extract tokens while preserving technical compounds, notation, and alphanumeric terms.
        e.g., O(log n), 2*log2(n+1), BusRd, BusRdX, Present=1, bh(x)
        """
        if lower:
            text = text.lower()
        # Captures technical words, identifiers with underscores/hyphens/dots, and math terms
        return re.findall(r"\b[a-zA-Z0-9_\-\./*^=<>]+(?:\([a-zA-Z0-9_\-\.\s]+\))?\b", text)

    @classmethod
    def detect_negations(cls, sentence: str) -> List[Dict[str, Any]]:
        """
        Detects negation contexts within a sentence to prevent misidentifying inverted claims as correct.
        e.g., 'Red nodes cannot have red children' vs 'Red nodes can have red children'.
        """
        tokens = cls.extract_tokens(sentence, lower=True)
        negation_scopes = []

        for idx, token in enumerate(tokens):
            if token in cls.NEGATION_WORDS:
                # Capture scope window of next 4 tokens
                window = tokens[idx + 1: idx + 5]
                negation_scopes.append({
                    "negation_word": token,
                    "scope_tokens": window,
                    "full_sentence": sentence
                })

        return negation_scopes

    @classmethod
    def check_concept_coverage(
        cls,
        student_text: str,
        required_concepts: List[str],
        optional_concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates coverage of required and optional concepts within student answer.
        Returns matched concepts, missing concepts, and coverage ratio.
        """
        cleaned_text = student_text.lower()
        sentences = cls.split_into_sentences(student_text)
        sentences_lower = [s.lower() for s in sentences]

        matched_required: List[Dict[str, Any]] = []
        missing_required: List[str] = []

        for concept in required_concepts:
            concept_clean = concept.strip()
            if not concept_clean:
                continue
            concept_lower = concept_clean.lower()
            concept_tokens = [t for t in cls.extract_tokens(concept_lower) if len(t) > 1]

            matched_sentence = None
            if concept_lower in cleaned_text:
                for s in sentences:
                    if concept_lower in s.lower():
                        matched_sentence = s
                        break
                if not matched_sentence and sentences:
                    matched_sentence = sentences[0]
            else:
                for idx, s_lower in enumerate(sentences_lower):
                    s_tokens = cls.extract_tokens(s_lower)
                    if concept_tokens and all(any(c_tok in st or st in c_tok for st in s_tokens) for c_tok in concept_tokens):
                        matched_sentence = sentences[idx]
                        break

            if matched_sentence:
                matched_required.append({
                    "concept": concept_clean,
                    "evidence_excerpt": matched_sentence,
                })
            else:
                missing_required.append(concept_clean)

        matched_optional: List[str] = []
        if optional_concepts:
            for opt in optional_concepts:
                opt_clean = opt.strip()
                if not opt_clean:
                    continue
                if opt_clean.lower() in cleaned_text:
                    matched_optional.append(opt_clean)

        total_req = len(required_concepts)
        coverage_ratio = len(matched_required) / total_req if total_req > 0 else 1.0

        return {
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_optional": matched_optional,
            "coverage_ratio": round(coverage_ratio, 3),
            "matched_concept_names": [m["concept"] for m in matched_required],
        }
