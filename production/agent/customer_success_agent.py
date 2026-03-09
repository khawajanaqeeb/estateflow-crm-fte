"""
EstateFlow Customer Success FTE — Production Agent
OpenAI Agents SDK implementation.

The agent is initialized once at module load and reused across all requests.
The worker passes a context dict per message that injects customer_id,
conversation_id, channel, plan, and ticket_subject into the conversation.
"""

from agents import Agent, Runner, RunConfig
from production.agent.tools import ALL_TOOLS
from production.agent.prompts import CUSTOMER_SUCCESS_SYSTEM_PROMPT

# ── Agent definition ──────────────────────────────────────────────────────────

customer_success_agent = Agent(
    name="Customer Success FTE",
    model="gpt-4o",
    instructions=CUSTOMER_SUCCESS_SYSTEM_PROMPT,
    tools=ALL_TOOLS,
)

# ── Runner helper ─────────────────────────────────────────────────────────────

async def run_agent(
    messages: list[dict],
    context: dict,
) -> object:
    """
    Run the agent for one incoming message and return the Runner result.

    Args:
        messages: Conversation history in OpenAI message format:
                  [{"role": "user" | "assistant", "content": "..."}]
        context:  Per-message metadata injected into the system prompt:
                  {
                      "customer_id":     str,
                      "conversation_id": str,
                      "channel":         "email" | "whatsapp" | "web_form",
                      "plan":            "starter" | "professional" | "team" | "brokerage",
                      "ticket_subject":  str,
                  }

    Returns:
        RunResult with .output (final text), .tool_calls (list), etc.
    """
    # Inject context variables into the system prompt
    injected_prompt = CUSTOMER_SUCCESS_SYSTEM_PROMPT
    for key, value in context.items():
        injected_prompt = injected_prompt.replace(f"{{{{{key}}}}}", str(value))

    agent_with_context = customer_success_agent.clone(
        instructions=injected_prompt
    )

    result = await Runner.run(
        agent_with_context,
        input=messages,
        max_turns=15,              # prevent runaway tool loops
        run_config=RunConfig(
            trace_include_sensitive_data=False,
        ),
    )
    return result
