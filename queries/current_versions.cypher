MATCH (fact:Fact)-[:CURRENT]->(version:FactVersion)
WHERE fact.id IN $fact_ids
RETURN fact.id, version.id
LIMIT 196
