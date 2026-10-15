MATCH (plan:Plan {id: $plan_id})
WHERE plan.complete = true AND coalesce(plan.stale, false) = false
MATCH (plan)-[:HAS_TARGET]->(target:PlanTarget)
OPTIONAL MATCH (opportunity:Opportunity {id: target.target_id})
OPTIONAL MATCH (guard:Fact {opportunity_id: target.target_id, name: 'requirement_set'})-[:CURRENT]->(guard_version:FactVersion)
OPTIONAL MATCH (target)-[:USED_FACT]->(tracked_guard:FactVersion)
WHERE tracked_guard.id = guard_version.id
OPTIONAL MATCH (opportunity)-[:HAS_FACT]->(hard_fact:Fact)-[:CURRENT]->(hard_version:FactVersion)
WHERE hard_version.kind = 'requirement' AND coalesce(hard_fact.provenance, 'source_fact') <> 'graph_metadata'
WITH plan, target, opportunity, guard_version, tracked_guard, collect(DISTINCT hard_fact.name) AS hard_names
WITH plan, collect(CASE WHEN opportunity IS NULL OR coalesce(opportunity.recipe_ready, false) = false
    OR guard_version IS NULL OR tracked_guard IS NULL
    OR size(hard_names) <> size(guard_version.requirement_names)
    OR any(name IN hard_names WHERE NOT name IN guard_version.requirement_names)
    THEN target.id ELSE NULL END) AS missing_guards
WHERE size(missing_guards) = 0
OPTIONAL MATCH (plan)-[:HAS_TARGET|HAS_TASK]->()-[:USED_FACT]->(used:FactVersion)
OPTIONAL MATCH (fact:Fact {id: used.fact_id})-[:CURRENT]->(current:FactVersion)
WITH plan, collect(CASE WHEN used IS NOT NULL AND (current IS NULL OR current.id <> used.id) THEN used.id ELSE NULL END) AS changed
WHERE size(changed) = 0
SET plan.lifecycle_status = 'accepted', plan.accepted_at = coalesce(plan.accepted_at, $accepted_at)
RETURN plan.payload, plan.lifecycle_status, plan.stale
