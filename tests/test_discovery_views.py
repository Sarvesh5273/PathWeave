from app.discovery.contracts import DiscoveryListing
from app.discovery.views import hunt_summary,listing_view


def listing(identifier,**changes):
    values={"id":identifier,"title":"Software Intern","organization":"Example","locations":["Japan"],
            "apply_url":"https://company.example/jobs/"+identifier,"source_url":"https://company.example/jobs/"+identifier,
            "checked_at":"2026-10-16T00:00:00Z","score":75}
    values.update(changes)
    return DiscoveryListing(**values)


def test_scout_saved_hidden_new_and_closed_views():
    values=[listing("open",is_new=True),listing("closed",call_status="closed",saved=True),listing("hidden",hidden=True),listing("old")]
    assert {v.id for v in listing_view(values)}=={"open","old"}
    assert [v.id for v in listing_view(values,view="saved")]==["closed"]
    assert [v.id for v in listing_view(values,view="hidden")]==["hidden"]
    assert [v.id for v in listing_view(values,view="new")]==["open"]


def test_scout_filtering_and_sorting_keep_approximate_deadline_unknown():
    values=[listing("month",deadline_text="November 2026",deadline_precision="month"),
            listing("day",deadline_text="October 30, 2026",deadline_precision="date",funding_level="paid",stipend=True,
                    filter_evidence={"stipend":["A stipend is provided."]},visa_status="sponsors"),
            listing("high",score=95),listing("low",score=40,kind="program")]
    assert listing_view(values,sort="deadline")[0].id=="day"
    assert listing_view(values)[0].id=="high"
    assert [v.id for v in listing_view(values,funding="paid",visa="sponsors",query="japan",min_score=60)]==["day"]


def test_hunt_summary_reports_observed_data_not_demo_metrics():
    values=[listing("new",is_new=True,visa_status="sponsors",saved=True),listing("closed",call_status="closed")]
    result=hunt_summary(values,[{"stage":"fetch","url":"https://company.example/jobs/new"}])
    assert result["total"]==1 and result["new"]==1 and result["saved"]==1
    assert result["sources"]==1 and result["by_visa"]["sponsors"]==1
