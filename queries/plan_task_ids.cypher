MATCH (plan:Plan)-[:HAS_TASK]->(task:PlanTask)
WHERE plan.id IN $plan_ids
RETURN DISTINCT task.task_id
LIMIT 1001
