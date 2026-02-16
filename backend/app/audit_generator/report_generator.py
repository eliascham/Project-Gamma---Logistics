"""Claude-powered audit report generator.

Takes audit events and produces a narrative summary with spend breakdown,
AI vs human decision ratios, and flagged items.
"""

import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.audit import AuditEvent


class AuditReportGenerator:
    """Generates Claude-powered audit-ready summaries from audit events."""

    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    async def generate_report(
        self,
        db: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        entity_type: str | None = None,
    ) -> dict:
        """Generate a narrative audit report from events in the specified range."""
        query = select(AuditEvent).order_by(AuditEvent.created_at.asc())

        if start_date:
            query = query.where(AuditEvent.created_at >= start_date)
        if end_date:
            query = query.where(AuditEvent.created_at <= end_date)
        if entity_type:
            query = query.where(AuditEvent.entity_type == entity_type)

        result = await db.execute(query.limit(500))
        events = list(result.scalars().all())

        if not events:
            return {
                "report": "No audit events found for the specified criteria.",
                "event_count": 0,
                "start_date": start_date,
                "end_date": end_date,
                "model_used": self.model,
                "generated_at": datetime.now(timezone.utc),
            }

        # Format events for Claude
        event_summaries = []
        for e in events:
            summary = (
                f"[{e.created_at}] {e.event_type} | "
                f"Entity: {e.entity_type}/{e.entity_id} | "
                f"Actor: {e.actor} ({e.actor_type}) | "
                f"Action: {e.action}"
            )
            if e.rationale:
                summary += f" | Rationale: {e.rationale}"
            event_summaries.append(summary)

        events_text = "\n".join(event_summaries)

        prompt = (
            "You are an auditor reviewing logistics operations. "
            "Generate a concise, professional audit report based on these events.\n\n"
            "Include:\n"
            "1. Executive summary (2-3 sentences)\n"
            "2. Key statistics (total events, AI vs human decisions)\n"
            "3. Notable actions and patterns\n"
            "4. Any concerns or recommendations\n\n"
            f"Events ({len(events)} total):\n{events_text}"
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        report_text = response.content[0].text

        return {
            "report": report_text,
            "event_count": len(events),
            "start_date": start_date,
            "end_date": end_date,
            "model_used": self.model,
            "generated_at": datetime.now(timezone.utc),
        }
