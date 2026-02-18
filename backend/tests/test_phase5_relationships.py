"""Tests for Phase 5 document relationships — model and auto-detection logic."""

import pytest
from unittest.mock import MagicMock

from app.models.document_relationship import (
    DocumentRelationship,
    RelationshipType,
)
from app.schemas.document_relationship import (
    DocumentRelationshipCreate,
    DocumentRelationshipResponse,
)


class TestRelationshipTypeEnum:
    """Test RelationshipType enum values."""

    def test_all_types_present(self):
        expected = {
            "fulfills", "invoices", "supports", "adjusts",
            "certifies", "clears", "confirms", "notifies",
        }
        actual = {t.value for t in RelationshipType}
        assert actual == expected

    def test_string_values(self):
        assert RelationshipType.FULFILLS.value == "fulfills"
        assert RelationshipType.INVOICES.value == "invoices"
        assert RelationshipType.ADJUSTS.value == "adjusts"


class TestDocumentRelationshipCreate:
    """Test the create request schema."""

    def test_minimal(self):
        import uuid
        req = DocumentRelationshipCreate(
            source_document_id=uuid.uuid4(),
            target_document_id=uuid.uuid4(),
            relationship_type="supports",
        )
        assert req.confidence == 1.0
        assert req.reference_field is None

    def test_full(self):
        import uuid
        req = DocumentRelationshipCreate(
            source_document_id=uuid.uuid4(),
            target_document_id=uuid.uuid4(),
            relationship_type="adjusts",
            reference_field="original_invoice_number",
            reference_value="FI-2025-001",
            confidence=0.95,
        )
        assert req.reference_field == "original_invoice_number"
        assert req.confidence == 0.95


class TestDocumentRelationshipResponse:
    """Test the response schema."""

    def test_from_attributes(self):
        import uuid
        from datetime import datetime

        mock_rel = MagicMock()
        mock_rel.id = uuid.uuid4()
        mock_rel.source_document_id = uuid.uuid4()
        mock_rel.target_document_id = uuid.uuid4()
        mock_rel.relationship_type = "supports"
        mock_rel.reference_field = "bol_number"
        mock_rel.reference_value = "BOL-001"
        mock_rel.confidence = 1.0
        mock_rel.created_by = "system"
        mock_rel.created_at = datetime(2025, 6, 1)

        resp = DocumentRelationshipResponse.model_validate(mock_rel, from_attributes=True)
        assert resp.relationship_type == "supports"
        assert resp.created_by == "system"


class TestReferenceFieldMappings:
    """Test that reference field mappings in relationships.py are correct."""

    def test_reference_map_keys(self):
        from app.api.v1.relationships import _REFERENCE_FIELD_MAP
        # All map keys should be valid document types
        from app.schemas.extraction import DocumentType
        valid_types = {t.value for t in DocumentType}
        for key in _REFERENCE_FIELD_MAP:
            assert key in valid_types, f"{key} is not a valid DocumentType"

    def test_primary_ref_fields(self):
        from app.api.v1.relationships import _PRIMARY_REF_FIELDS
        expected_types = {"freight_invoice", "bill_of_lading", "commercial_invoice", "purchase_order", "air_waybill"}
        assert set(_PRIMARY_REF_FIELDS.keys()) == expected_types


class TestNormalizeReference:
    """Test reference number normalization for fuzzy matching."""

    def test_strip_po_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("PO-12345") == "12345"

    def test_strip_inv_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("INV-00789") == "789"

    def test_strip_bol_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("BOL-001") == "1"

    def test_strip_awb_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("AWB-5678") == "5678"

    def test_strip_hyphens_and_dots(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("123-456.789") == "123456789"

    def test_strip_leading_zeros(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("000123") == "123"

    def test_all_zeros(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("0000") == "0"

    def test_case_insensitive(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("po-123") == _normalize_reference("PO-123")

    def test_whitespace_stripped(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("  INV 456  ") == "456"

    def test_matching_variants(self):
        """Different representations of the same reference should normalize equally."""
        from app.api.v1.relationships import _normalize_reference
        variants = [
            "PO-00123",
            "PO00123",
            "PO-123",
            "00123",
            "123",
        ]
        normalized = {_normalize_reference(v) for v in variants}
        assert len(normalized) == 1, f"Expected all variants to normalize the same, got {normalized}"
        assert normalized == {"123"}

    def test_ref_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("REF-0042") == "42"

    def test_no_prefix_plain_number(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("98765") == "98765"


class TestUniqueConstraint:
    """Test that the ORM model declares the unique constraint."""

    def test_unique_constraint_defined(self):
        from app.models.document_relationship import DocumentRelationship
        constraints = DocumentRelationship.__table_args__
        assert any(
            hasattr(c, "name") and c.name == "uq_document_relationships_src_tgt_type"
            for c in constraints
            if not isinstance(c, dict)
        ), "UniqueConstraint uq_document_relationships_src_tgt_type not found"

    def test_unique_constraint_columns(self):
        from app.models.document_relationship import DocumentRelationship
        import sqlalchemy as sa
        for c in DocumentRelationship.__table_args__:
            if isinstance(c, sa.UniqueConstraint) and c.name == "uq_document_relationships_src_tgt_type":
                col_names = [col.name for col in c.columns]
                assert "source_document_id" in col_names
                assert "target_document_id" in col_names
                assert "relationship_type" in col_names
                break
        else:
            pytest.fail("UniqueConstraint not found in __table_args__")


class TestInvoiceVariantClassification:
    """Test that invoice_variant field works correctly across schemas."""

    def test_freight_invoice_variants(self):
        from app.schemas.extraction import FreightInvoiceExtraction
        for variant in ["standard", "detention_demurrage", "accessorial", "consolidated", "pro_forma"]:
            inv = FreightInvoiceExtraction(
                invoice_number="FI-001",
                vendor_name="Test",
                total_amount=100.0,
                invoice_variant=variant,
            )
            assert inv.invoice_variant == variant

    def test_commercial_invoice_variants(self):
        from app.schemas.extraction import CommercialInvoiceExtraction, PartyInfo
        for variant in ["standard", "pro_forma"]:
            inv = CommercialInvoiceExtraction(
                invoice_number="CI-001",
                seller=PartyInfo(name="Seller"),
                buyer=PartyInfo(name="Buyer"),
                currency="USD",
                line_items=[],
                total_amount=100.0,
                invoice_variant=variant,
            )
            assert inv.invoice_variant == variant
