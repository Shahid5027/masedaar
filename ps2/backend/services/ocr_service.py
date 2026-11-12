"""
EDUCORE AI PS2 - OCR Service Interface
Provides modular interface for Tesseract and PaddleOCR engines for scanned documents.
Prioritizes digital PDF/TXT extraction while providing future-proof OCR extensibility.
"""

from typing import Dict, Any, Optional, List


class OCRService:
    def __init__(self, engine_preference: str = "auto", tesseract_cmd: Optional[str] = None):
        self.engine_preference = engine_preference
        self.tesseract_cmd = tesseract_cmd
        self._tesseract_available = False
        self._paddle_available = False
        self._check_engines()

    def _check_engines(self) -> None:
        # Check Tesseract
        try:
            import pytesseract  # type: ignore
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            self._tesseract_available = True
        except ImportError:
            self._tesseract_available = False

        # Check PaddleOCR
        try:
            import paddleocr  # type: ignore
            self._paddle_available = True
        except ImportError:
            self._paddle_available = False

    def is_available(self) -> bool:
        return self._tesseract_available or self._paddle_available

    def get_engine_status(self) -> Dict[str, Any]:
        return {
            "is_available": self.is_available(),
            "tesseract_available": self._tesseract_available,
            "paddle_available": self._paddle_available,
            "active_engine": "paddleocr" if self._paddle_available else ("tesseract" if self._tesseract_available else "none"),
            "notice": "Digital PDF/TXT is primary. OCR activates for scanned document fallbacks."
        }

    def process_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Extract text from image byte stream using active OCR engine with fallback.
        """
        if not self.is_available():
            return {
                "success": False,
                "text": "",
                "confidence": 0.0,
                "engine": "none",
                "warnings": ["OCR engines (PaddleOCR / Tesseract) are not initialized."],
                "error": "OCR engine unavailable. Digital PDF/TXT text extraction should be utilized."
            }

        # If PaddleOCR is available
        if self._paddle_available and self.engine_preference in ("auto", "paddle"):
            try:
                from paddleocr import PaddleOCR  # type: ignore
                ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                result = ocr.ocr(image_bytes, cls=True)
                lines = []
                confidences = []
                for line in result:
                    for word_info in line:
                        text = word_info[1][0]
                        conf = word_info[1][1]
                        lines.append(text)
                        confidences.append(conf)
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.8
                return {
                    "success": True,
                    "text": "\n".join(lines).strip(),
                    "confidence": round(avg_conf, 3),
                    "engine": "PaddleOCR",
                    "warnings": [],
                    "error": None
                }
            except Exception as e:
                pass

        # If Tesseract is available
        if self._tesseract_available:
            try:
                import io
                from PIL import Image  # type: ignore
                import pytesseract  # type: ignore

                image = Image.open(io.BytesIO(image_bytes))
                text = pytesseract.image_to_string(image)
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
                avg_conf = (sum(confidences) / len(confidences)) / 100.0 if confidences else 0.85

                return {
                    "success": True,
                    "text": text.strip(),
                    "confidence": round(avg_conf, 3),
                    "engine": "Tesseract",
                    "warnings": [],
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "confidence": 0.0,
                    "engine": "Tesseract",
                    "warnings": [f"Tesseract OCR failed: {str(e)}"],
                    "error": str(e)
                }

        return {
            "success": False,
            "text": "",
            "confidence": 0.0,
            "engine": "none",
            "warnings": [],
            "error": "No OCR engine successfully processed the image."
        }
