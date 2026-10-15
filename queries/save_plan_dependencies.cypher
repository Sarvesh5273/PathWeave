UNWIND $dependencies AS row
MATCH (task:PlanTask {id: row.task_id}), (prerequisite:PlanTask {id: row.prerequisite_id})
MERGE (task)-[:DEPENDS_ON]->(prerequisite)
RETURN count(*)
