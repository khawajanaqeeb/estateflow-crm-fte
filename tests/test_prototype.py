"""
Prototype validation — run the agent against a subset of sample tickets
and print results. Not a formal test suite yet (that comes in Stage 2).
"""

import json
import sys
import os
from pathlib import Path

# add project root to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from src.agent import CustomerSuccessAgent, IncomingMessage, Channel
from src.agent.agent import CustomerSuccessAgent


def load_tickets(path: str, limit: int = 10) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data["tickets"][:limit]


def channel_from_str(s: str) -> Channel:
    return {
        "email": Channel.EMAIL,
        "whatsapp": Channel.WHATSAPP,
        "web_form": Channel.WEB_FORM,
    }[s]


def run_tests(limit: int = 10):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    agent = CustomerSuccessAgent(api_key=api_key)
    tickets_path = Path(__file__).parents[1] / "context" / "sample-tickets.json"
    tickets = load_tickets(tickets_path, limit=limit)

    print(f"\n{'='*70}")
    print(f"  EstateFlow Customer Success FTE — Prototype Test Run")
    print(f"  Running {limit} tickets")
    print(f"{'='*70}\n")

    results = {
        "pass_escalation": 0,
        "fail_escalation": 0,
        "upsell_detected": 0,
        "total": 0,
    }

    for ticket in tickets:
        results["total"] += 1
        incoming = IncomingMessage(
            channel=channel_from_str(ticket["channel"]),
            raw_message=ticket["message"],
            customer_email=ticket.get("from") if "@" in ticket.get("from", "") else None,
            customer_phone=ticket.get("from") if "+" in ticket.get("from", "") else None,
            customer_name=ticket.get("customer_name"),
            subject=ticket.get("subject"),
            plan=ticket.get("plan"),
        )

        print(f"[{ticket['id']}] {ticket['channel'].upper()} | {ticket['category']} | plan={ticket['plan']}")
        print(f"  Customer: {ticket['customer_name']}")
        print(f"  Message:  {ticket['message'][:100]}{'...' if len(ticket['message']) > 100 else ''}")

        try:
            response = agent.handle(incoming)

            # check escalation accuracy
            expected_escalate = ticket.get("escalate", False)
            escalation_correct = response.escalate == expected_escalate
            if escalation_correct:
                results["pass_escalation"] += 1
                esc_mark = "✓"
            else:
                results["fail_escalation"] += 1
                esc_mark = "✗"

            if response.upsell_signal:
                results["upsell_detected"] += 1

            print(f"  Ticket ID:  {response.ticket_id}")
            print(f"  Sentiment:  {response.sentiment_detected.value}")
            print(f"  Priority:   {response.priority.value}")
            print(f"  Escalate:   {response.escalate} (expected={expected_escalate}) [{esc_mark}]")
            if response.escalate:
                print(f"  Esc Reason: {response.escalation_reason}")
                print(f"  Esc Level:  {response.escalation_level}")
            if response.upsell_signal:
                print(f"  Upsell:     → {response.upsell_plan} plan")
            print(f"  Topics:     {', '.join(response.topics_detected) if response.topics_detected else 'N/A'}")
            print(f"\n  --- RESPONSE ({response.channel.value}) ---")
            print(f"  {response.message.replace(chr(10), chr(10) + '  ')}")

        except Exception as e:
            results["fail_escalation"] += 1
            print(f"  ERROR: {e}")

        print(f"\n{'-'*70}\n")

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Tickets processed:       {results['total']}")
    acc = 100 * results['pass_escalation'] // results['total'] if results['total'] else 0
    print(f"  Escalation accuracy:     {results['pass_escalation']}/{results['total']} ({acc}%)")
    print(f"  Upsell signals detected: {results['upsell_detected']}")
    esc_rate = 100 * (results['pass_escalation'] + results['fail_escalation'] - results['total'] +
                      sum(1 for _ in range(results['fail_escalation']))) // results['total'] if results['total'] else 0
    print(f"{'='*70}\n")

    summary = agent.memory_summary()
    print(f"  Ticket store:  {summary['store']}")
    print(f"  Memory store:  {summary['memory']}")
    print()
    _run_memory_scenario(agent)


def _run_memory_scenario(agent: CustomerSuccessAgent):
    """
    Simulate a real multi-turn, cross-channel conversation to validate memory.

    Scenario: Tom Walsh contacts via WhatsApp about a crash,
    then follows up via web form after reinstall doesn't fix it.
    The agent should remember the prior troubleshooting context.
    """
    print(f"\n{'='*70}")
    print("  MEMORY SCENARIO: Multi-turn cross-channel conversation")
    print(f"{'='*70}\n")

    turn1 = IncomingMessage(
        channel=Channel.WHATSAPP,
        raw_message="app keeps crashing on iPhone when i open a contact",
        customer_phone="+17025551122",
        customer_name="Tom Walsh",
        customer_email="tom.walsh@walshproperties.com",
        plan="professional",
    )
    r1 = agent.handle(turn1)
    print(f"[Turn 1 — WhatsApp]")
    print(f"  Customer: {turn1.raw_message}")
    print(f"  Agent:    {r1.message}")
    print(f"  Ticket:   {r1.ticket_id} | Escalate: {r1.escalate}")

    turn2 = IncomingMessage(
        channel=Channel.WEB_FORM,
        raw_message=(
            "I submitted a WhatsApp message earlier about the app crashing. "
            "I've reinstalled it twice and it still crashes every time I try to open a contact record. "
            "I'm on iPhone 14, iOS 17.4, app version 3.2.1. This is a serious issue — "
            "I can't access my client info."
        ),
        customer_email="tom.walsh@walshproperties.com",
        customer_name="Tom Walsh",
        plan="professional",
    )
    r2 = agent.handle(turn2)
    print(f"\n[Turn 2 — Web Form (same customer, channel switch)]")
    print(f"  Customer: {turn2.raw_message[:120]}...")
    print(f"  Agent:    {r2.message[:300]}...")
    print(f"  Ticket:   {r2.ticket_id} | Escalate: {r2.escalate} | Level: {r2.escalation_level}")

    turn3 = IncomingMessage(
        channel=Channel.EMAIL,
        raw_message=(
            "Still no fix from your team. This is the third time I'm reaching out. "
            "My clients keep asking for updates and I can't access my contact records. "
            "This is completely unacceptable. I need someone to call me NOW."
        ),
        customer_email="tom.walsh@walshproperties.com",
        customer_name="Tom Walsh",
        plan="professional",
    )
    r3 = agent.handle(turn3)
    print(f"\n[Turn 3 — Email (escalating frustration, sentiment trend check)]")
    print(f"  Customer: {turn3.raw_message[:120]}...")
    print(f"  Agent:    {r3.message[:300]}...")
    print(f"  Sentiment: {r3.sentiment_detected.value} | Escalate: {r3.escalate} | Level: {r3.escalation_level}")
    print(f"\n  Memory summary: {agent.memory.summary()}")
    print()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run_tests(limit=limit)
