"""Invoice Processing Agent — Claude tool_use orchestration loop.

The agent receives a goal (e.g., "process this invoice") and autonomously
decides which tools to call, in what order, based on intermediate results.

Flow:
  1. User provides a goal + optional context (document_id, etc.)
  2. Agent plans steps using Claude with tool_use
  3. Each tool call is executed by the ToolExecutor
  4. Tool results are fed back to Claude for the next step
  5. Agent continues until Claude produces a final text response (no more tool calls)
  6. Returns a structured AgentResult with all steps and the final summary
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.agent.tools import AGENT_TOOLS
from app.agent.executor import ToolExecutor
from app.config import Settings

logger = logging.getLogger("gamma.agent")

AGENT_SYSTEM_PROMPT = """You are an invoice processing agent for a logistics operations platform.
You have tools to extract documents, validate extractions, reconcile invoices against shipments, create review items, and log audit events.

When processing an invoice, follow this workflow:
1. Get the document info to understand what you're working with
2. Check if an extraction already exists; if not, run extraction
3. Review the extraction quality (confidence scores, validation results)
4. Search for matching shipments and run reconciliation
5. Based on reconciliation results:
   - If auto_match is True: log the match and report success
   - If candidates exist but no auto-match: create a review item for manual review
   - If no matches found: create an exception review item
6. Always log audit events for traceability

Be thorough but efficient. Explain your reasoning at each step.
When you're done, provide a clear summary of what happened and any actions needed."""

MAX_AGENT_TURNS = 15


@dataclass
class AgentStep:
    """A single step in the agent's execution."""
    turn: int
    tool_name: str | None
    tool_input: dict | None
    tool_result: dict | None
    assistant_text: str | None
    duration_ms: int = 0


@dataclass
class AgentResult:
    """Complete result of an agent run."""
    goal: str
    success: bool
    summary: str
    steps: list[AgentStep] = field(default_factory=list)
    total_duration_ms: int = 0
    turns_used: int = 0
    tool_calls_made: int = 0
    error: str | None = None


async def run_agent(
    goal: str,
    executor: ToolExecutor,
    settings: Settings,
    context: dict[str, Any] | None = None,
    max_turns: int = MAX_AGENT_TURNS,
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
) -> AgentResult:
    """Run the invoice processing agent to completion.

    Args:
        goal: Natural language description of what to do.
        executor: ToolExecutor instance for executing tool calls.
        settings: App settings (for Claude API key, model).
        context: Optional context dict (e.g., {"document_id": "..."}).
        max_turns: Maximum number of agent turns before stopping.
        system_prompt: Override system prompt (for sub-agents).
        tools: Override tool definitions (for sub-agents).

    Returns:
        AgentResult with all steps and final summary.
    """
    start_time = time.monotonic()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    active_system = system_prompt or AGENT_SYSTEM_PROMPT
    active_tools = tools or AGENT_TOOLS

    # Build initial user message
    user_message = goal
    if context:
        user_message += f"\n\nContext: {json.dumps(context, indent=2)}"

    messages = [{"role": "user", "content": user_message}]
    steps: list[AgentStep] = []
    tool_calls_made = 0

    for turn in range(max_turns):
        turn_start = time.monotonic()

        # Call Claude with tools
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            system=active_system,
            tools=active_tools,
            messages=messages,
        )

        # Process response content blocks
        assistant_text_parts = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                assistant_text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        assistant_text = "\n".join(assistant_text_parts) if assistant_text_parts else None
        turn_ms = int((time.monotonic() - turn_start) * 1000)

        # If no tool calls, agent is done
        if not tool_uses:
            steps.append(AgentStep(
                turn=turn,
                tool_name=None,
                tool_input=None,
                tool_result=None,
                assistant_text=assistant_text,
                duration_ms=turn_ms,
            ))
            total_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                goal=goal,
                success=True,
                summary=assistant_text or "Agent completed without summary.",
                steps=steps,
                total_duration_ms=total_ms,
                turns_used=turn + 1,
                tool_calls_made=tool_calls_made,
            )

        # Build assistant message with all content blocks
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute each tool call and collect results
        tool_results = []
        for tool_use in tool_uses:
            tool_start = time.monotonic()
            logger.info(
                "Agent turn %d: calling %s(%s)",
                turn, tool_use.name, json.dumps(tool_use.input, default=str)[:200],
            )

            result = await executor.execute(tool_use.name, tool_use.input)
            tool_ms = int((time.monotonic() - tool_start) * 1000)
            tool_calls_made += 1

            steps.append(AgentStep(
                turn=turn,
                tool_name=tool_use.name,
                tool_input=tool_use.input,
                tool_result=result,
                assistant_text=assistant_text,
                duration_ms=tool_ms,
            ))
            # Only include text on the first tool call of this turn
            assistant_text = None

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result, default=str),
            })

        # Feed tool results back to Claude
        messages.append({"role": "user", "content": tool_results})

    # Hit max turns
    total_ms = int((time.monotonic() - start_time) * 1000)
    return AgentResult(
        goal=goal,
        success=False,
        summary="Agent reached maximum turns without completing.",
        steps=steps,
        total_duration_ms=total_ms,
        turns_used=max_turns,
        tool_calls_made=tool_calls_made,
        error="max_turns_exceeded",
    )


async def run_sub_agent(
    agent_type: str,
    goal: str,
    executor: ToolExecutor,
    settings: Settings,
    context: dict[str, Any] | None = None,
    max_turns: int = 10,
) -> AgentResult:
    """Run a specialized sub-agent.

    Args:
        agent_type: One of "extraction", "reconciliation", "audit".
        goal: What the sub-agent should accomplish.
        executor: ToolExecutor instance.
        settings: App settings.
        context: Optional context.
        max_turns: Max turns (sub-agents default to 10).

    Returns:
        AgentResult from the sub-agent.
    """
    from app.agent.sub_agents import SUB_AGENT_REGISTRY

    if agent_type not in SUB_AGENT_REGISTRY:
        return AgentResult(
            goal=goal,
            success=False,
            summary=f"Unknown sub-agent type: {agent_type}",
            error="invalid_agent_type",
        )

    spec = SUB_AGENT_REGISTRY[agent_type]
    logger.info("Running sub-agent '%s': %s", agent_type, goal[:100])

    return await run_agent(
        goal=goal,
        executor=executor,
        settings=settings,
        context=context,
        max_turns=max_turns,
        system_prompt=spec["system_prompt"],
        tools=spec["tools"],
    )
