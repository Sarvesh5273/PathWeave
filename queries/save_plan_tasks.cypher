MATCH (plan:Plan {id: $plan_id})
WITH plan
UNWIND $tasks AS row
MERGE (task:PlanTask {id: row.id})
ON CREATE SET task.task_id = row.task_id, task.target_ids = row.target_ids,
    task.payload = row.payload, task.stale = false
MERGE (plan)-[:HAS_TASK]->(task)
WITH task, row
UNWIND row.versions AS version_id
MATCH (version:FactVersion {id: version_id})
MERGE (task)-[:USED_FACT]->(version)
RETURN count(*)
