UNWIND $links AS row
MATCH (f:Fact {id: row.fact_id}), (t:Topic {key: row.topic_key})
MERGE (f)-[:MAPS_TO]->(t)
RETURN count(*)
