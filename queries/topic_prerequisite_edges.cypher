UNWIND $edges AS row
MATCH (prerequisite:Topic {key: row.prerequisite}), (topic:Topic {key: row.topic})
MERGE (prerequisite)-[:PREREQUISITE_OF]->(topic)
RETURN count(*)
