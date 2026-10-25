"""Order-scoped authentication and escalation regression tests; no live services."""
import json

import pytest

from src.agent import Agent, Resources


@pytest.fixture
def offline_resources(monkeypatch):
    resources = Resources(dense=False)
    ticket_orders = []

    def lookup(order_id, proof=None):
        verified = proof == "1234"
        order = {
            "order_id": order_id,
            "status": "SYNTHETIC_PRIVATE_STATUS",
            "promised_date": "2026-10-21",
        } if verified else {}
        arguments = {"order_id": order_id}
        if proof is not None:
            arguments["verification_value"] = "[REDACTED]"
        trace = {
            "name": "lookup_order",
            "arguments": arguments,
            "result": {"verified": verified, "verification_required": not verified},
        }
        if verified:
            trace["result"]["order"] = order.copy()
        return order, trace

    def ticket(summary, order_id, reason, intent):
        ticket_orders.append(order_id)
        result = {"created": True, "ticket_id": f"synthetic-ticket-{len(ticket_orders)}"}
        return result, {
            "name": "create_ticket",
            "arguments": {"summary": summary, "order_id": order_id, "reason": reason, "intent": intent},
            "result": result.copy(),
        }

    monkeypatch.setattr(resources.tools, "lookup", lookup)
    monkeypatch.setattr(resources.tools, "ticket", ticket)
    return resources, ticket_orders


@pytest.mark.parametrize("verified", [False, True], ids=["pending", "verified"])
@pytest.mark.parametrize("escalation_text", [
    "I want a human for order 33334444",
    "Battery is swelling in order 33334444",
    "I never placed order 33334444",
    "I will take legal action for order 33334444",
])
def test_escalation_order_switch_clears_verification_and_pending_context(offline_resources, verified, escalation_text):
    resources, _ = offline_resources
    agent = Agent(resources, compose=False)
    agent.respond("Where is order 11112222?")
    assert agent.state.pending_intent == "delivery"
    if verified:
        authenticated = agent.respond("Last four digits 1234")
        assert authenticated["verified"]
        assert agent.state.order["order_id"] == "11112222"

    result = agent.respond(escalation_text)

    assert result["decision"] == "escalate"
    assert agent.state.order_id == "33334444"
    assert agent.state.order is None
    assert not result["verified"]
    assert agent.state.pending_intent == ""
    assert agent.state.pending_issue == ""
    followup = agent.respond("Where is my order?")
    assert not followup["verified"]
    assert "SYNTHETIC_PRIVATE_STATUS" not in json.dumps(followup)


def test_same_escalation_reason_is_deduplicated_only_within_the_same_order(offline_resources):
    resources, ticket_orders = offline_resources
    agent = Agent(resources, compose=False)

    first = agent.respond("I want a human for order 11112222")
    repeated = agent.respond("I want a human for order 11112222")
    second = agent.respond("I want a human for order 33334444")
    repeated_second = agent.respond("I want a human for order 33334444")

    assert ticket_orders == ["11112222", "33334444"]
    first_tickets = [call["result"]["ticket_id"] for call in first["tool_calls"] if call["name"] == "create_ticket"]
    second_tickets = [call["result"]["ticket_id"] for call in second["tool_calls"] if call["name"] == "create_ticket"]
    assert len(first_tickets) == len(second_tickets) == 1
    assert first_tickets != second_tickets
    assert not any(call["name"] == "create_ticket" for call in repeated["tool_calls"])
    assert not any(call["name"] == "create_ticket" for call in repeated_second["tool_calls"])

