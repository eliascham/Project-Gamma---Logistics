"""AnomalyFlagger — orchestrates all anomaly detection strategies on a document.

Detectors:
1. Duplicate invoice (same invoice# + vendor within window)
2. Budget overrun (project spend vs budget, configurable threshold)
3. Misallocated cost (low confidence line items)
4. Missing approval (high-value without HITL sign-off)

Creates AnomalyFlag records and triggers HITL review items.
"""

import json as json_module
import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.anomaly_flagger.detectors import (
    detect_budget_overrun,
    detect_duplicate,
    detect_low_confidence_items,
)
from app.audit_generator.service import AuditService
from app.config import Settings
from app.hitl_workflow.triggers import should_review_anomaly
from app.models.anomaly import AnomalyFlag, AnomalySeverity, AnomalyType
from app.models.cost_allocation import AllocationStatus, CostAllocation, LineItemStatus
from app.models.mock_data import ProjectBudget
from app.models.review import ReviewItem, ReviewItemType, ReviewStatus


class AnomalyFlagger:
    """Orchestrates anomaly detection across all strategies."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.budget_threshold = settings.anomaly_budget_overrun_threshold
        self.duplicate_window = settings.anomaly_duplicate_window_days
        self.confidence_threshold = settings.allocation_confidence_threshold

    async def scan(
        self,
        db: AsyncSession,
        document_id: uuid.UUID | None = None,
    ) -> list[AnomalyFlag]:
        """Run all anomaly detection strategies. Returns list of new anomalies found."""
        anomalies: list[AnomalyFlag] = []

        # Get allocations to scan
        query = (
            select(CostAllocation)
            .options(selectinload(CostAllocation.line_items))
        )
        if document_id:
            query = query.where(CostAllocation.document_id == document_id)

        result = await db.execute(query)
        allocations = list(result.scalars().all())

        for alloc in allocations:
            # 1. Duplicate invoice detection
            dupes = await self._check_duplicate(db, alloc)
            anomalies.extend(dupes)

            # 2. Budget overrun detection
            overruns = await self._check_budget_overrun(db, alloc)
            anomalies.extend(overruns)

            # 3. Low confidence (misallocated cost)
            low_conf = await self._check_low_confidence(db, alloc)
            anomalies.extend(low_conf)

            # 4. Missing approval
            missing = await self._check_missing_approval(db, alloc)
            anomalies.extend(missing)

        # Create HITL review items for anomalies that need review
        for anomaly in anomalies:
            severity = anomaly.severity.value if isinstance(anomaly.severity, AnomalySeverity) else anomaly.severity
            atype = anomaly.anomaly_type.value if isinstance(anomaly.anomaly_type, AnomalyType) else anomaly.anomaly_type
            needs_review, reason = should_review_anomaly(severity, atype)
            if needs_review:
                review_item = ReviewItem(
                    id=uuid.uuid4(),
                    status=ReviewStatus.PENDING_REVIEW,
                    item_type=ReviewItemType.ANOMALY,
                    entity_id=anomaly.id,
                    entity_type="anomaly_flag",
                    title=anomaly.title,
                    description=anomaly.description,
                    severity=severity,
                )
                db.add(review_item)
                await db.flush()
                anomaly.review_item_id = review_item.id

        await db.flush()

        # Log audit event
        if anomalies:
            await AuditService.log_event(
                db,
                event_type="ANOMALY_SCAN_COMPLETED",
                entity_type="anomaly_scan",
                action="scan",
                actor="system",
                actor_type="ai",
                new_state={
                    "anomalies_found": len(anomalies),
                    "document_id": str(document_id) if document_id else None,
                },
            )

        return anomalies

    async def _check_duplicate(self, db: AsyncSession, alloc: CostAllocation) -> list[AnomalyFlag]:
        """Check for duplicate invoices."""
        if not alloc.document_id:
            return []

        # Get invoice number from extraction
        ext_row = (await db.execute(
            sa_text(
                "SELECT extraction_data FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": alloc.document_id},
        )).first()

        if not ext_row:
            return []

        data = ext_row[0]
        if isinstance(data, str):
            data = json_module.loads(data)

        invoice_number = data.get("invoice_number", "")
        vendor = data.get("vendor", data.get("shipper", ""))
        if not invoice_number:
            return []

        # Check for existing extractions with same invoice number
        existing = (await db.execute(
            sa_text(
                "SELECT document_id, extraction_data FROM extractions "
                "WHERE document_id != :doc_id "
                "ORDER BY created_at DESC LIMIT 100"
            ),
            {"doc_id": alloc.document_id},
        )).all()

        existing_invoices = []
        for row in existing:
            d = row[1]
            if isinstance(d, str):
                d = json_module.loads(d)
            existing_invoices.append({
                "invoice_number": d.get("invoice_number", ""),
                "vendor": d.get("vendor", d.get("shipper", "")),
                "document_id": str(row[0]),
            })

        dup = detect_duplicate(invoice_number, vendor, existing_invoices, self.duplicate_window)
        if dup:
            anomaly = AnomalyFlag(
                id=uuid.uuid4(),
                document_id=alloc.document_id,
                allocation_id=alloc.id,
                anomaly_type=AnomalyType.DUPLICATE_INVOICE,
                severity=AnomalySeverity.HIGH,
                title=f"Duplicate invoice: {invoice_number}",
                description=f"Invoice {invoice_number} from {vendor} already exists",
                details=dup,
            )
            db.add(anomaly)
            return [anomaly]
        return []

    async def _check_budget_overrun(self, db: AsyncSession, alloc: CostAllocation) -> list[AnomalyFlag]:
        """Check for budget overruns across project codes."""
        anomalies = []
        if not alloc.line_items:
            return anomalies

        # Group by project code
        project_amounts: dict[str, float] = {}
        for li in alloc.line_items:
            code = li.override_project_code or li.project_code
            if code:
                project_amounts[code] = project_amounts.get(code, 0) + li.amount

        for code, amount in project_amounts.items():
            budget = (await db.execute(
                select(ProjectBudget).where(ProjectBudget.project_code == code)
            )).scalar_one_or_none()

            if not budget:
                continue

            overrun = detect_budget_overrun(
                code, amount, budget.budget_amount, budget.spent_amount, self.budget_threshold,
            )
            if overrun:
                anomaly = AnomalyFlag(
                    id=uuid.uuid4(),
                    document_id=alloc.document_id,
                    allocation_id=alloc.id,
                    anomaly_type=AnomalyType.BUDGET_OVERRUN,
                    severity=AnomalySeverity.HIGH if overrun["overrun_pct"] > 20 else AnomalySeverity.MEDIUM,
                    title=f"Budget overrun: {code} ({overrun['overrun_pct']}% over)",
                    description=(
                        f"Project {code} would be {overrun['overrun_pct']}% over budget "
                        f"(${overrun['projected_total']:,.2f} vs ${budget.budget_amount:,.2f} budget)"
                    ),
                    details=overrun,
                )
                db.add(anomaly)
                anomalies.append(anomaly)

        return anomalies

    async def _check_low_confidence(self, db: AsyncSession, alloc: CostAllocation) -> list[AnomalyFlag]:
        """Check for low-confidence line items."""
        if not alloc.line_items:
            return []

        items = [
            {
                "index": li.line_item_index,
                "description": li.description,
                "amount": li.amount,
                "confidence": li.confidence or 1.0,
            }
            for li in alloc.line_items
        ]

        flagged = detect_low_confidence_items(items, self.confidence_threshold)
        if not flagged:
            return []

        total_flagged_amount = sum(f["amount"] for f in flagged)
        anomaly = AnomalyFlag(
            id=uuid.uuid4(),
            document_id=alloc.document_id,
            allocation_id=alloc.id,
            anomaly_type=AnomalyType.MISALLOCATED_COST,
            severity=AnomalySeverity.MEDIUM,
            title=f"Low confidence allocation: {len(flagged)} line items below threshold",
            description=(
                f"{len(flagged)} line items totaling ${total_flagged_amount:,.2f} have confidence "
                f"below {self.confidence_threshold}"
            ),
            details={"flagged_items": flagged},
        )
        db.add(anomaly)
        return [anomaly]

    async def _check_missing_approval(self, db: AsyncSession, alloc: CostAllocation) -> list[AnomalyFlag]:
        """Check for high-value allocations without approval."""
        if not alloc.total_amount:
            return []

        if alloc.total_amount < self.settings.hitl_high_risk_dollar_threshold:
            return []

        status = alloc.status.value if isinstance(alloc.status, AllocationStatus) else alloc.status
        if status in ("approved",):
            return []

        anomaly = AnomalyFlag(
            id=uuid.uuid4(),
            document_id=alloc.document_id,
            allocation_id=alloc.id,
            anomaly_type=AnomalyType.MISSING_APPROVAL,
            severity=AnomalySeverity.HIGH,
            title=f"Missing approval: ${alloc.total_amount:,.2f} allocation",
            description=(
                f"High-value allocation of ${alloc.total_amount:,.2f} has not been approved "
                f"(current status: {status})"
            ),
            details={
                "total_amount": alloc.total_amount,
                "status": status,
                "threshold": self.settings.hitl_high_risk_dollar_threshold,
            },
        )
        db.add(anomaly)
        return [anomaly]

    async def generate_audit_summary(self, db: AsyncSession) -> dict:
        """Generate a Claude-powered audit summary of all anomalies."""
        result = await db.execute(
            select(AnomalyFlag).order_by(AnomalyFlag.created_at.desc()).limit(100)
        )
        anomalies = list(result.scalars().all())

        if not anomalies:
            return {
                "summary": "No anomalies detected in the system.",
                "total_anomalies": 0,
                "total_spend": 0.0,
                "model_used": self.model,
                "generated_at": datetime.now(timezone.utc),
            }

        lines = []
        for a in anomalies:
            atype = a.anomaly_type.value if isinstance(a.anomaly_type, AnomalyType) else a.anomaly_type
            sev = a.severity.value if isinstance(a.severity, AnomalySeverity) else a.severity
            lines.append(f"- [{sev.upper()}] {atype}: {a.title}")

        prompt = (
            "You are a logistics auditor. Summarize these anomalies concisely for a compliance report.\n"
            "Include: total count, breakdown by type/severity, key concerns, and recommendations.\n\n"
            f"Anomalies ({len(anomalies)} total):\n" + "\n".join(lines)
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        return {
            "summary": response.content[0].text,
            "total_anomalies": len(anomalies),
            "total_spend": 0.0,
            "model_used": self.model,
            "generated_at": datetime.now(timezone.utc),
        }
