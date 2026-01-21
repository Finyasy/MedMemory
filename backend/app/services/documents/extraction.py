"""Document text extraction services (PDF, Images, etc.)."""

import asyncio
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from app.config import settings


@dataclass
class ExtractionResult:
    """Result of document text extraction."""
    
    text: str
    page_count: int
    confidence: Optional[float] = None
    language: Optional[str] = None
    metadata: Optional[dict] = None
    direct_text: Optional[str] = None
    ocr_text: Optional[str] = None
    used_ocr: bool = False
    
    @property
    def is_empty(self) -> bool:
        return not self.text or len(self.text.strip()) == 0


class DocumentExtractor(ABC):
    """Base class for document text extraction."""
    
    @abstractmethod
    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from a document.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            ExtractionResult with extracted text and metadata
        """
        pass
    
    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type."""
        pass


class PDFExtractor(DocumentExtractor):
    """Extract text from PDF documents using PyMuPDF.
    
    Supports:
    - Text-based PDFs (direct text extraction)
    - Image-based PDFs (OCR fallback)
    - Mixed PDFs (text + embedded images)
    """
    
    SUPPORTED_TYPES = ["application/pdf"]
    
    def __init__(self, ocr_fallback: bool = True):
        """Initialize PDF extractor.
        
        Args:
            ocr_fallback: Whether to use OCR for image-based pages
        """
        self.ocr_fallback = ocr_fallback
    
    def supports(self, mime_type: str) -> bool:
        return mime_type in self.SUPPORTED_TYPES
    
    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from PDF."""
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: str) -> ExtractionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        doc = fitz.open(file_path)

        try:
            pages_text = []
            direct_parts = []
            ocr_parts = []
            ocr_confidences = []
            used_ocr = False
            ocr_language = None
            page_count = len(doc)

            for page_num in range(page_count):
                page = doc[page_num]

                # Try direct text extraction first
                text = page.get_text("text")

                # If no text and OCR fallback enabled, try OCR
                if not text.strip() and self.ocr_fallback:
                    ocr_result = self._ocr_page_sync(page)
                    text = ocr_result.text
                    if text.strip():
                        used_ocr = True
                        ocr_confidences.append(ocr_result.confidence or 0.0)
                        ocr_language = ocr_result.language or ocr_language
                        ocr_parts.append(f"--- Page {page_num + 1} ---\n{text}")
                elif text.strip():
                    direct_parts.append(f"--- Page {page_num + 1} ---\n{text}")

                if text.strip():
                    pages_text.append(f"--- Page {page_num + 1} ---\n{text}")

            # Extract metadata
            metadata = self._extract_metadata(doc)

            full_text = "\n\n".join(pages_text)
            direct_text = "\n\n".join(direct_parts) if direct_parts else None
            ocr_text = "\n\n".join(ocr_parts) if ocr_parts else None
            avg_confidence = (
                sum(ocr_confidences) / len(ocr_confidences)
                if ocr_confidences
                else None
            )

            return ExtractionResult(
                text=full_text,
                page_count=page_count,
                confidence=avg_confidence,
                language=ocr_language,
                metadata=metadata,
                direct_text=direct_text,
                ocr_text=ocr_text,
                used_ocr=used_ocr,
            )

        finally:
            doc.close()
    
    def _ocr_page_sync(self, page: fitz.Page) -> ExtractionResult:
        """OCR a PDF page by rendering it as an image.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            ExtractionResult with text from OCR
        """
        try:
            # Render page to image
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            
            # Use ImageExtractor for OCR
            image_extractor = ImageExtractor()
            result = image_extractor.extract_from_bytes_sync(img_bytes, "image/png")
            
            return result
        
        except Exception:
            return ExtractionResult(
                text="",
                page_count=1,
                confidence=0.0,
                language="eng",
                used_ocr=True,
            )
    
    def _extract_metadata(self, doc: fitz.Document) -> dict:
        """Extract PDF metadata."""
        metadata = doc.metadata or {}
        
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": metadata.get("creationDate", ""),
            "modification_date": metadata.get("modDate", ""),
        }
    
    async def extract_page(self, file_path: str, page_number: int) -> str:
        """Extract text from a specific page.
        
        Args:
            file_path: Path to the PDF file
            page_number: Page number (1-indexed)
            
        Returns:
            Text from the specified page
        """
        return await asyncio.to_thread(self._extract_page_sync, file_path, page_number)

    def _extract_page_sync(self, file_path: str, page_number: int) -> str:
        doc = fitz.open(file_path)
        try:
            if page_number < 1 or page_number > len(doc):
                raise ValueError(f"Invalid page number: {page_number}")

            page = doc[page_number - 1]
            text = page.get_text("text")

            if not text.strip() and self.ocr_fallback:
                text = self._ocr_page_sync(page).text

            return text
        finally:
            doc.close()


class ImageExtractor(DocumentExtractor):
    """Extract text from images using OCR.
    
    Supports:
    - PNG, JPEG, TIFF images
    - Scanned documents
    - Medical imaging text overlays
    """
    
    SUPPORTED_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
    ]
    
    def __init__(self, language: str = "eng"):
        """Initialize image extractor.
        
        Args:
            language: Tesseract language code (default: English)
        """
        self.language = language
        self._tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    def supports(self, mime_type: str) -> bool:
        return mime_type in self.SUPPORTED_TYPES
    
    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from image using OCR."""
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: str) -> ExtractionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Read image
        with open(file_path, "rb") as f:
            img_bytes = f.read()

        # Detect MIME type from extension
        ext = path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        mime_type = mime_map.get(ext, "image/png")

        return self.extract_from_bytes_sync(img_bytes, mime_type)
    
    async def extract_from_bytes(
        self,
        img_bytes: bytes,
        mime_type: str,
    ) -> ExtractionResult:
        """Extract text from image bytes."""
        return await asyncio.to_thread(self.extract_from_bytes_sync, img_bytes, mime_type)

    def extract_from_bytes_sync(
        self,
        img_bytes: bytes,
        _mime_type: str,
    ) -> ExtractionResult:
        # Load image with PIL
        image = Image.open(io.BytesIO(img_bytes))

        # Preprocess image for better OCR
        image = self._preprocess_image(image)

        # Perform OCR
        if self._tesseract_available:
            text, confidence = self._ocr_with_tesseract_sync(image)
        else:
            # Fallback: basic text detection (limited)
            text = ""
            confidence = 0.0

        return ExtractionResult(
            text=text,
            page_count=1,
            confidence=confidence,
            language=self.language,
            direct_text=None,
            ocr_text=text,
            used_ocr=True,
        )
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results.
        
        Args:
            image: PIL Image
            
        Returns:
            Preprocessed image
        """
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Resize if too small (improves OCR accuracy)
        min_dimension = 1000
        if min(image.size) < min_dimension:
            scale = min_dimension / min(image.size)
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to grayscale/binarize for OCR
        if settings.ocr_preprocess_opencv:
            try:
                import cv2
                import numpy as np
                img_array = np.array(image)
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                binarized = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31,
                    15,
                )
                image = Image.fromarray(binarized)
            except Exception:
                image = image.convert("L")
        else:
            image = image.convert("L")

        return image
    
    def _ocr_with_tesseract_sync(
        self,
        image: Image.Image,
    ) -> tuple[str, float]:
        """Perform OCR using Tesseract."""
        import pytesseract

        # Get text with confidence data
        data = pytesseract.image_to_data(
            image,
            lang=self.language,
            output_type=pytesseract.Output.DICT,
        )

        # Extract text
        text_parts = []
        confidences = []

        for i, conf in enumerate(data["conf"]):
            if conf > 0:  # Valid detection
                text = data["text"][i].strip()
                if text:
                    text_parts.append(text)
                    confidences.append(conf)

        full_text = " ".join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return full_text, avg_confidence / 100.0  # Normalize to 0-1


class DocxExtractor(DocumentExtractor):
    """Extract text from Word documents."""
    
    SUPPORTED_TYPES = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    
    def supports(self, mime_type: str) -> bool:
        return mime_type in self.SUPPORTED_TYPES
    
    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from DOCX file."""
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: str) -> ExtractionResult:
        from docx import Document as DocxDocument

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"DOCX file not found: {file_path}")

        doc = DocxDocument(file_path)

        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    paragraphs.append(" | ".join(row_text))

        return ExtractionResult(
            text="\n\n".join(paragraphs),
            page_count=1,  # DOCX doesn't have fixed pages
            direct_text="\n\n".join(paragraphs),
            ocr_text=None,
            used_ocr=False,
        )


def get_extractor(mime_type: str) -> Optional[DocumentExtractor]:
    """Get the appropriate extractor for a MIME type.
    
    Args:
        mime_type: MIME type of the document
        
    Returns:
        Appropriate DocumentExtractor or None if unsupported
    """
    extractors = [
        PDFExtractor(),
        ImageExtractor(),
        DocxExtractor(),
    ]
    
    for extractor in extractors:
        if extractor.supports(mime_type):
            return extractor
    
    return None
