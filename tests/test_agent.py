from __future__ import annotations

import json
from dataclasses import replace

import httpx

from app.agent import compact_tool_context, run_agent, summarize_context, summarize_plan
from app.config import settings
from app.models import GraphContext, Plan, ProfileState, PlanTask, TargetAssessment
from app.sources import DiscoverService


def test_default_source_context_keeps_requirements_inside_bound():
    result = DiscoverService().load_examples()
    context = GraphContext(opportunities=[o for o in result.opportunities
                           if o.id in {"epfl-summer-2027", "oist-fall-2027"}])
    payload = compact_tool_context({"agent_context": summarize_context(context)})
    data = json.loads(payload)
    assert len(payload) <= 14500
    targets = {target["id"]: target for target in data["targets"]}
    oist = targets["oist-fall-2027"]
    facts = {fact["name"]: fact for fact in oist["facts"]}
    assert facts["reference_min"]["value"] == 1
    assert facts["reference_received_before_submit"]["value"] is True
    assert facts["reference_received_before_submit"]["excerpt"]
    assert targets["epfl-summer-2027"]["call_status"] == "closed"
    assert "notice" in data


def test_large_plan_keeps_action_and_external_blockers():
    profile = ProfileState()
    plan = Plan(id="test-plan", selected_ids=["oist"], profile=profile,
                targets=[TargetAssessment(target_id="oist", readiness="waiting_external",
                                          reasons=["Missing recommendation receipt." * 200])],
                tasks=[PlanTask(task_id="receipt", title="Confirm qualifying reference",
                                category="Research", target_ids=["oist"], status="waiting",
                                waiting_for="oist/references_received/min=1", reason="Not received." * 100)],
                next_action="Request a qualifying faculty reference.",
                warnings=["Explicit estimate only." * 100] * 20)
    payload = compact_tool_context({"agent_context": summarize_plan(plan)})
    data = json.loads(payload)
    assert len(payload) <= 14500
    assert data["next_action"] == plan.next_action
    assert data["targets"][0]["readiness"] == "waiting_external"
    assert data["blockers"][0]["waiting_for"] == "oist/references_received/min=1"


def test_agent_messages_contain_grounding_and_honest_trace():
    bodies = []
    called = []
    steps = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-bad", "type": "function", "function": {
                "name": "inspect_requirements", "arguments": '{"unexpected":"value"}'}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-good", "type": "function", "function": {
                "name": "inspect_requirements", "arguments": "{}"}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-plan", "type": "function", "function": {
                "name": "propose_plan", "arguments": "{}"}}]},
        {"role": "assistant", "content": "A qualifying recommendation is still waiting."},
    ]
    def transport(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": steps[len(bodies)-1]}]})
    def inspect():
        called.append("inspect")
        return {"summary": "Requirements read.", "agent_context": {
            "targets": [{"id": "oist", "facts": [{"name": "reference_min", "value": 1}]}]}}
    def plan():
        called.append("plan")
        return {"summary": "Proposal created.", "agent_context": {
            "next_action": "Request a qualifying reference.", "blockers": [{"status": "waiting"}]}}
    result = run_agent("Make a plan", {"inspect_requirements": inspect, "propose_plan": plan},
                       replace(settings, groq_key="test-dummy"),
                       transport=httpx.MockTransport(transport))
    assert called == ["inspect", "plan"]
    assert result["trace"][0]["arguments"] == {"unexpected": "value"}
    assert result["trace"][0]["outcome"] == "rejected"
    assert result["trace"][1]["outcome"] == "executed"
    messages = bodies[-1]["messages"]
    actual_tool_payloads = [json.loads(item["content"]) for item in messages if item["role"] == "tool"]
    assert any(item.get("next_action") == "Request a qualifying reference." for item in actual_tool_payloads)
    assert any(item.get("targets") for item in actual_tool_payloads)

