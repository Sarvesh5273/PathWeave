"""Emit a real offline planner response for browser checks; never access storage."""
import json
import sys

from app.models import EvidencePath, Fact, GraphContext, Opportunity, PreparationTask, ProfileState, TopicInfo
from app.planner import build_plan
from app.topics import TOPIC_CATALOG

request = json.load(sys.stdin)
target = request.get("target_id", "ui-fixture-target")
url = "https://example.org/internships/fixture"
facts = [Fact(name="requirements_review", status="unknown", source_url=url)]
tasks = [
    PreparationTask(id=f"{target}/verify", title="Check application requirements",
                    category="Company", target_ids=[target], hours_low=0.5, hours_high=1),
    PreparationTask(id=f"{target}/submission", title="Confirm the portal before applying",
                    category="Company", target_ids=[target], artifact_type="submission"),
]
topics = []
if request.get("with_source"):
    facts.append(Fact(name="skills", value=["Python"], status="known",
                      excerpt="Python skills required.", source_url=url, version_id="synthetic-python-v1"))
    tasks.append(PreparationTask(
        id="shared/skill-python-foundation/v1", title="Practice Python with a small tested exercise",
        target_ids=[target], hours_low=2, hours_high=4,
    ))
    topics.append(TopicInfo(key="python", title="Python", family="Programming",
                            resources=TOPIC_CATALOG["python"]["resources"], required_by={target: ["skills"]}))
context = GraphContext(opportunities=[Opportunity(
    id=target, program="Synthetic software internship", category="Company", mode="synthetic",
    source_url=url, facts=facts,
)], tasks=tasks, topics=topics, evidence=[
    EvidencePath(target_id=target, task_id=f"{target}/verify",
                 nodes=[target, "REQUIRES_REVIEW", f"{target}/verify"],
                 source_url=url, excerpt="Synthetic fixture: selected source review is incomplete."),
])
defaults = dict(id="ui-fixture-profile", start_date="2026-10-19", horizon_weeks=8,
                weekly_hours=6, study_track="software")
defaults.update(request.get("profile", {}))
print(build_plan(context, ProfileState.model_validate(defaults)).model_dump_json())
