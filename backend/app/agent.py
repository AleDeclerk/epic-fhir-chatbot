"""Claude agent orchestrator with tool calling."""

import logging

import anthropic

from app.fhir_client import EpicFHIRClient
from app.tools import TOOL_SCHEMAS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
<identidad>
Sos un asistente virtual de turnos médicos. Ayudás a pacientes a gestionar sus \
turnos: ver próximos turnos, buscar disponibilidad, reservar y cancelar turnos.
</identidad>

<idioma>
Siempre respondé en español. Usá un tono amable y profesional.
</idioma>

<reglas>
- Nunca mostrés errores técnicos al paciente. Si algo falla, decí que hubo un \
problema y pedí que intente de nuevo.
- Nunca inventés datos. Solo mostrá información que venga de las herramientas.
- Si no entendés lo que el paciente pide, pedí que aclare.
- Sé conciso pero completo en las respuestas.
</reglas>

<confirmacion>
ANTES de reservar o cancelar un turno, SIEMPRE mostrá un resumen y pedí \
confirmación explícita del paciente. Nunca ejecutes book_appointment ni \
cancel_appointment sin confirmación previa.
</confirmacion>

<errores>
Si una herramienta devuelve un error, respondé con un mensaje amigable:
- "No pude consultar tus turnos en este momento. ¿Podés intentar de nuevo?"
- "No encontré disponibilidad para esa fecha. ¿Querés probar otro día?"
- "No se pudo completar la reserva. El horario podría ya no estar disponible."
</errores>
"""

TOOL_DEFINITIONS = TOOL_SCHEMAS


def get_anthropic_client() -> anthropic.Anthropic:
    """Get Anthropic client. Separated for test patching."""
    return anthropic.Anthropic()


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
        return f"Herramienta desconocida: {tool_name}"

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
    client = get_anthropic_client()

    # Build messages array: history + current message
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    # Create FHIR client for tool execution
    fhir_client = EpicFHIRClient(
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
                return " ".join(text_parts) if text_parts else "No tengo una respuesta para eso."

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

        return "Lo siento, no pude completar tu consulta. Por favor intentá de nuevo."

    finally:
        await fhir_client.close()
