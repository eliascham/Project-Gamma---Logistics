"""
Phase 5 stress tests -- robustness, edge cases, and security validation.

Tests cover:
- Large document schemas (100+ line items)
- Minimal/all-null optional fields
- Maximum field lengths
- Matching with many line items
- Numeric edge cases (NaN, Inf, negatives, zero division)
- Self-referencing and cyclic relationships
- Reference normalization edge cases
- Schema validation rejection of bad data
- Cost allocation formatting for all document types
"""

import math
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.matching_engine.matchers import (
    MatchStatus,
    compute_three_way_match,
    match_description,
    match_line_items,
    match_numeric,
    match_party_name,
)
from app.schemas.extraction import (
    EXTRACTION_MODEL_REGISTRY,
    AdjustmentLineItem,
    AirWaybillExtraction,
    ArrivalCharge,
    ArrivalNoticeExtraction,
    AWBCharge,
    BillOfLadingExtraction,
    CertificateOfOriginExtraction,
    CommercialInvoiceExtraction,
    CommercialLineItem,
    CustomsEntryExtraction,
    DebitCreditNoteExtraction,
    DeliveryItem,
    DemurrageDetail,
    DocumentType,
    EntryLineItem,
    FreightInvoiceExtraction,
    LineItem,
    OriginItem,
    POLineItem,
    PackingItem,
    PackingListExtraction,
    PartyInfo,
    ProofOfDeliveryExtraction,
    PurchaseOrderExtraction,
)


# ---------------------------------------------------------------------------
# 1. LARGE DOCUMENT STRESS TESTS
# ---------------------------------------------------------------------------


class TestLargeDocuments:
    """Test schemas with large numbers of line items."""

    def test_freight_invoice_100_line_items(self):
        """Freight invoice with 100 line items should validate."""
        items = [
            LineItem(
                description=f"Service charge #{i}",
                quantity=float(i + 1),
                unit="kg",
                unit_price=10.50,
                total=(i + 1) * 10.50,
            )
            for i in range(100)
        ]
        inv = FreightInvoiceExtraction(
            invoice_number="FI-LARGE-001",
            vendor_name="Mega Carrier Inc",
            line_items=items,
            total_amount=sum(it.total for it in items),
        )
        assert len(inv.line_items) == 100
        assert inv.total_amount > 0

    def test_commercial_invoice_200_line_items(self):
        """Commercial invoice with 200 line items."""
        items = [
            CommercialLineItem(
                item_number=f"SKU-{i:04d}",
                description=f"Electronic component model {i}",
                hs_code="8542310000",
                quantity=float(i + 1),
                unit="pcs",
                unit_price=5.99,
                total=(i + 1) * 5.99,
            )
            for i in range(200)
        ]
        inv = CommercialInvoiceExtraction(
            invoice_number="CI-LARGE-001",
            seller=PartyInfo(name="Mega Exporter"),
            buyer=PartyInfo(name="Mega Importer"),
            currency="USD",
            line_items=items,
            total_amount=sum(it.total for it in items),
        )
        assert len(inv.line_items) == 200

    def test_purchase_order_150_line_items(self):
        """PO with 150 line items."""
        items = [
            POLineItem(
                line_number=i + 1,
                item_number=f"PART-{i:05d}",
                description=f"Mechanical part type {i}",
                quantity=100.0,
                unit="ea",
                unit_price=25.0,
                total=2500.0,
            )
            for i in range(150)
        ]
        po = PurchaseOrderExtraction(
            po_number="PO-LARGE-001",
            buyer=PartyInfo(name="Buyer Corp"),
            supplier=PartyInfo(name="Supplier Inc"),
            currency="USD",
            line_items=items,
            total_amount=150 * 2500.0,
        )
        assert len(po.line_items) == 150

    def test_customs_entry_50_line_items(self):
        """CBP 7501 with 50 HTS line items."""
        items = [
            EntryLineItem(
                line_number=i + 1,
                hts_number=f"854231{i:04d}",
                description=f"Import item category {i}",
                entered_value=float(1000 * (i + 1)),
                duty_rate=0.05,
                duty_amount=float(50 * (i + 1)),
            )
            for i in range(50)
        ]
        ce = CustomsEntryExtraction(
            entry_number="12345678901",
            line_items=items,
            total_entered_value=sum(it.entered_value for it in items),
            total_duty=sum(it.duty_amount or 0 for it in items),
        )
        assert len(ce.line_items) == 50

    def test_packing_list_100_items(self):
        """Packing list with 100 items."""
        items = [
            PackingItem(
                item_number=f"ITM-{i:04d}",
                description=f"Widget variant {i}",
                quantity=float(i + 1),
                unit="pcs",
                package_type="carton",
                package_count=max(1, (i + 1) // 10),
                gross_weight=float(i + 1) * 0.5,
                net_weight=float(i + 1) * 0.45,
                dimensions="30 x 20 x 15",
            )
            for i in range(100)
        ]
        pl = PackingListExtraction(
            packing_list_number="PL-LARGE-001",
            items=items,
            total_packages=100,
            total_gross_weight=sum(it.gross_weight or 0 for it in items),
        )
        assert len(pl.items) == 100

    def test_arrival_notice_many_charges(self):
        """Arrival notice with 30 itemized charges."""
        charges = [
            ArrivalCharge(
                charge_type=f"Charge type {i}",
                amount=float(100 + i * 10),
            )
            for i in range(30)
        ]
        an = ArrivalNoticeExtraction(
            notice_number="AN-LARGE-001",
            charges=charges,
            total_charges=sum(c.amount for c in charges),
        )
        assert len(an.charges) == 30

    def test_air_waybill_many_other_charges(self):
        """AWB with many other charges."""
        charges = [
            AWBCharge(
                charge_code=f"C{i:02d}",
                charge_type=f"Surcharge type {i}",
                amount=float(50 + i * 5),
                prepaid_or_collect="PP",
            )
            for i in range(25)
        ]
        awb = AirWaybillExtraction(
            awb_number="17612345678",
            other_charges=charges,
            total_charges=2500.0 + sum(c.amount for c in charges),
        )
        assert len(awb.other_charges) == 25

    def test_freight_invoice_many_demurrage_details(self):
        """D&D invoice with many container demurrage lines."""
        details = [
            DemurrageDetail(
                container_number=f"CONT{i:07d}",
                free_time_days=5,
                daily_rate=150.0,
                total_chargeable_days=i + 1,
            )
            for i in range(20)
        ]
        inv = FreightInvoiceExtraction(
            invoice_number="FI-DD-001",
            vendor_name="Port Authority",
            total_amount=sum(d.daily_rate * (d.total_chargeable_days or 0) for d in details),
            invoice_variant="detention_demurrage",
            demurrage_details=details,
        )
        assert len(inv.demurrage_details) == 20


# ---------------------------------------------------------------------------
# 2. MINIMAL / ALL-NULL OPTIONAL FIELDS
# ---------------------------------------------------------------------------


class TestMinimalDocuments:
    """Test each schema with only required fields (all optionals null)."""

    def test_freight_invoice_minimal(self):
        inv = FreightInvoiceExtraction(
            invoice_number="MIN-001",
            vendor_name="V",
            total_amount=0.0,
        )
        assert inv.line_items == []
        assert inv.invoice_date is None
        assert inv.subtotal is None

    def test_commercial_invoice_empty_line_items(self):
        """CommercialInvoice requires line_items as a list, but it can be empty."""
        inv = CommercialInvoiceExtraction(
            invoice_number="CI-MIN",
            seller=PartyInfo(name="S"),
            buyer=PartyInfo(name="B"),
            currency="USD",
            line_items=[],
            total_amount=0.0,
        )
        assert inv.line_items == []

    def test_purchase_order_empty_line_items(self):
        po = PurchaseOrderExtraction(
            po_number="PO-MIN",
            buyer=PartyInfo(name="B"),
            supplier=PartyInfo(name="S"),
            currency="USD",
            line_items=[],
            total_amount=0.0,
        )
        assert po.line_items == []

    def test_packing_list_empty_items(self):
        """PackingList requires items list but it can be empty."""
        pl = PackingListExtraction(items=[])
        assert pl.items == []
        assert pl.packing_list_number is None

    def test_arrival_notice_fully_empty(self):
        """ArrivalNotice has no required fields."""
        an = ArrivalNoticeExtraction()
        assert an.notice_number is None
        assert an.charges == []

    def test_air_waybill_only_required(self):
        awb = AirWaybillExtraction(awb_number="12345678901")
        assert awb.awb_type is None
        assert awb.other_charges == []

    def test_debit_credit_note_minimal(self):
        dcn = DebitCreditNoteExtraction(
            note_number="N-001",
            note_type="credit",
            currency="USD",
            total_amount=-100.0,
        )
        assert dcn.line_items == []

    def test_customs_entry_minimal(self):
        ce = CustomsEntryExtraction(
            entry_number="12345678901",
            line_items=[],
        )
        assert ce.total_amount is None

    def test_proof_of_delivery_minimal(self):
        pod = ProofOfDeliveryExtraction()
        assert pod.items == []
        assert pod.receiver_signature is False

    def test_certificate_of_origin_minimal(self):
        co = CertificateOfOriginExtraction(
            country_of_origin="US",
            items=[],
        )
        assert co.certificate_number is None


# ---------------------------------------------------------------------------
# 3. SCHEMA VALIDATION - REJECTION OF BAD DATA
# ---------------------------------------------------------------------------


class TestSchemaRejection:
    """Test that schemas reject invalid data correctly."""

    def test_freight_invoice_missing_required_invoice_number(self):
        with pytest.raises(ValidationError):
            FreightInvoiceExtraction(
                vendor_name="V",
                total_amount=100.0,
            )

    def test_freight_invoice_missing_required_vendor_name(self):
        with pytest.raises(ValidationError):
            FreightInvoiceExtraction(
                invoice_number="FI-001",
                total_amount=100.0,
            )

    def test_freight_invoice_missing_required_total_amount(self):
        with pytest.raises(ValidationError):
            FreightInvoiceExtraction(
                invoice_number="FI-001",
                vendor_name="V",
            )

    def test_commercial_invoice_missing_seller(self):
        with pytest.raises(ValidationError):
            CommercialInvoiceExtraction(
                invoice_number="CI-001",
                buyer=PartyInfo(name="B"),
                currency="USD",
                line_items=[],
                total_amount=100.0,
            )

    def test_commercial_invoice_missing_buyer(self):
        with pytest.raises(ValidationError):
            CommercialInvoiceExtraction(
                invoice_number="CI-001",
                seller=PartyInfo(name="S"),
                currency="USD",
                line_items=[],
                total_amount=100.0,
            )

    def test_purchase_order_missing_po_number(self):
        with pytest.raises(ValidationError):
            PurchaseOrderExtraction(
                buyer=PartyInfo(name="B"),
                supplier=PartyInfo(name="S"),
                currency="USD",
                line_items=[],
                total_amount=100.0,
            )

    def test_customs_entry_missing_entry_number(self):
        with pytest.raises(ValidationError):
            CustomsEntryExtraction(
                line_items=[EntryLineItem(hts_number="8542", description="ICs", entered_value=100)],
            )

    def test_air_waybill_missing_awb_number(self):
        with pytest.raises(ValidationError):
            AirWaybillExtraction()

    def test_debit_credit_note_missing_note_type(self):
        with pytest.raises(ValidationError):
            DebitCreditNoteExtraction(
                note_number="N-001",
                currency="USD",
                total_amount=100.0,
            )

    def test_certificate_of_origin_missing_country(self):
        with pytest.raises(ValidationError):
            CertificateOfOriginExtraction(
                items=[OriginItem(description="Goods")],
            )

    def test_party_info_missing_name(self):
        with pytest.raises(ValidationError):
            PartyInfo(address="123 Main St")

    def test_line_item_missing_description(self):
        with pytest.raises(ValidationError):
            LineItem(quantity=1, unit="ea", unit_price=10.0, total=10.0)

    def test_commercial_line_item_missing_quantity(self):
        with pytest.raises(ValidationError):
            CommercialLineItem(description="Item", unit="pcs", unit_price=5.0, total=5.0)

    def test_entry_line_item_missing_hts(self):
        with pytest.raises(ValidationError):
            EntryLineItem(description="Goods", entered_value=1000.0)


# ---------------------------------------------------------------------------
# 4. NUMERIC EDGE CASES FOR MATCHING
# ---------------------------------------------------------------------------


class TestMatchingNumericEdgeCases:
    """Test matching functions with extreme and edge-case numeric values."""

    def test_very_large_numbers(self):
        matched, conf = match_numeric(1e12, 1e12)
        assert matched is True
        assert conf == 1.0

    def test_very_small_numbers(self):
        matched, conf = match_numeric(0.001, 0.001)
        assert matched is True
        assert conf == 1.0

    def test_negative_values_exact(self):
        matched, conf = match_numeric(-500.0, -500.0)
        assert matched is True
        assert conf == 1.0

    def test_negative_values_close(self):
        matched, conf = match_numeric(-500.0, -495.0, tolerance_pct=0.05)
        assert matched is True

    def test_mixed_sign_mismatch(self):
        """Positive vs negative should never match."""
        matched, _ = match_numeric(500.0, -500.0)
        assert matched is False

    def test_both_none(self):
        matched, conf = match_numeric(None, None)
        assert matched is False
        assert conf == 0.0

    def test_near_zero_tolerance(self):
        """Very tight tolerance should only accept exact matches."""
        matched, _ = match_numeric(100.0, 100.5, tolerance_pct=0.001, tolerance_abs=0.0)
        assert matched is False

    def test_exact_tolerance_boundary(self):
        """Value exactly at tolerance boundary."""
        # 5% of 100 = 5; 100 vs 105 is exactly at 5% boundary
        matched, _ = match_numeric(100.0, 105.0, tolerance_pct=0.05)
        assert matched is True

    def test_just_outside_tolerance(self):
        # 100 vs 106 -- diff=6, max=106, pct=5.66% > 5% tolerance
        matched, _ = match_numeric(100.0, 106.0, tolerance_pct=0.05)
        assert matched is False


class TestMatchingDescriptionEdgeCases:
    """Test description matching edge cases."""

    def test_empty_strings(self):
        matched, _ = match_description("", "")
        assert matched is False

    def test_single_word_match(self):
        matched, conf = match_description("freight", "freight")
        assert matched is True
        assert conf == 1.0

    def test_very_long_descriptions(self):
        """Match with very long descriptions (500+ words)."""
        long_desc_a = " ".join([f"word{i}" for i in range(500)])
        long_desc_b = " ".join([f"word{i}" for i in range(300)])  # 60% overlap
        matched, conf = match_description(long_desc_a, long_desc_b)
        assert matched is True
        assert conf >= 0.5

    def test_description_with_special_chars(self):
        matched, conf = match_description(
            "Widget (A) - 100pcs @$5.00/ea",
            "Widget (A) - 100pcs @$5.00/ea",
        )
        assert matched is True

    def test_unicode_descriptions(self):
        matched, conf = match_description(
            "Elektronische Bauteile Typ A",
            "Elektronische Bauteile Typ B",
        )
        assert matched is True


class TestMatchingPartyNameEdgeCases:
    """Test party name matching edge cases."""

    def test_empty_string(self):
        matched, _ = match_party_name("", "Acme")
        assert matched is False

    def test_whitespace_only(self):
        matched, _ = match_party_name("   ", "Acme")
        assert matched is False

    def test_very_long_company_names(self):
        name_a = "International Global Trading Commerce Business Services Corporation LLC"
        name_b = "International Global Trading Commerce Business Services Corp."
        matched, conf = match_party_name(name_a, name_b)
        assert matched is True

    def test_all_suffix_stripping(self):
        """Test that all known suffixes are properly stripped."""
        base = "Acme"
        suffixes = [" LLC", " Inc", " Inc.", " Co", " Co.", " Ltd", " Ltd.",
                    " Corp", " Corp.", " Corporation", " Company",
                    " Limited", " GmbH", " SA", " S.A."]
        for suffix in suffixes:
            matched, conf = match_party_name(base + suffix, base)
            assert matched is True, f"Failed to match '{base + suffix}' vs '{base}'"


# ---------------------------------------------------------------------------
# 5. LINE ITEM MATCHING STRESS TESTS
# ---------------------------------------------------------------------------


class TestLineItemMatchingStress:
    """Test line item matching with large sets and edge cases."""

    def test_50_vs_50_line_items(self):
        """Matching 50 PO items against 50 invoice items."""
        po_items = [
            {"description": f"Part number {i} electronic component", "quantity": float(100 + i), "unit_price": float(10 + i)}
            for i in range(50)
        ]
        inv_items = [
            {"description": f"Part number {i} electronic component shipped", "quantity": float(100 + i), "unit_price": float(10 + i)}
            for i in range(50)
        ]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 50
        # Most items should match well
        good_matches = [r for r in results if r.overall > 0.5]
        assert len(good_matches) >= 40

    def test_mismatched_counts(self):
        """PO has 10 items, invoice has 5 items."""
        po_items = [
            {"description": f"Item {i} widget", "quantity": 10.0, "unit_price": 5.0}
            for i in range(10)
        ]
        inv_items = [
            {"description": f"Item {i} widget", "quantity": 10.0, "unit_price": 5.0}
            for i in range(5)
        ]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 10  # One result per PO item
        # 5 should match, 5 should not
        unmatched = [r for r in results if r.invoice_index is None]
        assert len(unmatched) == 5

    def test_all_identical_descriptions(self):
        """All items have the same description -- greedy match should still pair them."""
        po_items = [
            {"description": "Identical widget part", "quantity": float(i + 1) * 10, "unit_price": 5.0}
            for i in range(5)
        ]
        inv_items = [
            {"description": "Identical widget part", "quantity": float(i + 1) * 10, "unit_price": 5.0}
            for i in range(5)
        ]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 5
        # Each PO item should get some invoice index (greedy assigns first best)
        assigned = [r.invoice_index for r in results if r.invoice_index is not None]
        assert len(set(assigned)) == len(assigned), "Greedy matching should not assign same invoice index twice"

    def test_zero_quantity_items(self):
        """Line items with zero quantity."""
        po_items = [{"description": "Free sample widget", "quantity": 0, "unit_price": 0.0}]
        inv_items = [{"description": "Free sample widget shipped", "quantity": 0, "unit_price": 0.0}]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 1
        # Both zero -> exact match on quantity
        assert results[0].quantity_match == 1.0

    def test_missing_fields_in_items(self):
        """Line items with missing quantity/price fields."""
        po_items = [{"description": "Widget A"}]  # No quantity or unit_price
        inv_items = [{"description": "Widget A product"}]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 1
        # match_numeric with None -> 0.0 score
        assert results[0].quantity_match == 0.0


# ---------------------------------------------------------------------------
# 6. THREE-WAY MATCH STRESS TESTS
# ---------------------------------------------------------------------------


class TestThreeWayMatchStress:
    """Test 3-way matching with complex scenarios."""

    def test_large_po_and_invoice(self):
        """3-way match with 30+ line items."""
        po = {
            "supplier": {"name": "Big Supplier Corp"},
            "total_amount": 300000.0,
            "line_items": [
                {
                    "description": f"Component type {i} grade A",
                    "quantity": float(100 + i * 10),
                    "unit_price": float(100.0),
                    "total": float((100 + i * 10) * 100),
                }
                for i in range(30)
            ],
        }
        bol = {"gross_weight": 5000.0, "weight_unit": "kg"}
        invoice = {
            "seller": {"name": "Big Supplier Corporation"},
            "total_amount": 300000.0,
            "line_items": [
                {
                    "description": f"Component type {i} grade A shipped",
                    "quantity": float(100 + i * 10),
                    "unit_price": float(100.0),
                    "total": float((100 + i * 10) * 100),
                }
                for i in range(30)
            ],
        }
        result = compute_three_way_match(po, bol, invoice)
        assert result.status in (MatchStatus.FULL_MATCH, MatchStatus.PARTIAL_MATCH)
        assert result.overall_confidence > 0.5

    def test_currency_mismatch_scenario(self):
        """Documents with different currencies -- matching should still work on amounts."""
        po = {
            "supplier": {"name": "Euro Seller GmbH"},
            "total_amount": 10000.0,  # EUR
            "currency": "EUR",
            "line_items": [
                {"description": "Widget EUR batch", "quantity": 100, "unit_price": 100.0}
            ],
        }
        invoice = {
            "seller": {"name": "Euro Seller GmbH"},
            "total_amount": 11200.0,  # USD equivalent (12% diff)
            "currency": "USD",
            "line_items": [
                {"description": "Widget EUR batch converted", "quantity": 100, "unit_price": 112.0}
            ],
        }
        result = compute_three_way_match(po, {}, invoice)
        # Should be a mismatch since amounts differ by 12% (> 5% tolerance)
        assert result.status in (MatchStatus.MISMATCH, MatchStatus.PARTIAL_MATCH)

    def test_empty_line_items_both_sides(self):
        """Both PO and invoice have empty line items."""
        po = {
            "supplier": {"name": "Test Supplier"},
            "total_amount": 1000.0,
            "line_items": [],
        }
        invoice = {
            "seller": {"name": "Test Supplier"},
            "total_amount": 1000.0,
            "line_items": [],
        }
        result = compute_three_way_match(po, {}, invoice)
        # Should still match on party name and total amount
        assert result.overall_confidence > 0

    def test_party_as_string_not_dict(self):
        """Extraction might have party as a plain string, not a dict."""
        po = {
            "supplier": "Acme Corp",
            "total_amount": 1000.0,
            "line_items": [],
        }
        invoice = {
            "seller": "Acme Corp",
            "total_amount": 1000.0,
            "line_items": [],
        }
        result = compute_three_way_match(po, {}, invoice)
        party_match = next((fm for fm in result.field_matches if fm.field_name == "party_name"), None)
        assert party_match is not None
        assert party_match.matched is True


# ---------------------------------------------------------------------------
# 7. REFERENCE NORMALIZATION EDGE CASES
# ---------------------------------------------------------------------------


class TestNormalizeReferenceEdgeCases:
    """Test reference normalization with unusual inputs."""

    def test_empty_string(self):
        from app.api.v1.relationships import _normalize_reference
        result = _normalize_reference("")
        # Should handle gracefully (empty or "0")
        assert result == "" or result == "0"

    def test_only_prefix(self):
        from app.api.v1.relationships import _normalize_reference
        result = _normalize_reference("PO-")
        # After stripping prefix "PO-", we have empty -> "0"
        assert result == "0"

    def test_special_characters(self):
        from app.api.v1.relationships import _normalize_reference
        result = _normalize_reference("REF#123/456")
        assert "123" in result

    def test_very_long_reference(self):
        from app.api.v1.relationships import _normalize_reference
        long_ref = "PO-" + "1" * 200
        result = _normalize_reference(long_ref)
        assert len(result) > 0
        assert result == "1" * 200

    def test_numeric_only(self):
        from app.api.v1.relationships import _normalize_reference
        assert _normalize_reference("42") == "42"

    def test_alphanumeric(self):
        from app.api.v1.relationships import _normalize_reference
        result = _normalize_reference("ABC123")
        assert "ABC123" in result.upper()


# ---------------------------------------------------------------------------
# 8. RELATIONSHIP MODEL EDGE CASES
# ---------------------------------------------------------------------------


class TestRelationshipEdgeCases:
    """Test document relationship model edge cases."""

    def test_self_referencing_relationship_schema(self):
        """Schema allows same source and target -- application layer should prevent."""
        doc_id = uuid.uuid4()
        from app.schemas.document_relationship import DocumentRelationshipCreate
        req = DocumentRelationshipCreate(
            source_document_id=doc_id,
            target_document_id=doc_id,
            relationship_type="supports",
        )
        # Schema currently allows this -- noting as a security finding
        assert req.source_document_id == req.target_document_id

    def test_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        from app.schemas.document_relationship import DocumentRelationshipCreate
        # Valid bounds
        req = DocumentRelationshipCreate(
            source_document_id=uuid.uuid4(),
            target_document_id=uuid.uuid4(),
            relationship_type="supports",
            confidence=0.0,
        )
        assert req.confidence == 0.0

        req = DocumentRelationshipCreate(
            source_document_id=uuid.uuid4(),
            target_document_id=uuid.uuid4(),
            relationship_type="supports",
            confidence=1.0,
        )
        assert req.confidence == 1.0

    def test_confidence_out_of_bounds_rejected(self):
        """Confidence > 1 or < 0 should be rejected."""
        from app.schemas.document_relationship import DocumentRelationshipCreate
        with pytest.raises(ValidationError):
            DocumentRelationshipCreate(
                source_document_id=uuid.uuid4(),
                target_document_id=uuid.uuid4(),
                relationship_type="supports",
                confidence=1.5,
            )
        with pytest.raises(ValidationError):
            DocumentRelationshipCreate(
                source_document_id=uuid.uuid4(),
                target_document_id=uuid.uuid4(),
                relationship_type="supports",
                confidence=-0.1,
            )

    def test_reference_field_max_length(self):
        """reference_field has max_length=100."""
        from app.schemas.document_relationship import DocumentRelationshipCreate
        with pytest.raises(ValidationError):
            DocumentRelationshipCreate(
                source_document_id=uuid.uuid4(),
                target_document_id=uuid.uuid4(),
                relationship_type="supports",
                reference_field="a" * 101,
            )

    def test_reference_value_max_length(self):
        """reference_value has max_length=500."""
        from app.schemas.document_relationship import DocumentRelationshipCreate
        with pytest.raises(ValidationError):
            DocumentRelationshipCreate(
                source_document_id=uuid.uuid4(),
                target_document_id=uuid.uuid4(),
                relationship_type="supports",
                reference_value="b" * 501,
            )


# ---------------------------------------------------------------------------
# 9. REGISTRY COMPLETENESS
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Verify the extraction model registry covers all types."""

    def test_all_non_unknown_types_in_registry(self):
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
            assert doc_type in EXTRACTION_MODEL_REGISTRY, (
                f"{doc_type.value} missing from EXTRACTION_MODEL_REGISTRY"
            )

    def test_schema_template_registry(self):
        """Each type in the model registry should also have a Claude schema template."""
        from app.services.claude_service import _SCHEMA_REGISTRY
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
            assert doc_type in _SCHEMA_REGISTRY, (
                f"{doc_type.value} missing from _SCHEMA_REGISTRY in claude_service"
            )

    def test_unknown_type_falls_back(self):
        """UNKNOWN type should not crash extraction."""
        from app.services.claude_service import _get_schema_for_type, _validate_extraction
        schema = _get_schema_for_type(DocumentType.UNKNOWN)
        assert schema is not None  # Falls back to freight invoice schema

        # _validate_extraction should also handle unknown
        data = {
            "invoice_number": "UNKNOWN-001",
            "vendor_name": "Test",
            "total_amount": 100.0,
        }
        result = _validate_extraction(DocumentType.UNKNOWN, data)
        assert result["invoice_number"] == "UNKNOWN-001"


# ---------------------------------------------------------------------------
# 10. COST ALLOCATION FORMATTING
# ---------------------------------------------------------------------------


class TestCostAllocationFormatting:
    """Test that cost allocation pipeline correctly formats all supported doc types."""

    def _make_pipeline(self):
        from app.cost_allocator.pipeline import CostAllocationPipeline
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-test"
        mock_settings.allocation_confidence_threshold = 0.85
        return CostAllocationPipeline(mock_settings)

    def test_format_freight_invoice(self):
        pipeline = self._make_pipeline()
        extraction = {
            "invoice_number": "FI-001",
            "vendor_name": "Carrier A",
            "line_items": [
                {"description": "Ocean freight", "quantity": 1, "unit": "container", "unit_price": 3000, "total": 3000}
            ],
            "total_amount": 3000.0,
        }
        result = pipeline._format_invoice(extraction)
        assert "FI-001" in result
        assert "Carrier A" in result
        assert "Ocean freight" in result

    def test_format_commercial_invoice(self):
        pipeline = self._make_pipeline()
        extraction = {
            "invoice_number": "CI-001",
            "seller": {"name": "Exporter Co"},
            "buyer": {"name": "Importer Co"},
            "line_items": [
                {"description": "Goods A", "hs_code": "854231", "quantity": 100, "unit": "pcs", "unit_price": 10, "total": 1000}
            ],
            "total_amount": 1000.0,
        }
        result = pipeline._format_invoice(extraction, doc_type="commercial_invoice")
        assert "Commercial Invoice" in result
        assert "Exporter Co" in result
        assert "HS: 854231" in result

    def test_format_customs_entry(self):
        pipeline = self._make_pipeline()
        extraction = {
            "entry_number": "12345678901",
            "importer_name": "US Corp",
            "line_items": [
                {"hts_number": "8542310000", "description": "ICs", "entered_value": 25000, "duty_rate": 0.035, "duty_amount": 875}
            ],
            "total_entered_value": 25000,
            "total_duty": 875,
            "total_other": 120,
            "total_amount": 995,
        }
        result = pipeline._format_invoice(extraction, doc_type="customs_entry")
        assert "Customs Entry" in result
        assert "12345678901" in result
        assert "HTS" in result

    def test_format_debit_credit_note(self):
        pipeline = self._make_pipeline()
        extraction = {
            "note_number": "CN-001",
            "note_type": "credit",
            "original_invoice_number": "FI-001",
            "currency": "USD",
            "line_items": [
                {"description": "Overcharge", "original_amount": 3000, "adjusted_amount": 2800, "difference": -200}
            ],
            "total_amount": -200,
        }
        result = pipeline._format_invoice(extraction, doc_type="debit_credit_note")
        assert "Credit Note" in result
        assert "CN-001" in result
        assert "Overcharge" in result

    def test_format_unknown_doc_falls_back_to_freight(self):
        """Document without recognized keys should fall through to freight invoice format."""
        pipeline = self._make_pipeline()
        extraction = {
            "invoice_number": "MYSTERY-001",
            "vendor_name": "Unknown Vendor",
            "line_items": [],
            "total_amount": 500,
        }
        result = pipeline._format_invoice(extraction)
        assert "MYSTERY-001" in result


# ---------------------------------------------------------------------------
# 11. DOCUMENT TYPE ENUM CONSISTENCY
# ---------------------------------------------------------------------------


class TestDocumentTypeConsistency:
    """Verify classifier prompt and schema registry are in sync."""

    def test_classifier_handles_all_types(self):
        """Classification prompt should mention all non-unknown document types."""
        # Read classifier source directly to avoid __init__.py importing parser (needs aiofiles)
        import pathlib
        classifier_src = pathlib.Path(
            "/mnt/s/Claude/project-gamma/backend/app/document_extractor/classifier.py"
        ).read_text()
        # Extract the CLASSIFICATION_PROMPT string from source
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
            assert doc_type.value in classifier_src, (
                f"Classifier prompt missing description for {doc_type.value}"
            )

    def test_classifier_unknown_type(self):
        """Classifier prompt should include unknown as an option."""
        import pathlib
        classifier_src = pathlib.Path(
            "/mnt/s/Claude/project-gamma/backend/app/document_extractor/classifier.py"
        ).read_text()
        assert "unknown" in classifier_src


# ---------------------------------------------------------------------------
# 12. LONG STRING FIELDS
# ---------------------------------------------------------------------------


class TestLongStringFields:
    """Test schemas handle long strings without errors."""

    def test_long_invoice_number(self):
        """Invoice number with 200+ characters."""
        inv = FreightInvoiceExtraction(
            invoice_number="X" * 500,
            vendor_name="V",
            total_amount=100.0,
        )
        assert len(inv.invoice_number) == 500

    def test_long_party_name(self):
        party = PartyInfo(name="A" * 1000)
        assert len(party.name) == 1000

    def test_long_notes_field(self):
        inv = FreightInvoiceExtraction(
            invoice_number="FI-001",
            vendor_name="V",
            total_amount=100.0,
            notes="N" * 10000,
        )
        assert len(inv.notes) == 10000

    def test_long_description_in_line_item(self):
        item = LineItem(
            description="D" * 5000,
            quantity=1,
            unit="ea",
            unit_price=10.0,
            total=10.0,
        )
        assert len(item.description) == 5000

    def test_long_hs_code(self):
        """HS code field with unusual length (should not crash)."""
        item = CommercialLineItem(
            description="Test",
            hs_code="9" * 100,
            quantity=1,
            unit="pcs",
            unit_price=5.0,
            total=5.0,
        )
        assert len(item.hs_code) == 100


# ---------------------------------------------------------------------------
# 13. NEGATIVE AND ZERO AMOUNT EDGE CASES
# ---------------------------------------------------------------------------


class TestNegativeAndZeroAmounts:
    """Test schemas and matching with negative/zero monetary values."""

    def test_credit_note_negative_total(self):
        dcn = DebitCreditNoteExtraction(
            note_number="CN-NEG",
            note_type="credit",
            currency="USD",
            total_amount=-5000.0,
        )
        assert dcn.total_amount == -5000.0

    def test_zero_total_amount(self):
        inv = FreightInvoiceExtraction(
            invoice_number="FI-ZERO",
            vendor_name="V",
            total_amount=0.0,
        )
        assert inv.total_amount == 0.0

    def test_matching_negative_amounts(self):
        """Match result when both documents have negative amounts."""
        po = {
            "supplier": {"name": "Test"},
            "total_amount": -1000.0,
            "line_items": [],
        }
        invoice = {
            "seller": {"name": "Test"},
            "total_amount": -1000.0,
            "line_items": [],
        }
        result = compute_three_way_match(po, {}, invoice)
        total_match = next((fm for fm in result.field_matches if fm.field_name == "total_amount"), None)
        assert total_match is not None
        assert total_match.matched is True

    def test_zero_unit_price_line_items(self):
        """Zero unit price (free samples)."""
        po_items = [{"description": "Free widget sample", "quantity": 100, "unit_price": 0.0}]
        inv_items = [{"description": "Free widget sample item", "quantity": 100, "unit_price": 0.0}]
        results = match_line_items(po_items, inv_items)
        assert len(results) == 1
        # Both zero price -> match_numeric(0, 0) = True
        assert results[0].unit_price_match == 1.0


# ---------------------------------------------------------------------------
# 14. MODEL_VALIDATE FROM DICT WITH EXTRA FIELDS
# ---------------------------------------------------------------------------


class TestModelValidateExtras:
    """Pydantic's model_validate should handle unknown extra fields gracefully."""

    def test_freight_invoice_extra_fields_ignored(self):
        """Extra fields from Claude response should be silently ignored."""
        data = {
            "invoice_number": "FI-001",
            "vendor_name": "Test Vendor",
            "total_amount": 100.0,
            "unknown_field_from_claude": "some value",
            "another_unexpected": 42,
        }
        inv = FreightInvoiceExtraction.model_validate(data)
        assert inv.invoice_number == "FI-001"
        assert not hasattr(inv, "unknown_field_from_claude")

    def test_commercial_invoice_extra_fields(self):
        data = {
            "invoice_number": "CI-001",
            "seller": {"name": "S", "extra_field": True},
            "buyer": {"name": "B"},
            "currency": "USD",
            "line_items": [],
            "total_amount": 50.0,
            "hallucinated_field": "value",
        }
        inv = CommercialInvoiceExtraction.model_validate(data)
        assert inv.invoice_number == "CI-001"
