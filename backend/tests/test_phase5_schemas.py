"""Tests for Phase 5 extraction schemas — validates all new Pydantic models."""

import pytest
from datetime import date

from app.schemas.extraction import (
    # Enums
    DocumentType,
    EXTRACTION_MODEL_REGISTRY,
    # Shared
    PartyInfo,
    LocationInfo,
    # Existing (verify no regressions)
    FreightInvoiceExtraction,
    LineItem,
    DemurrageDetail,
    BillOfLadingExtraction,
    AddressInfo,
    # P0 types
    CommercialInvoiceExtraction,
    CommercialLineItem,
    PurchaseOrderExtraction,
    POLineItem,
    PackingListExtraction,
    PackingItem,
    # P1 types
    ArrivalNoticeExtraction,
    ArrivalCharge,
    AirWaybillExtraction,
    AWBCharge,
    DebitCreditNoteExtraction,
    AdjustmentLineItem,
    # P2 types
    CustomsEntryExtraction,
    EntryLineItem,
    ProofOfDeliveryExtraction,
    DeliveryItem,
    CertificateOfOriginExtraction,
    OriginItem,
)


class TestDocumentTypeEnum:
    """Test that DocumentType enum has all 12 values."""

    def test_all_types_present(self):
        assert len(DocumentType) == 12
        expected = {
            "freight_invoice", "bill_of_lading", "commercial_invoice",
            "purchase_order", "packing_list", "arrival_notice",
            "air_waybill", "debit_credit_note", "customs_entry",
            "proof_of_delivery", "certificate_of_origin", "unknown",
        }
        actual = {t.value for t in DocumentType}
        assert actual == expected

    def test_registry_covers_all_types_except_unknown(self):
        for dt in DocumentType:
            if dt == DocumentType.UNKNOWN:
                assert dt not in EXTRACTION_MODEL_REGISTRY
            else:
                assert dt in EXTRACTION_MODEL_REGISTRY


class TestPartyInfo:
    """Test the shared PartyInfo sub-model."""

    def test_minimal(self):
        p = PartyInfo(name="Acme Corp")
        assert p.name == "Acme Corp"
        assert p.tax_id is None
        assert p.email is None

    def test_full(self):
        p = PartyInfo(
            name="Acme Corp",
            address="123 Main St",
            city="New York",
            state="NY",
            country="US",
            postal_code="10001",
            tax_id="12-3456789",
            contact_name="John Doe",
            phone="+1-555-0100",
            email="john@acme.com",
        )
        assert p.country == "US"
        assert p.tax_id == "12-3456789"


class TestFreightInvoiceExtraction:
    """Test freight invoice with new Phase 5 fields."""

    def test_backward_compatible(self):
        """Existing freight invoices still work without new fields."""
        inv = FreightInvoiceExtraction(
            invoice_number="FI-001",
            vendor_name="FastShip LLC",
            total_amount=5000.0,
        )
        assert inv.invoice_variant is None
        assert inv.demurrage_details is None

    def test_with_variant(self):
        inv = FreightInvoiceExtraction(
            invoice_number="FI-002",
            vendor_name="FastShip LLC",
            total_amount=1200.0,
            invoice_variant="detention_demurrage",
            demurrage_details=[
                DemurrageDetail(
                    container_number="MSKU1234567",
                    free_time_days=5,
                    daily_rate=150.0,
                    total_chargeable_days=8,
                )
            ],
        )
        assert inv.invoice_variant == "detention_demurrage"
        assert len(inv.demurrage_details) == 1
        assert inv.demurrage_details[0].container_number == "MSKU1234567"


class TestCommercialInvoiceExtraction:
    """Test commercial invoice P0 schema."""

    def test_minimal(self):
        inv = CommercialInvoiceExtraction(
            invoice_number="CI-2025-001",
            seller=PartyInfo(name="Shanghai Export Co"),
            buyer=PartyInfo(name="US Import Inc"),
            currency="USD",
            line_items=[
                CommercialLineItem(
                    description="Widget A", quantity=100, unit="pcs",
                    unit_price=10.0, total=1000.0,
                )
            ],
            total_amount=1000.0,
        )
        assert inv.invoice_number == "CI-2025-001"
        assert inv.seller.name == "Shanghai Export Co"
        assert inv.line_items[0].hs_code is None

    def test_full(self):
        inv = CommercialInvoiceExtraction(
            invoice_number="CI-2025-002",
            invoice_date=date(2025, 6, 15),
            seller=PartyInfo(name="Shanghai Export Co", country="CN", tax_id="CN-12345"),
            buyer=PartyInfo(name="US Import Inc", country="US"),
            country_of_origin="CN",
            currency="USD",
            incoterms="CIF",
            incoterms_location="Los Angeles",
            payment_terms="Net 30",
            line_items=[
                CommercialLineItem(
                    item_number="SKU-001",
                    description="Electronic Components",
                    hs_code="8542310000",
                    country_of_origin="CN",
                    quantity=500,
                    unit="pcs",
                    unit_price=5.50,
                    total=2750.0,
                )
            ],
            freight_charges=450.0,
            insurance_charges=50.0,
            total_amount=3250.0,
            transport_reference="BOL-2025-001",
            invoice_variant="standard",
        )
        assert inv.incoterms == "CIF"
        assert inv.line_items[0].hs_code == "8542310000"
        assert inv.freight_charges == 450.0


class TestPurchaseOrderExtraction:
    """Test purchase order P0 schema."""

    def test_minimal(self):
        po = PurchaseOrderExtraction(
            po_number="PO-2025-100",
            buyer=PartyInfo(name="US Import Inc"),
            supplier=PartyInfo(name="Shanghai Export Co"),
            currency="USD",
            line_items=[
                POLineItem(
                    description="Widget A", quantity=100, unit="pcs",
                    unit_price=10.0, total=1000.0,
                )
            ],
            total_amount=1000.0,
        )
        assert po.po_number == "PO-2025-100"
        assert po.delivery_date is None

    def test_with_all_fields(self):
        po = PurchaseOrderExtraction(
            po_number="PO-2025-101",
            po_date=date(2025, 3, 1),
            buyer=PartyInfo(name="US Import Inc"),
            supplier=PartyInfo(name="Shanghai Export Co"),
            ship_to=PartyInfo(name="Warehouse West", city="Los Angeles"),
            currency="USD",
            incoterms="FOB",
            payment_terms="Net 60",
            delivery_date=date(2025, 5, 1),
            shipping_method="ocean",
            line_items=[
                POLineItem(
                    line_number=1, item_number="SKU-001",
                    description="Widget A", hs_code="8542310000",
                    quantity=100, unit="pcs", unit_price=10.0, total=1000.0,
                )
            ],
            subtotal=1000.0,
            shipping_amount=200.0,
            total_amount=1200.0,
            status="open",
        )
        assert po.shipping_method == "ocean"
        assert po.line_items[0].line_number == 1


class TestPackingListExtraction:
    """Test packing list P0 schema."""

    def test_minimal(self):
        pl = PackingListExtraction(
            items=[
                PackingItem(description="Widget A", quantity=100),
            ],
        )
        assert len(pl.items) == 1
        assert pl.total_packages is None

    def test_full(self):
        pl = PackingListExtraction(
            packing_list_number="PL-001",
            packing_date=date(2025, 4, 1),
            invoice_number="CI-2025-001",
            po_number="PO-2025-100",
            seller=PartyInfo(name="Shanghai Export Co"),
            container_numbers=["MSKU1234567"],
            items=[
                PackingItem(
                    item_number="SKU-001",
                    description="Widget A",
                    quantity=100,
                    unit="pcs",
                    package_type="carton",
                    package_count=10,
                    gross_weight=50.0,
                    net_weight=45.0,
                    dimensions="30 x 20 x 15",
                )
            ],
            total_packages=10,
            total_gross_weight=50.0,
            total_net_weight=45.0,
            weight_unit="kg",
        )
        assert pl.container_numbers == ["MSKU1234567"]
        assert pl.items[0].package_type == "carton"


class TestArrivalNoticeExtraction:
    """Test arrival notice P1 schema."""

    def test_minimal(self):
        an = ArrivalNoticeExtraction()
        assert an.notice_number is None
        assert an.charges == []

    def test_with_charges(self):
        an = ArrivalNoticeExtraction(
            notice_number="AN-001",
            bol_number="BOL-2025-001",
            eta=date(2025, 5, 10),
            charges=[
                ArrivalCharge(charge_type="Ocean Freight", amount=3000.0),
                ArrivalCharge(charge_type="THC", amount=350.0),
            ],
            total_charges=3350.0,
            currency="USD",
            free_time_days=5,
        )
        assert len(an.charges) == 2
        assert an.total_charges == 3350.0


class TestAirWaybillExtraction:
    """Test air waybill P1 schema."""

    def test_minimal(self):
        awb = AirWaybillExtraction(awb_number="17612345678")
        assert awb.awb_number == "17612345678"
        assert awb.awb_type is None

    def test_full(self):
        awb = AirWaybillExtraction(
            awb_number="17612345678",
            awb_type="master",
            issue_date=date(2025, 6, 1),
            airline_code="176",
            airline_name="Emirates SkyCargo",
            shipper=PartyInfo(name="Shanghai Export Co"),
            consignee=PartyInfo(name="US Import Inc"),
            airport_of_departure="PVG - Shanghai Pudong",
            airport_of_destination="LAX - Los Angeles",
            pieces=10,
            gross_weight=500.0,
            chargeable_weight=550.0,
            weight_unit="K",
            freight_charges=2500.0,
            other_charges=[
                AWBCharge(charge_type="Fuel Surcharge", amount=200.0, prepaid_or_collect="PP"),
            ],
            total_charges=2700.0,
            payment_type="PP",
            currency="USD",
        )
        assert awb.chargeable_weight == 550.0
        assert len(awb.other_charges) == 1


class TestDebitCreditNoteExtraction:
    """Test debit/credit note P1 schema."""

    def test_credit_note(self):
        cn = DebitCreditNoteExtraction(
            note_number="CN-001",
            note_type="credit",
            original_invoice_number="FI-001",
            currency="USD",
            line_items=[
                AdjustmentLineItem(
                    description="Overcharge on ocean freight",
                    original_amount=3000.0,
                    adjusted_amount=2800.0,
                    difference=-200.0,
                )
            ],
            total_amount=-200.0,
        )
        assert cn.note_type == "credit"
        assert cn.line_items[0].difference == -200.0

    def test_debit_note(self):
        dn = DebitCreditNoteExtraction(
            note_number="DN-001",
            note_type="debit",
            currency="USD",
            total_amount=150.0,
        )
        assert dn.note_type == "debit"


class TestCustomsEntryExtraction:
    """Test CBP 7501 P2 schema."""

    def test_minimal(self):
        ce = CustomsEntryExtraction(
            entry_number="12345678901",
            line_items=[
                EntryLineItem(
                    hts_number="8542310000",
                    description="Integrated circuits",
                    entered_value=25000.0,
                )
            ],
        )
        assert ce.entry_number == "12345678901"
        assert ce.total_duty is None

    def test_full(self):
        ce = CustomsEntryExtraction(
            entry_number="12345678901",
            entry_type="01",
            summary_date=date(2025, 7, 1),
            port_code="2704",
            country_of_origin="CN",
            importer_name="US Import Inc",
            bol_or_awb="BOL-2025-001",
            line_items=[
                EntryLineItem(
                    line_number=1,
                    hts_number="8542310000",
                    description="Integrated circuits",
                    country_of_origin="CN",
                    quantity=500,
                    unit="NO",
                    entered_value=25000.0,
                    duty_rate=0.035,
                    duty_amount=875.0,
                )
            ],
            total_entered_value=25000.0,
            total_duty=875.0,
            total_other=120.0,
            total_amount=995.0,
        )
        assert ce.line_items[0].duty_rate == 0.035
        assert ce.total_other == 120.0


class TestProofOfDeliveryExtraction:
    """Test proof of delivery P2 schema."""

    def test_minimal(self):
        pod = ProofOfDeliveryExtraction()
        assert pod.receiver_signature is False
        assert pod.has_photo is False

    def test_full(self):
        pod = ProofOfDeliveryExtraction(
            pod_number="POD-001",
            delivery_date=date(2025, 5, 15),
            delivery_time="14:30",
            carrier_name="FastTruck LLC",
            bol_number="BOL-2025-001",
            items=[
                DeliveryItem(
                    description="Widget A",
                    quantity_expected=100,
                    quantity_delivered=98,
                    condition="good",
                )
            ],
            total_packages=10,
            receiver_name="Jane Smith",
            receiver_signature=True,
            condition="good",
        )
        assert pod.receiver_signature is True
        assert pod.items[0].quantity_delivered == 98


class TestCertificateOfOriginExtraction:
    """Test certificate of origin P2 schema."""

    def test_minimal(self):
        co = CertificateOfOriginExtraction(
            country_of_origin="CN",
            items=[
                OriginItem(description="Electronic Components"),
            ],
        )
        assert co.country_of_origin == "CN"
        assert co.certificate_type is None

    def test_full(self):
        co = CertificateOfOriginExtraction(
            certificate_number="CO-2025-001",
            issue_date=date(2025, 4, 1),
            certificate_type="General",
            exporter=PartyInfo(name="Shanghai Export Co"),
            importer=PartyInfo(name="US Import Inc"),
            country_of_origin="CN",
            country_of_destination="US",
            invoice_number="CI-2025-001",
            items=[
                OriginItem(
                    description="Electronic Components",
                    hs_code="8542310000",
                    quantity=500,
                    unit="pcs",
                    origin_criterion="WO",
                    country_of_origin="CN",
                )
            ],
            origin_criterion="WO",
            issuing_authority="China Council for the Promotion of International Trade",
            certifier_name="Wang Wei",
            certification_date=date(2025, 4, 1),
        )
        assert co.certificate_type == "General"
        assert co.items[0].origin_criterion == "WO"


class TestModelValidation:
    """Test that model_validate works for dict data (as used in extraction pipeline)."""

    def test_commercial_invoice_from_dict(self):
        data = {
            "invoice_number": "CI-001",
            "seller": {"name": "Test Seller"},
            "buyer": {"name": "Test Buyer"},
            "currency": "EUR",
            "line_items": [
                {"description": "Item 1", "quantity": 10, "unit": "pcs", "unit_price": 5.0, "total": 50.0}
            ],
            "total_amount": 50.0,
        }
        inv = CommercialInvoiceExtraction.model_validate(data)
        assert inv.seller.name == "Test Seller"
        assert inv.currency == "EUR"

    def test_purchase_order_from_dict(self):
        data = {
            "po_number": "PO-001",
            "buyer": {"name": "Buyer Co"},
            "supplier": {"name": "Supplier Co"},
            "currency": "USD",
            "line_items": [
                {"description": "Part A", "quantity": 50, "unit": "ea", "unit_price": 20.0, "total": 1000.0}
            ],
            "total_amount": 1000.0,
        }
        po = PurchaseOrderExtraction.model_validate(data)
        assert po.supplier.name == "Supplier Co"

    def test_customs_entry_from_dict(self):
        data = {
            "entry_number": "99988877766",
            "line_items": [
                {"hts_number": "8542310000", "description": "ICs", "entered_value": 10000.0}
            ],
        }
        ce = CustomsEntryExtraction.model_validate(data)
        assert ce.entry_number == "99988877766"
