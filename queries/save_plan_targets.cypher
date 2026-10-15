MATCH (plan:Plan {id: $plan_id})
WITH plan
UNWIND $targets AS row
MERGE (target:PlanTarget {id: row.id})
ON CREATE SET target.target_id = row.target_id, target.payload = row.payload, target.stale = false
MERGE (plan)-[:HAS_TARGET]->(target)
WITH target, row
UNWIND row.versions AS version_id
MATCH (version:FactVersion {id: version_id})
MERGE (target)-[:USED_FACT]->(version)
RETURN count(*)
