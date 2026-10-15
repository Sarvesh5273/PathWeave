UNWIND $tasks AS row
MERGE (task:PrepTask {id: row.id})
SET task.payload = row.payload, task.title = row.title,
    task.fact_names = row.fact_names, task.provenance = row.provenance
WITH task
OPTIONAL MATCH (task)-[old:DEPENDS_ON|USES_FACT]->()
DELETE old
RETURN count(DISTINCT task)
