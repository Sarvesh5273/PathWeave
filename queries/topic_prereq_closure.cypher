MATCH (o:Opportunity)-[:HAS_FACT]->(:Fact)-[:MAPS_TO]->(t0:Topic)
WHERE o.id IN $selected_ids
MATCH (p:Topic)-[:PREREQUISITE_OF*0..6]->(t0)
RETURN DISTINCT p.key, p.payload
LIMIT 200
