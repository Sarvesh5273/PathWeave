MATCH (o:Opportunity {id: $opportunity_id})
OPTIONAL MATCH (o)-[:HAS_FACT]->(f:Fact)-[:CURRENT]->(:FactVersion)
WHERE coalesce(f.provenance, 'source_fact') <> 'graph_metadata'
RETURN o.payload, collect(f.payload), o.recipe_ready
