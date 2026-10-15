MATCH (plan:Plan {id: $plan_id})-[:HAS_TARGET|HAS_TASK]->()-[:USED_FACT]->(used:FactVersion)
RETURN DISTINCT used.fact_id, used.id
LIMIT 196
