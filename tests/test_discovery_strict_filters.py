from dataclasses import replace
from pathlib import Path
import json

import pytest

from app.discovery.contracts import DiscoveryListing, DiscoveryPreferences, SourceLead, WebPage
from app.discovery.filters import classify_constraints, source_filter_evidence
from app.discovery.basic import BasicDiscoveryEngine,source_listing
from app.discovery.state import DiscoveryState
from app.discovery.views import listing_view
from app.config import settings
from app.models import SourceSnapshot

URL='https://employer.example/jobs/software-intern'
TITLE='Software Intern'

def posting(text, *, title=TITLE, url=URL, **changes):
    snapshot=SourceSnapshot(id='sourced-posting',url=url,title=title,text=text)
    page=WebPage(snapshot=snapshot,requested_url=url)
    listing=DiscoveryListing(id='target',title=title,organization='Employer',locations=['Tokyo, Japan'],
        source_url=url,apply_url=url,checked_at=snapshot.checked_at,verification='partial',**changes)
    return source_filter_evidence(listing,page)

def preferences(**changes):
    return DiscoveryPreferences(roles=['software intern'],locations=['Japan'],funding='fully_funded',**changes)

FULL='# Software Intern\nLocation: Tokyo, Japan\nWe provide a monthly stipend.\nAccommodation is provided.\nRound-trip flights are reimbursed up to 900 USD.'

def test_all_three_benefits_require_quotes_and_match_the_posting_location():
    listing=posting(FULL)
    classified=classify_constraints(listing,preferences())
    assert classified.constraint_status=='match'
    assert listing.stipend is True and listing.housing is True and listing.round_trip_travel is True
    assert listing.filter_evidence['round_trip_travel']==['Round-trip flights are reimbursed up to 900 USD.']
    assert '900 USD' in listing.funding_note
    assert listing_view([listing],preferences=preferences())[0].id=='target'

@pytest.mark.parametrize('text',[FULL.replace('Accommodation is provided.',''),FULL.replace('Round-trip flights','Travel expenses'),FULL.replace('We provide a monthly stipend.','')])
def test_missing_component_does_not_pass_strict_filter(text):
    listing=posting(text)
    assert classify_constraints(listing,preferences()).constraint_status=='needs_review'
    assert not listing_view([listing],preferences=preferences())
    assert listing_view([listing],view='review',preferences=preferences())

@pytest.mark.parametrize('coverage',['Accommodation is not provided.','No accommodation is included.','You must pay for accommodation at your expense.'])
def test_explicit_uncovered_component_is_excluded_not_unknown(coverage):
    listing=posting(FULL.replace('Accommodation is provided.',coverage))
    assert listing.housing is False
    assert classify_constraints(listing,preferences()).constraint_status=='excluded'
    assert not listing_view([listing],view='review',preferences=preferences())

@pytest.mark.parametrize('coverage',['Accommodation may be provided.','You can apply for accommodation support.','We help you find accommodation.','Housing market research is part of the project.'])
def test_conditional_and_incidental_benefits_cannot_be_confirmed(coverage):
    listing=posting(FULL.replace('Accommodation is provided.',coverage))
    assert listing.housing is None
    assert classify_constraints(listing,preferences()).constraint_status=='needs_review'


def test_other_country_is_excluded_even_with_full_funding():
    text=FULL.replace('Tokyo, Japan','Berlin, Germany')
    snapshot=SourceSnapshot(id='foreign',url=URL,title=TITLE,text=text)
    value=source_listing(SourceLead(url=URL,title=TITLE,kind='posting'),WebPage(snapshot=snapshot,requested_url=URL))
    assert value.locations==['Berlin, Germany']
    assert classify_constraints(value,preferences()).constraint_status=='excluded'


def test_snippet_location_and_funding_label_alone_do_not_pass():
    value=DiscoveryListing(id='unread',title=TITLE,organization='Employer',locations=['Japan'],
        source_url=URL,apply_url=URL,checked_at='2026-10-17',verification='uncertain',
        funding_level='fully_funded',stipend=True,housing=True,round_trip_travel=True)
    assert classify_constraints(value,preferences()).constraint_status=='needs_review'


def test_stale_evidence_cannot_restore_confirmed_match():
    value=posting(FULL).model_copy(update={'verification':'uncertain'})
    assert classify_constraints(value,preferences()).constraint_status=='needs_review'


def test_related_posting_cannot_supply_missing_benefits():
    value=posting('# Software Intern\nLocation: Tokyo, Japan\nPython required.\n# Related jobs\n# Robotics Intern\nWe provide a stipend, accommodation and round-trip flights.')
    assert value.stipend is value.housing is value.round_trip_travel is None


def test_benefits_list_uses_provider_promise_but_access_list_does_not():
    value=posting('# Software Intern\nLocation: Tokyo, Japan\n# Benefits\n### be provided with\nMonthly subsidy\nAccommodation\nRound-trip airfares\n### and get access to\nHousing market workshops')
    assert value.stipend is True and value.housing is True and value.round_trip_travel is True


def test_conflicting_benefit_text_keeps_coverage_unknown():
    value=posting(FULL+'\nAccommodation is not covered.')
    assert value.housing is None
    assert classify_constraints(value,preferences()).constraint_status=='needs_review'


def test_unpaid_program_can_offer_living_subsidy_without_being_paid_employment():
    value=posting('# Software Intern\nLocation: Tokyo, Japan\nThe program is unpaid, but we provide a monthly subsidy.\nAccommodation is provided.\nRound-trip travel is provided.')
    assert value.stipend is True
    assert value.funding_level=='fully_funded'


def test_no_salary_is_not_paid_filter_match():
    value=posting('# Software Intern\nLocation: Tokyo, Japan\nNo salary or stipend is provided.')
    assert value.stipend is False
    assert classify_constraints(value,DiscoveryPreferences(roles=['intern'],funding='paid')).constraint_status=='excluded'


def test_preferring_japan_does_not_establish_japan_location():
    value=posting('# Software Intern\nLocation not stated.\nApplicants should be interested in pursuing a career in Japan.\n'+FULL.split('\n',2)[2])
    assert 'location' not in value.filter_evidence
    assert classify_constraints(value,preferences()).constraint_status=='needs_review'


def test_location_and_funding_filters_are_cumulative():
    good=posting(FULL)
    wrong=posting(FULL).model_copy(update={'id':'wrong','locations':['Germany'],'filter_evidence':{'location':['Location: Berlin, Germany'],**{k:v for k,v in good.filter_evidence.items() if k!='location'}}})
    missing=posting(FULL.replace('Accommodation is provided.','')).model_copy(update={'id':'missing'})
    assert [x.id for x in listing_view([wrong,missing,good],preferences=preferences())]==['target']
    assert [x.id for x in listing_view([wrong,missing,good],preferences=preferences(),view='review')]==['missing']


def test_scenario_bank_has_balanced_contexts_and_no_invented_named_assignment():
    bank=json.loads((Path(__file__).resolve().parents[1]/'app/interest/scenarios.json').read_text())
    assert len(bank['scenarios'])==12 and len({s['id'] for s in bank['scenarios']})==12
    for direction in bank['directions']:
        items=[s for s in bank['scenarios'] if s['direction']==direction]
        assert len(items)==2 and any('Company' in s['context'] for s in items) and any('Research internship' in s['context'] for s in items)
    assert 'illustrative' in bank['notice'] and 'do not measure skill' in bank['notice']


def test_unrelated_source_cannot_provide_filter_evidence():
    value=posting(FULL)
    other=WebPage(snapshot=SourceSnapshot(id='other',url='https://other.example/jobs/1',title=TITLE,text=FULL),
                  requested_url='https://other.example/jobs/1')
    assert not source_filter_evidence(value,other).filter_evidence


def test_multiple_cohorts_do_not_share_other_cohort_benefits():
    text='# Software Intern\n# Spring 2027\nLocation: Tokyo, Japan\nPython required.\n# Fall 2027\n'+FULL
    value=posting(text,cycle='Spring 2027')
    assert value.stipend is value.housing is value.round_trip_travel is None


@pytest.mark.parametrize('quote',['Students pay for accommodation.','Housing workshop provided.','A stipend research project is provided.'])
def test_payment_and_project_mentions_are_not_funding_promises(quote):
    value=posting('# Software Intern\nLocation: Tokyo, Japan\n'+quote)
    assert value.funding_level=='unknown'


@pytest.mark.parametrize('quote',['Accommodation is provided for a fee.','Housing is paid by interns.'])
def test_accommodation_at_users_cost_is_excluded(quote):
    value=posting(FULL.replace('Accommodation is provided.',quote))
    assert value.housing is False
    assert classify_constraints(value,preferences()).constraint_status=='excluded'


@pytest.mark.parametrize('quote',['Accommodation is provided subject to availability.','Accommodation is provided only for eligible applicants.'])
def test_conditional_accommodation_remains_unconfirmed(quote):
    value=posting(FULL.replace('Accommodation is provided.',quote))
    assert value.housing is None
    assert classify_constraints(value,preferences()).constraint_status=='needs_review'
