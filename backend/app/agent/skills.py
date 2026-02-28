"""User-invocable skills — pre-built agent workflows.

Skills are structured goals with pre-configured agent types and context.
They provide convenient shortcuts for common operations:

- /process-invoice <document_id>: Full pipeline (extract → validate → reconcile → review)
- /review-queue: Check pending review items and summarize
- /reconcile <document_id>: Just the reconciliation step
- /extract <document_id>: Just extraction + validation
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import ToolExecutor
from app.agent.orchestrator import run_agent, run_sub_agent, AgentResult
from app.config import Settings

logger = logging.getLogger("gamma.agent.skills")


@dataclass
class SkillSpec:
    """Specification for a user-invocable skill."""
    name: str
    description: str
    agent_type: str | None  # None = use main agent, else sub-agent
    goal_template: str
    requires_document_id: bool = False


SKILL_REGISTRY: dict[str, SkillSpec] = {
    "process-invoice": SkillSpec(
        name="process-invoice",
        description=(
            "End-to-end invoice processing: extract structured data, validate, "
            "reconcile against shipments, and create review items if needed."
        ),
        agent_type=None,  # Use main agent (needs all tools)
        goal_template=(
            "Process the invoice document {document_id} through the full pipeline:\n"
            "1. Get document info and check if extraction exists\n"
            "2. If not extracted, run extraction\n"
            "3. Review confidence scores and validation results\n"
            "4. Search for matching shipments and run reconciliation\n"
            "5. If auto-match: log success audit event\n"
            "6. If no auto-match: create a review item with candidates\n"
            "7. Provide a clear summary of the results"
        ),
        requires_document_id=True,
    ),
    "review-queue": SkillSpec(
        name="review-queue",
        description=(
            "Check the HITL review queue for pending items and provide a summary."
        ),
        agent_type="audit",
        goal_template=(
            "Check the review queue for pending items. "
            "Summarize how many items are pending, their types, severities, "
            "and total dollar amounts at risk. Highlight any critical items."
        ),
        requires_document_id=False,
    ),
    "reconcile": SkillSpec(
        name="reconcile",
        description=(
            "Reconcile an invoice against shipments. Gets the extraction, "
            "searches for candidate shipments, and runs matching."
        ),
        agent_type="reconciliation",
        goal_template=(
            "Reconcile invoice document {document_id} against shipments:\n"
            "1. Get the extraction data for this document\n"
            "2. Search for candidate shipments\n"
            "3. Run reconciliation\n"
            "4. Report results: best match, score, diffs, and whether auto-match is possible"
        ),
        requires_document_id=True,
    ),
    "extract": SkillSpec(
        name="extract",
        description=(
            "Extract structured data from a document and validate."
        ),
        agent_type="extraction",
        goal_template=(
            "Extract and validate document {document_id}:\n"
            "1. Get document info\n"
            "2. Run extraction\n"
            "3. Report: document type, key fields, confidence scores, validation status"
        ),
        requires_document_id=True,
    ),
}


async def run_skill(
    skill_name: str,
    session: AsyncSession,
    settings: Settings,
    document_id: str | None = None,
    extra_context: dict | None = None,
) -> AgentResult:
    """Run a user-invocable skill.

    Args:
        skill_name: Skill name (e.g., "process-invoice").
        session: Database session.
        settings: App settings.
        document_id: Document UUID (required for some skills).
        extra_context: Optional additional context.

    Returns:
        AgentResult with the skill execution result.
    """
    if skill_name not in SKILL_REGISTRY:
        return AgentResult(
            goal=f"/{skill_name}",
            success=False,
            summary=f"Unknown skill: {skill_name}. Available: {list(SKILL_REGISTRY.keys())}",
            error="unknown_skill",
        )

    spec = SKILL_REGISTRY[skill_name]

    if spec.requires_document_id and not document_id:
        return AgentResult(
            goal=f"/{skill_name}",
            success=False,
            summary=f"Skill '{skill_name}' requires a document_id.",
            error="missing_document_id",
        )

    # Build goal from template
    goal = spec.goal_template.format(document_id=document_id or "N/A")

    # Build context
    context = extra_context or {}
    if document_id:
        context["document_id"] = document_id

    executor = ToolExecutor(session=session, settings=settings)
    try:
        if spec.agent_type:
            return await run_sub_agent(
                agent_type=spec.agent_type,
                goal=goal,
                executor=executor,
                settings=settings,
                context=context,
            )
        else:
            return await run_agent(
                goal=goal,
                executor=executor,
                settings=settings,
                context=context,
            )
    finally:
        await executor.close()
