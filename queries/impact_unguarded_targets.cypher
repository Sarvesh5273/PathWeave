MATCH path = (plan:Plan)-[:HAS_TARGET]->(target:PlanTarget)
WHERE plan.complete = true AND target.target_id IN $opportunity_ids
MATCH (guard:Fact {opportunity_id: target.target_id, name: 'requirement_set'})-[:CURRENT]->(:FactVersion)
OPTIONAL MATCH (target)-[:USED_FACT]->(used:FactVersion)
WHERE used.fact_id = guard.id
WITH plan, target, path, used
WHERE used IS NULL
SET target.stale = true, plan.stale = true
RETURN plan.id, target.target_id, '' AS task_id, [node IN nodes(path) | node.id], '' AS source_url, '' AS excerpt,
       [edge IN relationships(path) | type(edge)]
LIMIT 1001
