"""Claude agent orchestrator with tool calling."""

import logging

import anthropic

from app.fhir_client import EpicFHIRClient
from app.mock_fhir import MockFHIRClient
from app.tools import TOOL_SCHEMAS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
<identity>
You are a virtual medical appointment assistant. You help patients manage their \
appointments: view upcoming appointments, search for availability, book, and cancel appointments.
</identity>

<language>
Always respond in English. Use a friendly and professional tone.
</language>

<rules>
- Never show technical errors to the patient. If something fails, say there was a \
problem and ask them to try again.
- Never make up data. Only show information that comes from the tools.
- If you don't understand what the patient is asking, ask them to clarify.
- Be concise but thorough in your responses.
</rules>

<confirmation>
BEFORE booking or cancelling an appointment, ALWAYS show a summary and ask for \
explicit confirmation from the patient. Never execute book_appointment or \
cancel_appointment without prior confirmation.
</confirmation>

<errors>
If a tool returns an error, respond with a friendly message:
- "I couldn't check your appointments right now. Can you try again?"
- "I didn't find availability for that date. Would you like to try another day?"
- "The booking couldn't be completed. The time slot may no longer be available."
</errors>
"""

TOOL_DEFINITIONS = TOOL_SCHEMAS


def get_anthropic_client(api_key: str | None = None) -> anthropic.Anthropic:
    """Get Anthropic client. Separated for test patching."""
    return anthropic.Anthropic(api_key=api_key)


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Execute a tool by name and return the result string."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        logger.error("Unknown tool: %s", tool_name)
        return f"Unknown tool: {tool_name}"

    return await handler(
        tool_input=tool_input,
        fhir_client=fhir_client,
        patient_id=patient_id,
    )


async def process_message(
    message: str,
    history: list[dict],
    patient_id: str,
    access_token: str,
    settings,
) -> str:
    """Process a patient message through the Claude agent with tool calling.

    Args:
        message: The current patient message.
        history: Conversation history (list of {role, content} dicts).
        patient_id: FHIR Patient ID from session.
        access_token: OAuth access token for FHIR calls.
        settings: Application settings.

    Returns:
        The agent's final text response.
    """
    client = get_anthropic_client(api_key=settings.ANTHROPIC_API_KEY)

    # Build messages array: history + current message
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    # Create FHIR client for tool execution (mock in dev mode)
    is_dev = access_token == "dev-token-not-for-fhir-calls"
    fhir_client = MockFHIRClient() if is_dev else EpicFHIRClient(
        base_url=settings.EPIC_FHIR_BASE_URL,
        access_token=access_token,
    )

    try:
        # Agentic loop: keep calling until end_turn
        max_iterations = 5
        for _ in range(max_iterations):
            response = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
                timeout=60.0,
            )

            if response.stop_reason == "end_turn":
                # Extract text from response
                text_parts = [
                    block.text for block in response.content
                    if block.type == "text"
                ]
                return " ".join(text_parts) if text_parts else "I don't have a response for that."

            if response.stop_reason == "tool_use":
                # Add assistant message with tool_use blocks
                messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": block.type,
                            **({"id": block.id, "name": block.name, "input": block.input}
                               if block.type == "tool_use" else {"text": block.text}),
                        }
                        for block in response.content
                    ],
                })

                # Execute each tool and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            fhir_client=fhir_client,
                            patient_id=patient_id,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add tool results as user message
                messages.append({"role": "user", "content": tool_results})

        return "Sorry, I couldn't complete your request. Please try again."

    finally:
        await fhir_client.close()
