MATCH (o:Opportunity)-[:HAS_FACT]->(f:Fact)-[:MAPS_TO]->(t:Topic)
WHERE o.id IN $selected_ids
RETURN DISTINCT o.id, f.id, t.key, t.payload
LIMIT 200
