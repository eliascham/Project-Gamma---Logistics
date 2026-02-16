"""ReconciliationEngine — cross-references TMS/WMS/ERP records.

Flow:
1. Load records from mock_logistics_data (TMS shipments + ERP GL entries)
2. Phase 1: Deterministic matching by reference number
3. Phase 2: Fuzzy matching by amount + date
4. Generate mismatch report
5. Create HITL review items for mismatches
6. Log audit events
"""

import json as json_module
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_generator.service import AuditService
from app.config import Settings
from app.hitl_workflow.triggers import should_review_reconciliation
from app.models.reconciliation import (
    ReconciliationRecord,
    ReconciliationRun,
    ReconciliationStatus,
    RecordSource,
)
from app.models.review import ReviewItem, ReviewItemType, ReviewStatus
from app.reconciliation_engine.matchers import (
    compute_composite_confidence,
    match_by_amount,
    match_by_date,
    match_by_reference,
)


class ReconciliationEngine:
    """Cross-system reconciliation engine."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def run_reconciliation(
        self,
        db: AsyncSession,
        name: str | None = None,
        description: str | None = None,
        run_by: str = "system",
    ) -> ReconciliationRun:
        """Run a full reconciliation pass across TMS and ERP data."""
        start = time.perf_counter()

        # Create the run record
        run = ReconciliationRun(
            id=uuid.uuid4(),
            name=name or f"Reconciliation {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            description=description,
            status=ReconciliationStatus.PENDING,
            run_by=run_by,
        )
        db.add(run)
        await db.flush()

        # Load TMS shipments
        tms_rows = (await db.execute(sa_text(
            "SELECT id, reference_number, data FROM mock_logistics_data "
            "WHERE data_source = 'tms' AND record_type = 'shipment' "
            "ORDER BY created_at DESC LIMIT 500"
        ))).all()

        # Load ERP GL entries
        erp_rows = (await db.execute(sa_text(
            "SELECT id, reference_number, data FROM mock_logistics_data "
            "WHERE data_source = 'erp' AND record_type = 'gl_entry' "
            "ORDER BY created_at DESC LIMIT 500"
        ))).all()

        # Create reconciliation records for TMS
        tms_records: list[ReconciliationRecord] = []
        for row in tms_rows:
            data = row[2] if isinstance(row[2], dict) else json_module.loads(row[2])
            rec = ReconciliationRecord(
                id=uuid.uuid4(),
                run_id=run.id,
                source=RecordSource.TMS,
                record_type="shipment",
                reference_number=row[1],
                record_data=data,
                match_status=ReconciliationStatus.PENDING,
            )
            db.add(rec)
            tms_records.append(rec)

        # Create reconciliation records for ERP
        erp_records: list[ReconciliationRecord] = []
        for row in erp_rows:
            data = row[2] if isinstance(row[2], dict) else json_module.loads(row[2])
            rec = ReconciliationRecord(
                id=uuid.uuid4(),
                run_id=run.id,
                source=RecordSource.ERP,
                record_type="gl_entry",
                reference_number=row[1],
                record_data=data,
                match_status=ReconciliationStatus.PENDING,
            )
            db.add(rec)
            erp_records.append(rec)

        await db.flush()

        # Phase 1: Deterministic matching by reference number
        matched_count = 0
        mismatch_count = 0
        erp_by_ref: dict[str, list[ReconciliationRecord]] = {}
        for erp_rec in erp_records:
            ref = (erp_rec.reference_number or "").strip().lower()
            erp_by_ref.setdefault(ref, []).append(erp_rec)

        for tms_rec in tms_records:
            ref = (tms_rec.reference_number or "").strip().lower()
            matching_erp = erp_by_ref.get(ref, [])

            if matching_erp:
                erp_rec = matching_erp[0]
                tms_data = tms_rec.record_data or {}
                erp_data = erp_rec.record_data or {}

                # Check amount match
                tms_amount = tms_data.get("amount", 0)
                erp_amount = erp_data.get("amount", 0)
                amt_match, amt_conf = match_by_amount(tms_amount, erp_amount)

                # Check date match
                tms_date = tms_data.get("ship_date", "")
                erp_date = erp_data.get("posting_date", "")
                date_match, date_conf = match_by_date(tms_date, erp_date)

                composite = compute_composite_confidence(1.0, amt_conf, date_conf)

                if amt_match:
                    tms_rec.match_status = ReconciliationStatus.MATCHED
                    tms_rec.matched_with_id = erp_rec.id
                    tms_rec.match_confidence = composite
                    tms_rec.match_reasoning = f"Reference match + amount match (TMS: ${tms_amount}, ERP: ${erp_amount})"

                    erp_rec.match_status = ReconciliationStatus.MATCHED
                    erp_rec.matched_with_id = tms_rec.id
                    erp_rec.match_confidence = composite
                    erp_rec.match_reasoning = tms_rec.match_reasoning

                    matched_count += 1
                else:
                    tms_rec.match_status = ReconciliationStatus.MISMATCH
                    tms_rec.matched_with_id = erp_rec.id
                    tms_rec.match_confidence = composite
                    tms_rec.match_reasoning = "Reference matched but amounts differ"
                    tms_rec.mismatch_details = {
                        "tms_amount": tms_amount,
                        "erp_amount": erp_amount,
                        "difference": round(abs(tms_amount - erp_amount), 2),
                    }

                    erp_rec.match_status = ReconciliationStatus.MISMATCH
                    erp_rec.matched_with_id = tms_rec.id
                    erp_rec.match_confidence = composite
                    erp_rec.match_reasoning = tms_rec.match_reasoning
                    erp_rec.mismatch_details = tms_rec.mismatch_details

                    mismatch_count += 1
            else:
                tms_rec.match_status = ReconciliationStatus.MISMATCH
                tms_rec.match_reasoning = "No matching ERP record found"
                mismatch_count += 1

        # Mark unmatched ERP records
        for erp_rec in erp_records:
            status = erp_rec.match_status
            if isinstance(status, ReconciliationStatus):
                status = status.value if hasattr(status, 'value') else str(status)
            if status == "pending":
                erp_rec.match_status = ReconciliationStatus.MISMATCH
                erp_rec.match_reasoning = "No matching TMS record found"
                mismatch_count += 1

        total_records = len(tms_records) + len(erp_records)
        match_rate = matched_count / max(len(tms_records), 1)

        # Determine overall status
        if mismatch_count == 0:
            run.status = ReconciliationStatus.MATCHED
        elif matched_count > 0:
            run.status = ReconciliationStatus.PARTIAL_MATCH
        else:
            run.status = ReconciliationStatus.MISMATCH

        run.total_records = total_records
        run.matched_count = matched_count
        run.mismatch_count = mismatch_count
        run.match_rate = round(match_rate, 4)
        run.processing_time_ms = int((time.perf_counter() - start) * 1000)
        run.summary = {
            "tms_records": len(tms_records),
            "erp_records": len(erp_records),
            "matched": matched_count,
            "mismatched": mismatch_count,
            "match_rate": run.match_rate,
        }

        await db.flush()

        # Create HITL review item if needed
        needs_review, reason = should_review_reconciliation(
            match_confidence=run.match_rate,
            mismatch_count=mismatch_count,
            total_records=total_records,
        )
        if needs_review:
            review_item = ReviewItem(
                id=uuid.uuid4(),
                status=ReviewStatus.PENDING_REVIEW,
                item_type=ReviewItemType.RECONCILIATION_MISMATCH,
                entity_id=run.id,
                entity_type="reconciliation_run",
                title=f"Reconciliation: {mismatch_count} mismatches ({run.match_rate:.0%} match rate)",
                description=reason,
                severity="high" if mismatch_count > 10 else "medium",
                dollar_amount=None,
            )
            db.add(review_item)

        # Audit log
        await AuditService.log_event(
            db,
            event_type="RECONCILIATION_COMPLETED",
            entity_type="reconciliation_run",
            entity_id=run.id,
            action="reconcile",
            actor=run_by,
            actor_type="user" if run_by != "system" else "system",
            new_state={
                "total_records": total_records,
                "matched": matched_count,
                "mismatched": mismatch_count,
                "match_rate": run.match_rate,
            },
        )

        await db.flush()

        # Reload with records
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(ReconciliationRun)
            .options(selectinload(ReconciliationRun.records))
            .where(ReconciliationRun.id == run.id)
        )
        return result.scalar_one()
