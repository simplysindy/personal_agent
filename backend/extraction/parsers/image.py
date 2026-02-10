"""Image parser with OCR and Vision LLM support."""

import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import httpx

from PIL import Image

from backend.config import settings


@dataclass
class ParsedImage:
    """Result of parsing an image file."""

    file_path: str
    ocr_text: str = ""
    vision_description: str = ""
    width: int = 0
    height: int = 0
    format: str = ""


class ImageParser:
    """Parser for images with OCR and Vision LLM capabilities."""

    def __init__(
        self,
        use_ocr: bool = True,
        use_vision_llm: bool = True,
        openrouter_api_key: str = None,
        vision_model: str = None,
    ):
        self.use_ocr = use_ocr
        self.use_vision_llm = use_vision_llm
        self.api_key = openrouter_api_key or settings.openrouter_api_key
        self.vision_model = vision_model or settings.openrouter_vision_model
        self._tesseract_available = None

    def _check_tesseract(self) -> bool:
        """Check if tesseract is available."""
        if self._tesseract_available is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
            except Exception:
                self._tesseract_available = False
        return self._tesseract_available

    def parse_file(self, file_path: Path) -> ParsedImage:
        """Parse an image file with OCR and/or Vision LLM."""
        # Get image info
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                img_format = img.format or file_path.suffix[1:].upper()
        except Exception as e:
            raise ValueError(f"Could not open image: {file_path} - {e}")

        result = ParsedImage(
            file_path=str(file_path),
            width=width,
            height=height,
            format=img_format,
        )

        # OCR extraction
        if self.use_ocr and self._check_tesseract():
            result.ocr_text = self._extract_ocr(file_path)

        # Vision LLM description
        if self.use_vision_llm and self.api_key:
            result.vision_description = self._get_vision_description(file_path)

        return result

    def _extract_ocr(self, file_path: Path) -> str:
        """Extract text from image using OCR."""
        try:
            import pytesseract
            from PIL import Image

            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                text = pytesseract.image_to_string(img)
                return text.strip()
        except Exception as e:
            return f"[OCR failed: {e}]"

    def _get_vision_description(self, file_path: Path) -> str:
        """Get description from Vision LLM via OpenRouter."""
        try:
            # Encode image to base64
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Determine media type
            suffix = file_path.suffix.lower()
            media_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_types.get(suffix, "image/png")

            # Call OpenRouter Vision API
            response = httpx.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Personal Agent",
                },
                json={
                    "model": self.vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Describe this image in detail. If it's a diagram, explain its structure and meaning. If it contains text, include the key text content. Focus on what information this image conveys.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 500,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[Vision API error: {response.status_code}]"

        except Exception as e:
            return f"[Vision description failed: {e}]"

    def parse_bytes(
        self,
        image_bytes: bytes,
        image_format: str = "png",
        source_info: str = "",
    ) -> ParsedImage:
        """Parse image from bytes (for embedded images in PDFs, etc.)."""
        import io

        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0

        result = ParsedImage(
            file_path=source_info,
            width=width,
            height=height,
            format=image_format,
        )

        # OCR from bytes
        if self.use_ocr and self._check_tesseract():
            try:
                import pytesseract
                with Image.open(io.BytesIO(image_bytes)) as img:
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    result.ocr_text = pytesseract.image_to_string(img).strip()
            except Exception:
                pass

        # Vision LLM from bytes
        if self.use_vision_llm and self.api_key:
            result.vision_description = self._get_vision_description_from_bytes(
                image_bytes, image_format
            )

        return result

    def _get_vision_description_from_bytes(
        self, image_bytes: bytes, image_format: str
    ) -> str:
        """Get Vision LLM description from image bytes."""
        try:
            image_data = base64.b64encode(image_bytes).decode("utf-8")

            format_to_media = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
            }
            media_type = format_to_media.get(image_format.lower(), "image/png")

            response = httpx.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Personal Agent",
                },
                json={
                    "model": self.vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Describe this image briefly. What does it show?",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 200,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            return ""

        except Exception:
            return ""
