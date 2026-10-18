from app.discovery.contracts import DiscoveryPreferences,SourceLead
from app.discovery.engine import _lead_priority


def test_requested_place_source_hints_prioritize_reads_without_establishing_facts():
    preferences=DiscoveryPreferences(roles=['software engineering intern','robotics intern'],locations=['Japan'])
    elsewhere=SourceLead(url='https://company.example/jobs/1001',title='Software Engineering Intern',snippet='Software internship in Austin, United States',kind='posting')
    relevant=SourceLead(url='https://lab.example/internship',title='Robotics research internship in Japan',kind='page')
    assert sorted([elsewhere,relevant],key=lambda lead:_lead_priority(preferences,lead))[0] is relevant
    assert relevant.location is None


def test_no_location_constraint_preserves_posting_before_index_priority():
    preferences=DiscoveryPreferences(roles=['software engineering intern'])
    index=SourceLead(url='https://company.example/careers',title='Software internships',kind='page')
    posting=SourceLead(url='https://company.example/jobs/1001',title='Software Engineer Intern',kind='posting')
    assert sorted([index,posting],key=lambda lead:_lead_priority(preferences,lead))[0] is posting
