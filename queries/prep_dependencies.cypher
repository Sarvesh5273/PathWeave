UNWIND $dependencies AS row
MATCH (task:PrepTask {id: row.task_id}), (prerequisite:PrepTask {id: row.prerequisite_id})
MERGE (task)-[:DEPENDS_ON]->(prerequisite)
RETURN count(*)
