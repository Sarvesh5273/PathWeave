UNWIND $links AS row
MATCH (task:PrepTask {id: row.task_id}), (fact:Fact {id: row.fact_id})
MERGE (task)-[:USES_FACT]->(fact)
RETURN count(*)
