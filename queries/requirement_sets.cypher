MATCH (o:Opportunity)-[:HAS_FACT]->(guard:Fact)-[:CURRENT]->(version:FactVersion)
WHERE o.id IN $selected_ids AND guard.name = 'requirement_set' AND guard.provenance = 'graph_metadata'
RETURN o.id, guard.id, version.id, guard.payload
LIMIT 4
