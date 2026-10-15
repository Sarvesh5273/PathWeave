MATCH (plan:Plan {id: $plan_id})-[:HAS_TARGET|HAS_TASK]->(item)
WHERE item.stale = true
RETURN coalesce(item.target_id, ''), coalesce(item.task_id, '')
LIMIT 193
