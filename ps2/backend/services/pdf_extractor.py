"""
EDUCORE AI PS2 - Document Extraction Service
Extracts text from PDF and TXT documents.
Uses PyMuPDF (fitz) as primary PDF extraction engine with pypdf fallback.
Provides paragraph preservation, empty document detection, and unreadable document handling.
"""

import io
import re
from typing import Dict, Any, List, Optional


class DocumentExtractorService:
    @staticmethod
    def extract_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """
        Extract text from digital PDF using PyMuPDF (fitz) with pypdf fallback.
        Preserves paragraphs, checks for empty pages, and flags unreadable content.
        """
        if not file_bytes or len(file_bytes) == 0:
            return {
                "success": False,
                "status": "empty",
                "extracted_text": "",
                "page_count": 0,
                "word_count": 0,
                "character_count": 0,
                "warnings": ["The uploaded PDF file is 0 bytes."],
                "engine": "none",
                "error": "Empty file received"
            }

        extracted_text = ""
        page_count = 0
        warnings: List[str] = []
        engine_used = "PyMuPDF"

        # 1. Primary Engine: PyMuPDF
        try:
            import pymupdf as fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            page_texts = []

            for page_idx in range(page_count):
                page = doc[page_idx]
                text = page.get_text("text") or ""
                # Preserve paragraphs while stripping line-edge whitespace
                cleaned_page = "\n".join(line.rstrip() for line in text.splitlines())
                page_texts.append(cleaned_page.strip())

            doc.close()
            extracted_text = "\n\n".join(p for p in page_texts if p).strip()

        except Exception as fitz_err:
            warnings.append(f"PyMuPDF parser warning: {str(fitz_err)}. Attempting pypdf fallback.")
            engine_used = "pypdf"

            # 2. Fallback Engine: pypdf
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
                page_texts = []
                for p in reader.pages:
                    txt = p.extract_text() or ""
                    page_texts.append(txt.strip())
                extracted_text = "\n\n".join(p for p in page_texts if p).strip()
            except Exception as pypdf_err:
                return {
                    "success": False,
                    "status": "unreadable",
                    "extracted_text": "",
                    "page_count": 0,
                    "word_count": 0,
                    "character_count": 0,
                    "warnings": warnings + [f"Document could not be parsed: {str(pypdf_err)}"],
                    "engine": "failed",
                    "error": f"Unreadable PDF document: {str(pypdf_err)}"
                }

        # 3. Post-Extraction Quality Evaluation
        char_count = len(extracted_text)
        words = re.findall(r"\b\w+\b", extracted_text)
        word_count = len(words)

        if char_count == 0:
            warnings.append("Document appears empty or contains only non-selectable scanned images (requires OCR).")
            return {
                "success": False,
                "status": "empty",
                "extracted_text": "",
                "page_count": page_count,
                "word_count": 0,
                "character_count": 0,
                "warnings": warnings,
                "engine": engine_used,
                "error": "No selectable text found in PDF document"
            }

        if word_count < 15:
            warnings.append(f"Very short submission detected ({word_count} words). Verify content validity.")
            status = "warning"
        else:
            status = "success"

        return {
            "success": True,
            "status": status,
            "extracted_text": extracted_text,
            "page_count": page_count,
            "word_count": word_count,
            "character_count": char_count,
            "warnings": warnings,
            "engine": engine_used,
            "error": None
        }

    @staticmethod
    def extract_from_txt(file_bytes: bytes, filename: str = "document.txt") -> Dict[str, Any]:
        """
        Extract and normalize text from TXT files directly with robust encoding handling.
        """
        if not file_bytes or len(file_bytes) == 0:
            return {
                "success": False,
                "status": "empty",
                "extracted_text": "",
                "page_count": 1,
                "word_count": 0,
                "character_count": 0,
                "warnings": ["The uploaded TXT file is empty."],
                "engine": "direct_text",
                "error": "Empty text file"
            }

        raw_text = ""
        warnings: List[str] = []

        # Try UTF-8 first, fallback to Latin-1
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = file_bytes.decode("latin-1")
                warnings.append("Encoded in Latin-1 charset rather than standard UTF-8.")
            except Exception as e:
                return {
                    "success": False,
                    "status": "unreadable",
                    "extracted_text": "",
                    "page_count": 1,
                    "word_count": 0,
                    "character_count": 0,
                    "warnings": [f"Text decoding failed: {str(e)}"],
                    "engine": "direct_text",
                    "error": "Unreadable text encoding"
                }

        # Normalize line endings while preserving paragraphs
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove trailing whitespace from each line
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
        # Collapse 4+ newlines to 2 newlines (paragraph boundary)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()

        char_count = len(normalized)
        words = re.findall(r"\b\w+\b", normalized)
        word_count = len(words)

        if char_count == 0:
            warnings.append("TXT file contains only whitespace characters.")
            return {
                "success": False,
                "status": "empty",
                "extracted_text": "",
                "page_count": 1,
                "word_count": 0,
                "character_count": 0,
                "warnings": warnings,
                "engine": "direct_text",
                "error": "Empty text file"
            }

        if word_count < 15:
            warnings.append(f"Short text submission ({word_count} words).")
            status = "warning"
        else:
            status = "success"

        return {
            "success": True,
            "status": status,
            "extracted_text": normalized,
            "page_count": 1,
            "word_count": word_count,
            "character_count": char_count,
            "warnings": warnings,
            "engine": "direct_text",
            "error": None
        }

    @classmethod
    def extract_document(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Unified document extraction router dispatching to PDF or TXT handlers.
        Rejects unsupported formats with an explicit validation error.
        """
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            return cls.extract_from_pdf(file_bytes, filename)
        elif lower_name.endswith(".txt"):
            return cls.extract_from_txt(file_bytes, filename)
        else:
            ext = lower_name.split(".")[-1] if "." in lower_name else "unknown"
            return {
                "success": False,
                "status": "error",
                "extracted_text": "",
                "page_count": 0,
                "word_count": 0,
                "character_count": 0,
                "warnings": [f"Unsupported file format '.{ext}'."],
                "engine": "none",
                "error": f"Unsupported file extension: '.{ext}'. Supported formats are PDF (.pdf) and Plain Text (.txt)."
            }


# Backward-compatible alias
PDFExtractorService = DocumentExtractorService
