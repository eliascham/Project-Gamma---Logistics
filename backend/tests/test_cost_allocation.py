"""Tests for the cost allocation pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cost_allocator.pipeline import CostAllocationPipeline
from app.cost_allocator.rules import DEFAULT_RULES, format_rules_for_prompt


class TestCostAllocationPipeline:
    """Tests for CostAllocationPipeline.allocate()."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.anthropic_api_key = "test-key"
        settings.claude_model = "claude-sonnet-4-20250514"
        settings.allocation_confidence_threshold = 0.85
        return settings

    @pytest.fixture
    def sample_extraction(self):
        return {
            "invoice_number": "FI-2024-001",
            "vendor_name": "Test Freight LLC",
            "invoice_date": "2024-12-01",
            "origin": "Shanghai, China",
            "destination": "Los Angeles, CA",
            "currency": "USD",
            "line_items": [
                {
                    "description": "Ocean Freight (40ft Container)",
                    "quantity": 2,
                    "unit": "container",
                    "unit_price": 3000.0,
                    "total": 6000.0,
                },
                {
                    "description": "Customs Brokerage",
                    "quantity": 1,
                    "unit": "service",
                    "unit_price": 350.0,
                    "total": 350.0,
                },
            ],
            "total_amount": 6350.0,
        }

    @pytest.fixture
    def mock_claude_response(self):
        """Simulates Claude's JSON response for allocation."""
        return json.dumps([
            {
                "line_item_index": 0,
                "project_code": "INTL-FREIGHT-001",
                "cost_center": "LOGISTICS-OPS",
                "gl_account": "5100-FREIGHT",
                "confidence": 0.95,
                "reasoning": "Ocean freight matches the Ocean Freight rule",
            },
            {
                "line_item_index": 1,
                "project_code": "CUSTOMS-OPS-002",
                "cost_center": "COMPLIANCE",
                "gl_account": "5200-CUSTOMS",
                "confidence": 0.92,
                "reasoning": "Customs brokerage matches the Customs & Brokerage rule",
            },
        ])

    @pytest.mark.asyncio
    async def test_allocate_success(self, mock_settings, sample_extraction, mock_claude_response):
        """Test successful allocation with mocked Claude response."""
        pipeline = CostAllocationPipeline(mock_settings)

        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=mock_claude_response)]
        pipeline.client = AsyncMock()
        pipeline.client.messages.create = AsyncMock(return_value=mock_response)

        result = await pipeline.allocate(sample_extraction, "test rules")

        assert len(result.line_items) == 2
        assert result.line_items[0].project_code == "INTL-FREIGHT-001"
        assert result.line_items[0].gl_account == "5100-FREIGHT"
        assert result.line_items[0].confidence == 0.95
        assert result.line_items[1].project_code == "CUSTOMS-OPS-002"
        assert result.total_amount == 6350.0
        assert result.currency == "USD"

    @pytest.mark.asyncio
    async def test_allocate_no_line_items(self, mock_settings):
        """Test allocation fails with no line items."""
        pipeline = CostAllocationPipeline(mock_settings)
        pipeline.client = AsyncMock()

        with pytest.raises(ValueError, match="No line items"):
            await pipeline.allocate({"line_items": []}, "test rules")

    @pytest.mark.asyncio
    async def test_allocate_strips_markdown(self, mock_settings, sample_extraction):
        """Test that markdown code blocks in Claude response are handled."""
        pipeline = CostAllocationPipeline(mock_settings)

        response_with_markdown = '```json\n[{"line_item_index": 0, "project_code": "TEST", "cost_center": "TEST", "gl_account": "TEST", "confidence": 0.9, "reasoning": "test"}]\n```'
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_with_markdown)]
        pipeline.client = AsyncMock()
        pipeline.client.messages.create = AsyncMock(return_value=mock_response)

        result = await pipeline.allocate(sample_extraction, "test rules")
        assert len(result.line_items) == 1
        assert result.line_items[0].project_code == "TEST"

    def test_format_invoice(self, mock_settings, sample_extraction):
        """Test invoice formatting for the prompt."""
        pipeline = CostAllocationPipeline(mock_settings)
        text = pipeline._format_invoice(sample_extraction)

        assert "FI-2024-001" in text
        assert "Ocean Freight" in text
        assert "Customs Brokerage" in text
        assert "6350.0" in text


class TestAllocationRules:
    """Tests for business rules formatting."""

    def test_format_rules_empty(self):
        """Test formatting with no rules."""
        result = format_rules_for_prompt([])
        assert "No allocation rules configured" in result

    def test_format_rules_with_data(self):
        """Test formatting with mock rules."""
        mock_rule = MagicMock()
        mock_rule.priority = 1
        mock_rule.rule_name = "Ocean Freight"
        mock_rule.match_pattern = "ocean freight, sea freight"
        mock_rule.project_code = "INTL-FREIGHT-001"
        mock_rule.cost_center = "LOGISTICS-OPS"
        mock_rule.gl_account = "5100-FREIGHT"
        mock_rule.description = "Ocean freight charges"

        result = format_rules_for_prompt([mock_rule])
        assert "Ocean Freight" in result
        assert "INTL-FREIGHT-001" in result
        assert "5100-FREIGHT" in result

    def test_default_rules_count(self):
        """Verify we have 10 default demo rules."""
        assert len(DEFAULT_RULES) == 10
        for rule in DEFAULT_RULES:
            assert "rule_name" in rule
            assert "project_code" in rule
            assert "gl_account" in rule
