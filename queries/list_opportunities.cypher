MATCH (o:Opportunity)
OPTIONAL MATCH (o)-[:HAS_FACT]->(f:Fact)-[:CURRENT]->(:FactVersion)
WHERE coalesce(f.provenance, 'source_fact') <> 'graph_metadata'
RETURN o.payload, collect(f.payload)
ORDER BY o.id
LIMIT 100
