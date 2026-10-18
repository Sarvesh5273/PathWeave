UNWIND $resources AS row
MERGE (r:Resource {id: row.id})
SET r.title = row.title, r.url = row.url, r.provenance = row.provenance
WITH r, row
MATCH (t:Topic {key: row.topic})
MERGE (r)-[:COVERS]->(t)
RETURN count(*)
