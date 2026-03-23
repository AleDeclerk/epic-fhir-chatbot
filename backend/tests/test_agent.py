"""Tests for Claude agent orchestrator (TDD Red → Green)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAgentSystemPrompt:
    """T016: Tests for agent system prompt and tool loop."""

    def test_system_prompt_is_in_english(self):
        """System prompt must be in English."""
        from app.agent import SYSTEM_PROMPT

        # Check for English content markers
        assert any(word in SYSTEM_PROMPT.lower() for word in ["patient", "appointment", "practitioner"])

    def test_system_prompt_has_xml_tags(self):
        """System prompt uses XML tags per research.md R7."""
        from app.agent import SYSTEM_PROMPT

        assert "<" in SYSTEM_PROMPT and ">" in SYSTEM_PROMPT

    def test_tool_definitions_include_list_appointments(self):
        """list_appointments tool is defined in tool array."""
        from app.agent import TOOL_DEFINITIONS

        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "list_appointments" in names

    def test_tool_definitions_include_search_available_slots(self):
        """search_available_slots tool is defined."""
        from app.agent import TOOL_DEFINITIONS

        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "search_available_slots" in names

    def test_tool_definitions_include_book_appointment(self):
        """book_appointment tool is defined."""
        from app.agent import TOOL_DEFINITIONS

        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "book_appointment" in names

    def test_tool_definitions_include_cancel_appointment(self):
        """cancel_appointment tool is defined."""
        from app.agent import TOOL_DEFINITIONS

        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "cancel_appointment" in names


class TestAgenticLoop:
    """Test the agentic loop: send → tool_use → tool_result → end_turn."""

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self):
        """When Claude returns end_turn, return the text directly."""
        from app.agent import process_message

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text="Hello! How can I help you?")
        ]

        with patch("app.agent.get_anthropic_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = MagicMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await process_message(
                message="Hello",
                history=[],
                patient_id="patient-123",
                access_token="token-123",
                settings=MagicMock(
                    CLAUDE_MODEL="claude-sonnet-4-20250514",
                    EPIC_FHIR_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/STU3",
                ),
            )
            assert "Hello" in result or "help" in result

    @pytest.mark.asyncio
    async def test_tool_use_then_end_turn(self):
        """When Claude returns tool_use, execute tool, send result, get final response."""
        from app.agent import process_message

        # First response: tool_use
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tool-call-1"
        tool_use_block.name = "list_appointments"
        tool_use_block.input = {}

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use_block]

        # Second response: end_turn with text
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "You have no upcoming appointments."

        second_response = MagicMock()
        second_response.stop_reason = "end_turn"
        second_response.content = [text_block]

        with patch("app.agent.get_anthropic_client") as mock_get_client, \
             patch("app.agent.execute_tool", new_callable=AsyncMock) as mock_exec:

            mock_client = MagicMock()
            mock_client.messages.create = MagicMock(
                side_effect=[first_response, second_response]
            )
            mock_get_client.return_value = mock_client
            mock_exec.return_value = "No upcoming appointments found."

            result = await process_message(
                message="What appointments do I have?",
                history=[],
                patient_id="patient-123",
                access_token="token-123",
                settings=MagicMock(
                    CLAUDE_MODEL="claude-sonnet-4-20250514",
                    EPIC_FHIR_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/STU3",
                ),
            )
            assert "appointment" in result.lower() or "no" in result.lower()
            mock_exec.assert_called_once()
