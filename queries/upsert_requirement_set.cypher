MATCH (o:Opportunity {id: $opportunity_id})
MERGE (guard:Fact {id: $requirement_set.id})
SET guard.name = 'requirement_set', guard.opportunity_id = $opportunity_id,
    guard.payload = $requirement_set.payload, guard.provenance = 'graph_metadata'
MERGE (o)-[:HAS_FACT]->(guard)
MERGE (version:FactVersion {id: $requirement_set.version_id})
ON CREATE SET version.payload = $requirement_set.payload, version.fact_id = guard.id,
    version.opportunity_id = $opportunity_id, version.name = 'requirement_set',
    version.kind = 'information', version.status = 'known',
    version.value_json = $requirement_set.value_json, version.created_at = $checked_at,
    version.provenance = 'graph_metadata', version.requirement_names = $requirement_set.names
WITH guard, version
OPTIONAL MATCH (guard)-[current:CURRENT]->(previous:FactVersion)
WITH guard, version, current, previous
DELETE current
MERGE (guard)-[:CURRENT]->(version)
MERGE (metadata:GraphMetadata {id: 'requirement-set-v1'})
ON CREATE SET metadata.description = 'Graph-derived membership of hard requirement fact names and kinds; not an official source rule',
    metadata.provenance = 'graph_metadata'
MERGE (version)-[:DERIVED_FROM]->(metadata)
RETURN guard.id, coalesce(previous.id, ''), version.id
