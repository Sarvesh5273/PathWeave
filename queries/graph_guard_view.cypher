MATCH path = (o:Opportunity)-[:HAS_FACT]->(guard:Fact)-[:CURRENT]->(:FactVersion)-[:DERIVED_FROM]->(:GraphMetadata)
WHERE o.id IN $selected_ids AND guard.provenance = 'graph_metadata'
RETURN path
LIMIT 4
