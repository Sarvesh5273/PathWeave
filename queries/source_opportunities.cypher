MATCH (opportunity:Opportunity)
OPTIONAL MATCH (opportunity)-[:HAS_FACT]->(fact:Fact)
WHERE opportunity.source_url = $source_url OR fact.source_url = $source_url
RETURN DISTINCT opportunity.id
LIMIT 101
