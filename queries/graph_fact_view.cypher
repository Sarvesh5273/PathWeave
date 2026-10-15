MATCH path = (o:Opportunity)-[:HAS_FACT]->(fact:Fact)-[:CURRENT]->(:FactVersion)-[:SUPPORTED_BY]->(source:Source)
WHERE o.id IN $selected_ids AND source.id = fact.source_node_id
RETURN path
LIMIT 193
