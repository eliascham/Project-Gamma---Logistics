"""Tests for the Invoice Processing Agent (B2).

Tests tool definitions, executor dispatch, orchestrator data structures,
and the agent API schema.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from app.agent.tools import AGENT_TOOLS
from app.agent.executor import ToolExecutor
from app.agent.orchestrator import (
    AGENT_SYSTEM_PROMPT,
    AgentResult,
    AgentStep,
    MAX_AGENT_TURNS,
    run_agent,
    run_sub_agent,
)
from app.agent.sub_agents import (
    SUB_AGENT_REGISTRY,
    EXTRACTION_AGENT_TOOLS,
    RECONCILIATION_AGENT_TOOLS,
    AUDIT_AGENT_TOOLS,
)
from app.agent.skills import SKILL_REGISTRY, SkillSpec


# ─── Tool Definitions ──────────────────────────────────────────


class TestAgentToolDefinitions:
    def test_tool_count(self):
        assert len(AGENT_TOOLS) == 8

    def test_all_tools_have_names(self):
        for tool in AGENT_TOOLS:
            assert "name" in tool
            assert len(tool["name"]) > 0

    def test_all_tools_have_descriptions(self):
        for tool in AGENT_TOOLS:
            assert "description" in tool
            assert len(tool["description"]) > 20

    def test_all_tools_have_input_schemas(self):
        for tool in AGENT_TOOLS:
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "properties" in tool["input_schema"]

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in AGENT_TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_exist(self):
        names = {t["name"] for t in AGENT_TOOLS}
        expected = {
            "extract_document",
            "validate_extraction",
            "search_shipments",
            "reconcile_invoice",
            "create_review_item",
            "log_audit_event",
            "get_document_info",
            "get_extraction",
        }
        assert expected == names

    def test_required_fields_specified(self):
        """Tools that need document_id should have it required."""
        extract = next(t for t in AGENT_TOOLS if t["name"] == "extract_document")
        assert "document_id" in extract["input_schema"]["required"]

        validate = next(t for t in AGENT_TOOLS if t["name"] == "validate_extraction")
        assert "extraction" in validate["input_schema"]["required"]
        assert "document_type" in validate["input_schema"]["required"]


# ─── Executor Dispatch ──────────────────────────────────────────


class TestToolExecutor:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.database_url = "sqlite+aiosqlite:///./test.db"
        settings.anthropic_api_key = "test-key"
        settings.claude_model = "claude-sonnet-4-20250514"
        settings.upload_dir = "/tmp/uploads"
        return settings

    def test_unknown_tool_returns_error(self, mock_session, mock_settings):
        executor = ToolExecutor(session=mock_session, settings=mock_settings)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("nonexistent_tool", {})
        )
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_extraction_tool(self, mock_session, mock_settings):
        """validate_extraction should run without DB access."""
        executor = ToolExecutor(session=mock_session, settings=mock_settings)
        result = await executor.execute("validate_extraction", {
            "extraction": {
                "invoice_number": "INV-001",
                "vendor_name": "Maersk Line",
                "total_amount": 7500.0,
                "invoice_date": "2024-11-15",
                "currency": "USD",
                "line_items": [
                    {"description": "Ocean Freight", "quantity": 2, "unit": "TEU",
                     "unit_price": 3500.0, "total": 7000.0},
                    {"description": "BAF", "quantity": 2, "unit": "TEU",
                     "unit_price": 250.0, "total": 500.0},
                ],
                "subtotal": 7500.0,
                "tax_amount": 0,
            },
            "document_type": "freight_invoice",
        })
        assert result["passed"] is True
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_validate_extraction_with_errors(self, mock_session, mock_settings):
        """Validation should catch issues."""
        executor = ToolExecutor(session=mock_session, settings=mock_settings)
        result = await executor.execute("validate_extraction", {
            "extraction": {
                "invoice_number": "",  # empty required
                "vendor_name": None,   # null required
                "total_amount": -500,  # negative
                "currency": "FAKE",
            },
            "document_type": "freight_invoice",
        })
        assert result["passed"] is False
        assert result["error_count"] > 0
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_log_audit_event_tool(self, mock_session, mock_settings):
        """Audit logging should call AuditService.log_event."""
        executor = ToolExecutor(session=mock_session, settings=mock_settings)
        with patch("app.audit_generator.service.AuditService.log_event", new_callable=AsyncMock) as mock_log:
            result = await executor.execute("log_audit_event", {
                "action": "test_action",
                "entity_type": "document",
                "entity_id": "test-123",
                "details": {"note": "test"},
            })
        assert result["status"] == "logged"
        assert result["action"] == "test_action"
        mock_log.assert_called_once()


# ─── Agent Data Structures ──────────────────────────────────────


class TestAgentDataStructures:
    def test_agent_step_creation(self):
        step = AgentStep(
            turn=0,
            tool_name="extract_document",
            tool_input={"document_id": "abc"},
            tool_result={"status": "extracted"},
            assistant_text="Extracting document...",
            duration_ms=150,
        )
        assert step.turn == 0
        assert step.tool_name == "extract_document"
        assert step.duration_ms == 150

    def test_agent_result_success(self):
        result = AgentResult(
            goal="Process invoice",
            success=True,
            summary="Invoice processed and matched.",
            steps=[],
            total_duration_ms=5000,
            turns_used=4,
            tool_calls_made=6,
        )
        assert result.success is True
        assert result.error is None
        assert result.turns_used == 4

    def test_agent_result_failure(self):
        result = AgentResult(
            goal="Process invoice",
            success=False,
            summary="Agent reached max turns.",
            error="max_turns_exceeded",
        )
        assert result.success is False
        assert result.error == "max_turns_exceeded"

    def test_max_turns_default(self):
        assert MAX_AGENT_TURNS == 15

    def test_system_prompt_contains_workflow(self):
        assert "extract" in AGENT_SYSTEM_PROMPT.lower()
        assert "reconcil" in AGENT_SYSTEM_PROMPT.lower()
        assert "review" in AGENT_SYSTEM_PROMPT.lower()
        assert "audit" in AGENT_SYSTEM_PROMPT.lower()


# ─── Orchestrator (mocked Claude) ──────────────────────────────


class TestAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_agent_completes_with_text_only_response(self):
        """Agent should complete when Claude returns text without tool calls."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        mock_settings.claude_max_tokens = 4096

        mock_executor = AsyncMock()

        # Mock Claude to return a text-only response (no tool calls)
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "I've completed the task. Here is the summary."
        mock_response.content = [mock_text_block]

        with patch("app.agent.orchestrator.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            result = await run_agent(
                goal="Test goal",
                executor=mock_executor,
                settings=mock_settings,
                max_turns=5,
            )

        assert result.success is True
        assert result.turns_used == 1
        assert result.tool_calls_made == 0
        assert "completed" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_agent_executes_tool_calls(self):
        """Agent should execute tool calls and feed results back."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        mock_settings.claude_max_tokens = 4096

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"status": "ok", "data": "test"})

        # Turn 1: Claude returns a tool call
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool_1"
        mock_tool_block.name = "get_document_info"
        mock_tool_block.input = {"document_id": "abc-123"}

        mock_text_block1 = MagicMock()
        mock_text_block1.type = "text"
        mock_text_block1.text = "Let me look up the document."

        response1 = MagicMock()
        response1.content = [mock_text_block1, mock_tool_block]

        # Turn 2: Claude returns final text
        mock_text_block2 = MagicMock()
        mock_text_block2.type = "text"
        mock_text_block2.text = "Done. The document was processed successfully."

        response2 = MagicMock()
        response2.content = [mock_text_block2]

        with patch("app.agent.orchestrator.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=[response1, response2])
            mock_anthropic.return_value = mock_client

            result = await run_agent(
                goal="Process document abc-123",
                executor=mock_executor,
                settings=mock_settings,
                context={"document_id": "abc-123"},
                max_turns=5,
            )

        assert result.success is True
        assert result.turns_used == 2
        assert result.tool_calls_made == 1
        assert len(result.steps) == 2  # 1 tool call + 1 final text

        # Verify executor was called with the right tool
        mock_executor.execute.assert_called_once_with(
            "get_document_info", {"document_id": "abc-123"}
        )

    @pytest.mark.asyncio
    async def test_agent_stops_at_max_turns(self):
        """Agent should stop and report failure at max turns."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        mock_settings.claude_max_tokens = 4096

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"status": "ok"})

        # Always return a tool call (never finishes)
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool_loop"
        mock_tool_block.name = "search_shipments"
        mock_tool_block.input = {"vendor": "test"}

        response = MagicMock()
        response.content = [mock_tool_block]

        with patch("app.agent.orchestrator.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=response)
            mock_anthropic.return_value = mock_client

            result = await run_agent(
                goal="Infinite loop test",
                executor=mock_executor,
                settings=mock_settings,
                max_turns=3,
            )

        assert result.success is False
        assert result.error == "max_turns_exceeded"
        assert result.turns_used == 3
        assert result.tool_calls_made == 3

    @pytest.mark.asyncio
    async def test_context_included_in_messages(self):
        """Context dict should be included in the initial user message."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        mock_settings.claude_max_tokens = 4096

        mock_executor = AsyncMock()

        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Done."
        response = MagicMock()
        response.content = [mock_text]

        with patch("app.agent.orchestrator.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=response)
            mock_anthropic.return_value = mock_client

            await run_agent(
                goal="Process invoice",
                executor=mock_executor,
                settings=mock_settings,
                context={"document_id": "doc-456", "priority": "high"},
            )

            # Check that Claude was called with context in the message
            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            user_msg = messages[0]["content"]
            assert "doc-456" in user_msg
            assert "priority" in user_msg


# ─── Sub-Agent Definitions ──────────────────────────────────────


class TestSubAgents:
    def test_registry_has_three_agents(self):
        assert len(SUB_AGENT_REGISTRY) == 3
        assert "extraction" in SUB_AGENT_REGISTRY
        assert "reconciliation" in SUB_AGENT_REGISTRY
        assert "audit" in SUB_AGENT_REGISTRY

    def test_each_agent_has_required_keys(self):
        for name, spec in SUB_AGENT_REGISTRY.items():
            assert "system_prompt" in spec, f"{name} missing system_prompt"
            assert "tools" in spec, f"{name} missing tools"
            assert "description" in spec, f"{name} missing description"

    def test_extraction_agent_tools(self):
        names = {t["name"] for t in EXTRACTION_AGENT_TOOLS}
        assert "extract_document" in names
        assert "validate_extraction" in names
        assert "get_document_info" in names
        # Should NOT have reconciliation tools
        assert "reconcile_invoice" not in names
        assert "search_shipments" not in names

    def test_reconciliation_agent_tools(self):
        names = {t["name"] for t in RECONCILIATION_AGENT_TOOLS}
        assert "reconcile_invoice" in names
        assert "search_shipments" in names
        assert "get_extraction" in names
        # Should NOT have extraction tools
        assert "extract_document" not in names

    def test_audit_agent_tools(self):
        names = {t["name"] for t in AUDIT_AGENT_TOOLS}
        assert "log_audit_event" in names
        assert "create_review_item" in names
        assert "get_document_info" in names
        # Should NOT have processing tools
        assert "extract_document" not in names
        assert "reconcile_invoice" not in names

    def test_tool_subsets_are_valid(self):
        """All sub-agent tools must exist in the main tool list."""
        all_names = {t["name"] for t in AGENT_TOOLS}
        for name, spec in SUB_AGENT_REGISTRY.items():
            sub_names = {t["name"] for t in spec["tools"]}
            assert sub_names.issubset(all_names), (
                f"Sub-agent '{name}' has unknown tools: {sub_names - all_names}"
            )

    @pytest.mark.asyncio
    async def test_run_sub_agent_invalid_type(self):
        """Invalid agent type should return error."""
        mock_settings = MagicMock()
        mock_executor = AsyncMock()

        result = await run_sub_agent(
            agent_type="nonexistent",
            goal="Test",
            executor=mock_executor,
            settings=mock_settings,
        )
        assert result.success is False
        assert result.error == "invalid_agent_type"

    @pytest.mark.asyncio
    async def test_run_sub_agent_uses_correct_prompt(self):
        """Sub-agent should use its own system prompt and tools."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        mock_settings.claude_max_tokens = 4096

        mock_executor = AsyncMock()

        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Extraction complete."
        response = MagicMock()
        response.content = [mock_text]

        with patch("app.agent.orchestrator.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=response)
            mock_anthropic.return_value = mock_client

            await run_sub_agent(
                agent_type="extraction",
                goal="Extract document abc",
                executor=mock_executor,
                settings=mock_settings,
            )

            call_args = mock_client.messages.create.call_args
            # Should use extraction agent system prompt
            system = call_args.kwargs["system"]
            assert "extraction specialist" in system.lower()
            # Should use extraction agent tools (subset)
            tools = call_args.kwargs["tools"]
            tool_names = {t["name"] for t in tools}
            assert "extract_document" in tool_names
            assert "reconcile_invoice" not in tool_names


# ─── Skills ──────────────────────────────────────────────────────


class TestSkills:
    def test_skill_registry_has_four_skills(self):
        assert len(SKILL_REGISTRY) == 4
        assert "process-invoice" in SKILL_REGISTRY
        assert "review-queue" in SKILL_REGISTRY
        assert "reconcile" in SKILL_REGISTRY
        assert "extract" in SKILL_REGISTRY

    def test_each_skill_is_skill_spec(self):
        for name, spec in SKILL_REGISTRY.items():
            assert isinstance(spec, SkillSpec)
            assert spec.name == name
            assert len(spec.description) > 10
            assert len(spec.goal_template) > 10

    def test_process_invoice_requires_document_id(self):
        spec = SKILL_REGISTRY["process-invoice"]
        assert spec.requires_document_id is True
        assert spec.agent_type is None  # Uses main agent

    def test_review_queue_no_document_id(self):
        spec = SKILL_REGISTRY["review-queue"]
        assert spec.requires_document_id is False
        assert spec.agent_type == "audit"

    def test_reconcile_uses_sub_agent(self):
        spec = SKILL_REGISTRY["reconcile"]
        assert spec.agent_type == "reconciliation"
        assert spec.requires_document_id is True

    def test_extract_uses_sub_agent(self):
        spec = SKILL_REGISTRY["extract"]
        assert spec.agent_type == "extraction"
        assert spec.requires_document_id is True

    def test_goal_template_has_placeholder(self):
        """Skills requiring document_id should have {document_id} in template."""
        for name, spec in SKILL_REGISTRY.items():
            if spec.requires_document_id:
                assert "{document_id}" in spec.goal_template, (
                    f"Skill '{name}' requires document_id but template lacks placeholder"
                )
