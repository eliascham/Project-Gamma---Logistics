"""Agent API — invoke the invoice processing agent."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import ToolExecutor
from app.agent.orchestrator import run_agent, run_sub_agent, AgentResult
from app.agent.sub_agents import SUB_AGENT_REGISTRY
from app.config import settings
from app.database import get_db

logger = logging.getLogger("gamma.api.agent")

router = APIRouter()


class AgentRequest(BaseModel):
    """Request to invoke the agent."""
    goal: str = Field(..., description="Natural language description of what to do")
    document_id: str | None = Field(None, description="Optional document UUID for context")
    context: dict | None = Field(None, description="Optional additional context")
    max_turns: int = Field(15, ge=1, le=30, description="Maximum agent turns")


class AgentStepResponse(BaseModel):
    turn: int
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_result: dict | None = None
    assistant_text: str | None = None
    duration_ms: int = 0


class AgentResponse(BaseModel):
    goal: str
    success: bool
    summary: str
    steps: list[AgentStepResponse] = []
    total_duration_ms: int = 0
    turns_used: int = 0
    tool_calls_made: int = 0
    error: str | None = None


@router.post("/run", response_model=AgentResponse)
async def run_agent_endpoint(
    request: AgentRequest,
    session: AsyncSession = Depends(get_db),
):
    """Run the invoice processing agent.

    The agent autonomously decides which tools to call based on the goal.
    Typical goals:
    - "Process invoice document {document_id}"
    - "Reconcile invoice {document_id} against shipments"
    - "Check the review queue for pending items"
    """
    context = request.context or {}
    if request.document_id:
        context["document_id"] = request.document_id

    executor = ToolExecutor(session=session, settings=settings)
    try:
        result = await run_agent(
            goal=request.goal,
            executor=executor,
            settings=settings,
            context=context,
            max_turns=request.max_turns,
        )

        return AgentResponse(
            goal=result.goal,
            success=result.success,
            summary=result.summary,
            steps=[
                AgentStepResponse(
                    turn=s.turn,
                    tool_name=s.tool_name,
                    tool_input=s.tool_input,
                    tool_result=s.tool_result,
                    assistant_text=s.assistant_text,
                    duration_ms=s.duration_ms,
                )
                for s in result.steps
            ],
            total_duration_ms=result.total_duration_ms,
            turns_used=result.turns_used,
            tool_calls_made=result.tool_calls_made,
            error=result.error,
        )
    finally:
        await executor.close()


class SubAgentRequest(BaseModel):
    """Request to invoke a specialized sub-agent."""
    agent_type: str = Field(..., description="Sub-agent type: extraction, reconciliation, or audit")
    goal: str = Field(..., description="Task for the sub-agent")
    document_id: str | None = Field(None, description="Optional document UUID")
    context: dict | None = Field(None, description="Optional additional context")
    max_turns: int = Field(10, ge=1, le=20, description="Maximum sub-agent turns")


@router.post("/sub-agent", response_model=AgentResponse)
async def run_sub_agent_endpoint(
    request: SubAgentRequest,
    session: AsyncSession = Depends(get_db),
):
    """Run a specialized sub-agent.

    Available agent types:
    - extraction: Extract and validate documents
    - reconciliation: Match invoices to shipments
    - audit: Audit trail and compliance checks
    """
    if request.agent_type not in SUB_AGENT_REGISTRY:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type '{request.agent_type}'. "
                   f"Available: {list(SUB_AGENT_REGISTRY.keys())}",
        )

    context = request.context or {}
    if request.document_id:
        context["document_id"] = request.document_id

    executor = ToolExecutor(session=session, settings=settings)
    try:
        result = await run_sub_agent(
            agent_type=request.agent_type,
            goal=request.goal,
            executor=executor,
            settings=settings,
            context=context,
            max_turns=request.max_turns,
        )

        return AgentResponse(
            goal=result.goal,
            success=result.success,
            summary=result.summary,
            steps=[
                AgentStepResponse(
                    turn=s.turn,
                    tool_name=s.tool_name,
                    tool_input=s.tool_input,
                    tool_result=s.tool_result,
                    assistant_text=s.assistant_text,
                    duration_ms=s.duration_ms,
                )
                for s in result.steps
            ],
            total_duration_ms=result.total_duration_ms,
            turns_used=result.turns_used,
            tool_calls_made=result.tool_calls_made,
            error=result.error,
        )
    finally:
        await executor.close()


@router.get("/agents")
async def list_agents():
    """List available agent types and their descriptions."""
    return {
        "agents": {
            "main": {
                "description": "Full invoice processing agent with all tools",
                "tool_count": len(AGENT_TOOLS),
                "endpoint": "/api/v1/agent/run",
            },
            **{
                name: {
                    "description": spec["description"],
                    "tool_count": len(spec["tools"]),
                    "tools": [t["name"] for t in spec["tools"]],
                    "endpoint": "/api/v1/agent/sub-agent",
                }
                for name, spec in SUB_AGENT_REGISTRY.items()
            },
        }
    }


class SkillRequest(BaseModel):
    """Request to invoke a skill."""
    document_id: str | None = Field(None, description="Document UUID (required for some skills)")
    context: dict | None = Field(None, description="Optional additional context")


@router.post("/skills/{skill_name}", response_model=AgentResponse)
async def run_skill_endpoint(
    skill_name: str,
    request: SkillRequest,
    session: AsyncSession = Depends(get_db),
):
    """Run a user-invocable skill.

    Available skills:
    - /process-invoice: Full pipeline (extract → validate → reconcile → review)
    - /review-queue: Check pending review items
    - /reconcile: Reconcile invoice against shipments
    - /extract: Extract and validate a document
    """
    result = await run_skill(
        skill_name=skill_name,
        session=session,
        settings=settings,
        document_id=request.document_id,
        extra_context=request.context,
    )

    return AgentResponse(
        goal=result.goal,
        success=result.success,
        summary=result.summary,
        steps=[
            AgentStepResponse(
                turn=s.turn,
                tool_name=s.tool_name,
                tool_input=s.tool_input,
                tool_result=s.tool_result,
                assistant_text=s.assistant_text,
                duration_ms=s.duration_ms,
            )
            for s in result.steps
        ],
        total_duration_ms=result.total_duration_ms,
        turns_used=result.turns_used,
        tool_calls_made=result.tool_calls_made,
        error=result.error,
    )


@router.get("/skills")
async def list_skills():
    """List available user-invocable skills."""
    return {
        "skills": {
            name: {
                "description": spec.description,
                "requires_document_id": spec.requires_document_id,
                "agent_type": spec.agent_type or "main",
                "endpoint": f"/api/v1/agent/skills/{name}",
            }
            for name, spec in SKILL_REGISTRY.items()
        }
    }


# Import AGENT_TOOLS for the list endpoint
from app.agent.tools import AGENT_TOOLS
from app.agent.skills import SKILL_REGISTRY, run_skill
