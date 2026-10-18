import json
from dataclasses import replace

import httpx
import pytest

from app.config import settings
from app.discovery.contracts import DiscoveryListing,DiscoveryPreferences,WebPage
from app.discovery.extract import ListingExtractor
from app.models import SourceSnapshot


def source():
    return WebPage(snapshot=SourceSnapshot(id="source-test",url="https://lab.example/jobs/1001",title="Software Intern –\u00a0Summer 2027",
        text="# Software Intern –\u00a0Summer 2027\nLocation: Tokyo, Japan\nBasic qualifications\nPython and algorithms required.\nPreferred qualifications\nJavaScript preferred."),requested_url="https://lab.example/jobs/1001")


def run(output):
    def handler(request):
        value=json.loads(request.content)
        lines=json.loads(value['messages'][1]['content'])['source_lines']
        assert lines[3][1]=="Python and algorithms required."
        return httpx.Response(200,json={"usage":{"prompt_tokens":100,"completion_tokens":100},"choices":[{"finish_reason":"stop","message":{"content":json.dumps(output)}}]})
    config=replace(settings,groq_key="unique-offline-line-key",groq_model="line-test",discovery_ai_tpm=1_000_000,discovery_ai_output_tpm=1_000_000)
    return ListingExtractor(config,httpx.MockTransport(handler)).extract(source(),DiscoveryPreferences(roles=["software intern"]))


def test_compact_line_references_resolve_to_exact_source_quotes():
    result=run({'extraction_complete':True,'page_type':'posting','listings':[{'title':'Software Intern - Summer 2027','organization':'Unknown',
        'locations':['Tokyo','Japan'],'seniority':'internship','evidence':{'locations':[1]},
        'requirements':[{'name':'skills','value':['Python','algorithms'],'kind':'requirement','source_lines':[3]}]}]})
    assert len(result.listings)==1
    assert result.listings[0].title==source().snapshot.title
    assert result.listings[0].locations==['Tokyo','Japan']
    assert result.listings[0].requirements[0].excerpt=='Python and algorithms required.'


@pytest.mark.parametrize('indices',[[100],[-1],[3,5],[3,2],[True],[]])
def test_phantom_noncontiguous_or_invalid_source_ids_cannot_validate_facts(indices):
    result=run({'extraction_complete':True,'page_type':'posting','listings':[{'title':source().snapshot.title,
        'requirements':[{'name':'skills','value':['Python'],'kind':'requirement','source_lines':indices}]}]})
    assert not result.listings or not result.listings[0].requirements


def selected(output):
    def handler(request):
        body=json.loads(request.content)
        user=json.loads(body["messages"][1]["content"])
        assert user["selected_title"]==source().snapshot.title
        assert "seeker" not in user and "links" not in user
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(output)}}]})
    config=replace(settings,groq_key="offline-selected",groq_model="selected-test",
                   discovery_ai_tpm=1_000_000,discovery_ai_output_tpm=1_000_000)
    listing=DiscoveryListing(id="selected-real-identity",title=source().snapshot.title,
        organization="Lab",apply_url=source().snapshot.url,source_url=source().snapshot.url,
        checked_at=source().snapshot.checked_at,locations=["Japan"])
    return ListingExtractor(config,httpx.MockTransport(handler)).extract_selected(
        source(),listing,DiscoveryPreferences(roles=["software intern"]))


def test_selected_compact_facts_preserve_identity_and_separate_required_preferred():
    result=selected({"complete":True,"facts":[["skills",["Python","algorithms"],"requirement",[3]],
                                           ["skills",["JavaScript"],"preference",[5]]]})
    assert result.listings[0].id=="selected-real-identity"
    assert result.listings[0].locations==["Japan"]
    facts=result.listings[0].requirements
    assert facts[0].value==["Python","algorithms"] and facts[0].kind=="requirement"
    assert facts[1].value==["JavaScript"] and facts[1].kind=="preference"
    assert facts[0].excerpt=="Python and algorithms required."


def test_selected_partial_output_preserves_verified_fact_and_blocks_certification():
    result=selected({"complete":False,"facts":[["skills",["Python"],"requirement",[3]]]})
    assert result.listings and any("incomplete" in warning for warning in result.warnings)
    facts={f.name:f for f in result.listings[0].requirements}
    assert facts["skills"].value==["Python"] and facts["skills"].status=="known"
    assert facts["requirements_review"].status=="unknown" and facts["requirements_review"].kind=="requirement"
    from app.discovery.bridge import listing_to_opportunities
    from app.models import GraphContext,ProfileState
    from app.planner import build_plan
    targets=listing_to_opportunities(result.listings[0],source())
    plan=build_plan(GraphContext(opportunities=targets),ProfileState(start_date="2026-10-19"))
    assert plan.targets[0].schedule_status=="cannot_certify"
    assert any("review is incomplete" in warning for warning in plan.warnings)


def test_selected_compact_phantom_values_and_source_lines_are_rejected():
    result=selected({"complete":True,"facts":[["skills",["Rust"],"requirement",[3]],
        ["documents",["passport"],"requirement",[100]]]})
    assert result.listings and all(f.status=="unknown" for f in result.listings[0].requirements)
