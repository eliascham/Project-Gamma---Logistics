"""
Document parser that routes files to the right parsing strategy.

Supports:
- PDF: text extraction via pdfplumber, falls back to page images for scanned docs
- Images (PNG/JPG/TIFF): base64 encoding for Claude vision API
- CSV: structured text table formatting
"""

import base64
import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles
import pdfplumber
from PIL import Image

logger = logging.getLogger("gamma.parser")

# Minimum chars per page to consider a PDF "text-based" vs "scanned"
SCANNED_THRESHOLD = 50

# Max image dimension before resizing (Claude vision has limits)
MAX_IMAGE_DIMENSION = 2048


@dataclass
class ParsedDocument:
    """Result of parsing a document file."""

    text: str = ""
    images: list[dict] = field(default_factory=list)  # [{"base64": str, "media_type": str}]
    page_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def is_vision_required(self) -> bool:
        """True if document needs Claude's vision API (scanned/image docs)."""
        return self.has_images and not self.has_text


class DocumentParser:
    """Routes documents to the appropriate parsing strategy."""

    async def parse(self, file_path: str, file_type: str, mime_type: str) -> ParsedDocument:
        """Parse a document file into text and/or images.

        Args:
            file_path: Path to the document file on disk.
            file_type: File extension (e.g., "pdf", "png", "csv").
            mime_type: MIME type of the file.

        Returns:
            ParsedDocument with extracted text and/or images.
        """
        file_type = file_type.lower()

        if file_type == "pdf":
            return await self._parse_pdf(file_path)
        elif file_type in ("png", "jpg", "jpeg", "tiff", "tif"):
            return await self._parse_image(file_path, mime_type)
        elif file_type == "csv":
            return await self._parse_csv(file_path)
        else:
            # Fallback: try reading as text
            return await self._parse_text(file_path)

    async def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """Parse a PDF file. Extracts text; falls back to images for scanned pages."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        text_parts: list[str] = []
        images: list[dict] = []
        page_count = 0
        scanned_pages = 0

        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                # Check if this page is scanned (minimal text)
                if len(page_text.strip()) < SCANNED_THRESHOLD:
                    scanned_pages += 1
                    # Convert page to image for vision
                    page_image = page.to_image(resolution=200)
                    img_bytes = io.BytesIO()
                    page_image.original.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    img_b64 = base64.standard_b64encode(img_bytes.read()).decode("utf-8")
                    images.append({
                        "base64": img_b64,
                        "media_type": "image/png",
                    })

        full_text = "\n\n".join(text_parts).strip()
        is_scanned = scanned_pages > page_count / 2

        logger.info(
            "Parsed PDF: %d pages, %d scanned, %d chars text",
            page_count,
            scanned_pages,
            len(full_text),
        )

        return ParsedDocument(
            text=full_text if not is_scanned else "",
            images=images if is_scanned else [],
            page_count=page_count,
            metadata={
                "scanned_pages": scanned_pages,
                "is_scanned": is_scanned,
                "text_chars": len(full_text),
            },
        )

    async def _parse_image(self, file_path: str, mime_type: str) -> ParsedDocument:
        """Parse an image file by encoding it for Claude vision."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")

        # Open and optionally resize the image
        with Image.open(path) as img:
            # Resize if too large
            if max(img.size) > MAX_IMAGE_DIMENSION:
                ratio = MAX_IMAGE_DIMENSION / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to PNG for consistent encoding
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

        img_b64 = base64.standard_b64encode(img_bytes.read()).decode("utf-8")

        # Map common MIME types
        media_type = mime_type
        if media_type in ("image/tiff", "image/tif"):
            media_type = "image/png"  # We converted to PNG

        return ParsedDocument(
            text="",
            images=[{"base64": img_b64, "media_type": "image/png"}],
            page_count=1,
            metadata={"original_mime_type": mime_type},
        )

    async def _parse_csv(self, file_path: str) -> ParsedDocument:
        """Parse a CSV file into a structured text table."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {file_path}")

        async with aiofiles.open(path, mode="r", errors="replace") as f:
            content = await f.read()

        # Parse CSV and format as readable table
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        if not rows:
            return ParsedDocument(text="", page_count=1, metadata={"rows": 0})

        # Format as aligned text table
        col_widths = [
            max(len(str(row[i])) if i < len(row) else 0 for row in rows)
            for i in range(max(len(row) for row in rows))
        ]

        formatted_lines: list[str] = []
        for row_idx, row in enumerate(rows):
            line = " | ".join(
                str(row[i]).ljust(col_widths[i]) if i < len(row) else " " * col_widths[i]
                for i in range(len(col_widths))
            )
            formatted_lines.append(line)
            # Add separator after header row
            if row_idx == 0:
                separator = "-+-".join("-" * w for w in col_widths)
                formatted_lines.append(separator)

        formatted_text = "\n".join(formatted_lines)

        return ParsedDocument(
            text=formatted_text,
            page_count=1,
            metadata={"rows": len(rows), "columns": len(col_widths)},
        )

    async def _parse_text(self, file_path: str) -> ParsedDocument:
        """Fallback: read file as plain text."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        async with aiofiles.open(path, mode="r", errors="replace") as f:
            content = await f.read()

        return ParsedDocument(
            text=content,
            page_count=1,
            metadata={"parser": "text_fallback"},
        )
