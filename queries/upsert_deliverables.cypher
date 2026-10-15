MATCH (o:Opportunity {id: $opportunity_id})
WITH o
UNWIND $deliverables AS row
MATCH (task:PrepTask {id: row.task_id})
MERGE (deliverable:Deliverable {id: row.id})
SET deliverable.name = row.name, deliverable.provenance = row.provenance
MERGE (o)-[:REQUIRES]->(deliverable)
MERGE (task)-[:SUPPORTS]->(deliverable)
RETURN count(*)
