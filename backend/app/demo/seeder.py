"""DemoDataSeeder — creates end-to-end demo data for the vertical slice.

Seeds 5 sample freight invoices with matching shipment records so the
full pipeline can be demonstrated:
  Document → Extraction → Validation → Reconciliation → HITL Review

Each invoice has a corresponding shipment with matched PO numbers,
vendors, and amounts (with deliberate variations for demo scenarios).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.mock_data import MockLogisticsData
from app.models.reconciliation import RecordSource


# ── Demo invoice scenarios ──

DEMO_INVOICES = [
    {
        "id": "d0000001-0001-4000-a000-000000000001",
        "filename": "maersk_freight_inv_2025_001.csv",
        "vendor_name": "Maersk Line LLC",
        "invoice_number": "INV-MAE-70001",
        "invoice_date": "2025-11-15",
        "po_number": "PO-2025-0001",
        "total_amount": 12500.00,
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight - Shanghai to Los Angeles", "amount": 9500.00, "charge_type": "ocean_freight"},
            {"description": "Documentation Fee", "amount": 250.00, "charge_type": "documentation"},
            {"description": "BAF Surcharge", "amount": 1800.00, "charge_type": "fuel_surcharge"},
            {"description": "Terminal Handling", "amount": 950.00, "charge_type": "terminal_handling"},
        ],
        "scenario": "perfect_match",
    },
    {
        "id": "d0000001-0002-4000-a000-000000000002",
        "filename": "msc_freight_inv_2025_002.csv",
        "vendor_name": "MSC Mediterranean Shipping",
        "invoice_number": "INV-MSC-80002",
        "invoice_date": "2025-11-18",
        "po_number": "PO-2025-0002",
        "total_amount": 18750.00,
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight - Rotterdam to New York", "amount": 14200.00, "charge_type": "ocean_freight"},
            {"description": "Customs Brokerage", "amount": 850.00, "charge_type": "customs_brokerage"},
            {"description": "Drayage - Port to Warehouse", "amount": 2200.00, "charge_type": "drayage"},
            {"description": "Insurance", "amount": 1500.00, "charge_type": "insurance"},
        ],
        "scenario": "amount_mismatch",
    },
    {
        "id": "d0000001-0003-4000-a000-000000000003",
        "filename": "cosco_freight_inv_2025_003.csv",
        "vendor_name": "COSCO Shipping Lines",
        "invoice_number": "INV-COS-90003",
        "invoice_date": "2025-11-20",
        "po_number": "PO-2025-0003",
        "total_amount": 7200.00,
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight - Shenzhen to Long Beach", "amount": 5800.00, "charge_type": "ocean_freight"},
            {"description": "Documentation Fee", "amount": 200.00, "charge_type": "documentation"},
            {"description": "Container Cleaning", "amount": 350.00, "charge_type": "handling"},
            {"description": "AMS Filing Fee", "amount": 850.00, "charge_type": "documentation"},
        ],
        "scenario": "no_match",
    },
    {
        "id": "d0000001-0004-4000-a000-000000000004",
        "filename": "hapag_freight_inv_2025_004.csv",
        "vendor_name": "Hapag-Lloyd AG",
        "invoice_number": "INV-HAP-60004",
        "invoice_date": "2025-11-22",
        "po_number": "PO-2025-0004",
        "total_amount": 32000.00,
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight - Hamburg to Charleston", "amount": 24000.00, "charge_type": "ocean_freight"},
            {"description": "Demurrage - 3 days", "amount": 4500.00, "charge_type": "demurrage"},
            {"description": "Chassis Usage", "amount": 1200.00, "charge_type": "equipment"},
            {"description": "Port Congestion Surcharge", "amount": 2300.00, "charge_type": "surcharge"},
        ],
        "scenario": "high_value_review",
    },
    {
        "id": "d0000001-0005-4000-a000-000000000005",
        "filename": "evergreen_freight_inv_2025_005.csv",
        "vendor_name": "Evergreen Marine Corp",
        "invoice_number": "INV-EVG-50005",
        "invoice_date": "2025-11-25",
        "po_number": "PO-2025-0005",
        "total_amount": 9800.00,
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight - Kaohsiung to Oakland", "amount": 7600.00, "charge_type": "ocean_freight"},
            {"description": "CAF Surcharge", "amount": 1200.00, "charge_type": "fuel_surcharge"},
            {"description": "Seal Fee", "amount": 50.00, "charge_type": "handling"},
            {"description": "B/L Fee", "amount": 950.00, "charge_type": "documentation"},
        ],
        "scenario": "close_candidates",
    },
]

# ── Matching shipments (one per invoice, with scenario-specific variations) ──

DEMO_SHIPMENTS = [
    {
        # Perfect match for invoice 1
        "reference_number": "SHP-DEMO-0001",
        "bol_number": "BOL-DEMO-700001",
        "po_number": "PO-2025-0001",
        "carrier": "Maersk Line LLC",
        "origin": "Shanghai",
        "destination": "Los Angeles",
        "ship_date": "2025-11-12",
        "amount": 12500.00,
        "status": "delivered",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "CC-INTL",
    },
    {
        # Amount mismatch for invoice 2 (shipment shows $17,900 vs invoice $18,750)
        "reference_number": "SHP-DEMO-0002",
        "bol_number": "BOL-DEMO-800002",
        "po_number": "PO-2025-0002",
        "carrier": "MSC",  # Slightly different name
        "origin": "Rotterdam",
        "destination": "New York",
        "ship_date": "2025-11-14",
        "amount": 17900.00,
        "status": "delivered",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "CC-INTL",
    },
    {
        # Unrelated shipment (for no-match scenario on invoice 3)
        "reference_number": "SHP-DEMO-0003",
        "bol_number": "BOL-DEMO-900003",
        "po_number": "PO-2025-9999",  # Different PO
        "carrier": "CMA CGM",  # Different carrier
        "origin": "Singapore",
        "destination": "Savannah",
        "ship_date": "2025-06-01",  # Far away date
        "amount": 22000.00,
        "status": "delivered",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "CC-INTL",
    },
    {
        # High-value match for invoice 4
        "reference_number": "SHP-DEMO-0004",
        "bol_number": "BOL-DEMO-600004",
        "po_number": "PO-2025-0004",
        "carrier": "Hapag-Lloyd",
        "origin": "Hamburg",
        "destination": "Charleston",
        "ship_date": "2025-11-18",
        "amount": 32000.00,
        "status": "customs_hold",
        "project_code": "SPEC-PROJ-005",
        "cost_center": "CC-SPEC",
    },
    {
        # Close candidate A for invoice 5
        "reference_number": "SHP-DEMO-0005A",
        "bol_number": "BOL-DEMO-500005",
        "po_number": "PO-2025-0005",
        "carrier": "Evergreen Marine",
        "origin": "Kaohsiung",
        "destination": "Oakland",
        "ship_date": "2025-11-22",
        "amount": 9800.00,
        "status": "delivered",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "CC-INTL",
    },
    {
        # Close candidate B for invoice 5 (same PO, similar amount)
        "reference_number": "SHP-DEMO-0005B",
        "bol_number": "BOL-DEMO-500006",
        "po_number": "PO-2025-0005",
        "carrier": "Evergreen Marine Corp",
        "origin": "Kaohsiung",
        "destination": "Oakland",
        "ship_date": "2025-11-23",
        "amount": 9750.00,
        "status": "delivered",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "CC-INTL",
    },
]


class DemoDataSeeder:
    """Seeds end-to-end demo data for the invoice reconciliation vertical slice."""

    async def seed(self, db: AsyncSession) -> dict:
        """Seed all demo data. Returns summary counts."""
        # Check if already seeded
        existing = (await db.execute(
            select(func.count(Document.id)).where(
                Document.filename.like("%freight_inv%")
            )
        )).scalar_one()
        if existing > 0:
            return {
                "documents": existing,
                "extractions": 0,
                "shipments": 0,
                "message": "Demo data already seeded",
            }

        doc_count = 0
        ext_count = 0
        ship_count = 0

        # Seed documents and extractions
        for inv in DEMO_INVOICES:
            doc_id = uuid.UUID(inv["id"])

            # Create document record
            doc = Document(
                id=doc_id,
                filename=inv["filename"],
                original_filename=inv["filename"],
                file_path=f"/demo/{inv['filename']}",
                file_type="csv",
                mime_type="text/csv",
                file_size=2048,
                status=DocumentStatus.EXTRACTED,
                document_type="freight_invoice",
                page_count=1,
            )
            db.add(doc)
            await db.flush()  # Flush so document row exists for extraction FK
            doc_count += 1

            # Create extraction record (raw SQL since no ORM model)
            ext_id = uuid.uuid4()
            extraction_data = {
                "invoice_number": inv["invoice_number"],
                "invoice_date": inv["invoice_date"],
                "vendor_name": inv["vendor_name"],
                "po_number": inv["po_number"],
                "total_amount": inv["total_amount"],
                "currency": inv["currency"],
                "line_items": inv["line_items"],
            }

            await db.execute(sa_text("""
                INSERT INTO extractions (id, document_id, document_type,
                    extraction_data, model_used, processing_time_ms, metadata, created_at)
                VALUES (
                    :ext_id,
                    :doc_id,
                    :doc_type,
                    :ext_data,
                    :model,
                    :time_ms,
                    :metadata,
                    CURRENT_TIMESTAMP
                )
            """), {
                "ext_id": str(ext_id),
                "doc_id": str(doc_id),
                "doc_type": "freight_invoice",
                "ext_data": _json_str(extraction_data),
                "model": "demo-seeder",
                "time_ms": 0,
                "metadata": _json_str({"scenario": inv["scenario"], "demo": True}),
            })
            ext_count += 1

        # Seed matching shipments
        for ship in DEMO_SHIPMENTS:
            db.add(MockLogisticsData(
                id=uuid.uuid4(),
                data_source=RecordSource.TMS,
                record_type="shipment",
                reference_number=ship["reference_number"],
                data=ship,
            ))
            ship_count += 1

        await db.flush()

        return {
            "documents": doc_count,
            "extractions": ext_count,
            "shipments": ship_count,
            "scenarios": [inv["scenario"] for inv in DEMO_INVOICES],
            "message": "Demo data seeded successfully",
        }


def _json_str(obj) -> str:
    """Convert dict to JSON string for raw SQL insertion."""
    import json
    return json.dumps(obj)


def get_demo_invoice_ids() -> list[str]:
    """Return the fixed demo invoice document IDs for scripting."""
    return [inv["id"] for inv in DEMO_INVOICES]


def get_demo_scenarios() -> list[dict]:
    """Return demo scenario descriptions for documentation."""
    return [
        {
            "document_id": inv["id"],
            "filename": inv["filename"],
            "scenario": inv["scenario"],
            "vendor": inv["vendor_name"],
            "amount": inv["total_amount"],
            "description": _scenario_description(inv["scenario"]),
        }
        for inv in DEMO_INVOICES
    ]


def _scenario_description(scenario: str) -> str:
    return {
        "perfect_match": "Invoice matches shipment exactly — PO, vendor, amount all align. Auto-approve expected.",
        "amount_mismatch": "Invoice total differs from shipment ($18,750 vs $17,900). Vendor name slight variation. Triggers review.",
        "no_match": "No matching shipment for this invoice PO. Creates exception for manual investigation.",
        "high_value_review": "$32K invoice with demurrage charges. High-value threshold triggers mandatory review.",
        "close_candidates": "Two shipments match the same PO — ambiguous match requires human decision.",
    }.get(scenario, scenario)
