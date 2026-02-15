"""Tests for the DocumentParser (PDF, image, CSV parsing)."""

import pytest
from pathlib import Path

from app.document_extractor.parser import DocumentParser, ParsedDocument


@pytest.fixture
def parser():
    return DocumentParser()


@pytest.fixture
def csv_file(tmp_path) -> str:
    """Create a test CSV file with freight invoice data."""
    csv_content = """Description,Quantity,Unit,Unit Price,Total
Ocean Freight,2,container,2500.00,5000.00
Port Handling,2,container,150.00,300.00
Customs Clearance,1,service,275.00,275.00"""
    path = tmp_path / "test_freight.csv"
    path.write_text(csv_content)
    return str(path)


@pytest.fixture
def text_file(tmp_path) -> str:
    """Create a plain text file."""
    path = tmp_path / "test_doc.txt"
    path.write_text("FREIGHT INVOICE\nInvoice #: FI-2024-001\nTotal: $5,575.00")
    return str(path)


@pytest.fixture
def image_file(tmp_path) -> str:
    """Create a minimal test PNG image."""
    from PIL import Image

    img = Image.new("RGB", (200, 100), color="white")
    path = tmp_path / "test_scan.png"
    img.save(path)
    return str(path)


class TestCSVParsing:
    async def test_csv_returns_text(self, parser, csv_file):
        result = await parser.parse(csv_file, "csv", "text/csv")
        assert isinstance(result, ParsedDocument)
        assert result.has_text
        assert not result.has_images
        assert "Ocean Freight" in result.text
        assert "5000.00" in result.text

    async def test_csv_has_metadata(self, parser, csv_file):
        result = await parser.parse(csv_file, "csv", "text/csv")
        assert result.metadata["rows"] == 4  # header + 3 data rows
        assert result.metadata["columns"] == 5
        assert result.page_count == 1

    async def test_csv_formatted_as_table(self, parser, csv_file):
        result = await parser.parse(csv_file, "csv", "text/csv")
        # Should have separator line after header
        lines = result.text.split("\n")
        assert len(lines) >= 5  # header + separator + 3 rows
        assert "-" in lines[1]  # separator line


class TestImageParsing:
    async def test_image_returns_base64(self, parser, image_file):
        result = await parser.parse(image_file, "png", "image/png")
        assert isinstance(result, ParsedDocument)
        assert result.has_images
        assert not result.has_text
        assert len(result.images) == 1
        assert "base64" in result.images[0]
        assert result.images[0]["media_type"] == "image/png"

    async def test_image_page_count(self, parser, image_file):
        result = await parser.parse(image_file, "png", "image/png")
        assert result.page_count == 1

    async def test_vision_required_for_image(self, parser, image_file):
        result = await parser.parse(image_file, "png", "image/png")
        assert result.is_vision_required


class TestTextFallback:
    async def test_unknown_type_reads_as_text(self, parser, text_file):
        result = await parser.parse(text_file, "txt", "text/plain")
        assert result.has_text
        assert "FREIGHT INVOICE" in result.text

    async def test_file_not_found(self, parser):
        with pytest.raises(FileNotFoundError):
            await parser.parse("/nonexistent/file.csv", "csv", "text/csv")


class TestParsedDocumentProperties:
    def test_empty_document(self):
        doc = ParsedDocument()
        assert not doc.has_text
        assert not doc.has_images
        assert not doc.is_vision_required

    def test_text_only_document(self):
        doc = ParsedDocument(text="Some content")
        assert doc.has_text
        assert not doc.has_images
        assert not doc.is_vision_required

    def test_image_only_document(self):
        doc = ParsedDocument(images=[{"base64": "abc", "media_type": "image/png"}])
        assert not doc.has_text
        assert doc.has_images
        assert doc.is_vision_required

    def test_mixed_document(self):
        doc = ParsedDocument(
            text="Some text",
            images=[{"base64": "abc", "media_type": "image/png"}],
        )
        assert doc.has_text
        assert doc.has_images
        assert not doc.is_vision_required  # Has text, so vision not required
