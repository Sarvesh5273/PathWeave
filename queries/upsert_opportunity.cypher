MERGE (o:Opportunity {id: $opportunity_id})
SET o.payload = $opportunity_payload, o.program = $program,
    o.source_url = $source_url, o.recipe_ready = false
WITH o
UNWIND $facts AS row
MERGE (f:Fact {id: row.id})
SET f.name = row.name, f.opportunity_id = $opportunity_id,
    f.payload = row.payload, f.source_url = row.source_url,
    f.source_node_id = row.source_node_id, f.provenance = 'source_fact'
MERGE (o)-[:HAS_FACT]->(f)
MERGE (version:FactVersion {id: row.version_id})
ON CREATE SET version.payload = row.payload, version.fact_id = row.id,
    version.opportunity_id = $opportunity_id, version.name = row.name,
    version.status = row.status, version.kind = row.kind,
    version.value_json = row.value_json, version.created_at = $checked_at,
    version.provenance = 'source_fact'
WITH o, row, f, version
OPTIONAL MATCH (f)-[current:CURRENT]->(previous:FactVersion)
WITH o, row, f, version, previous, current
DELETE current
MERGE (f)-[:CURRENT]->(version)
MERGE (source:Source {id: row.source_node_id})
ON CREATE SET source.payload = row.source_payload, source.url = row.source_url,
    source.checked_at = row.source_checked_at, source.mode = row.source_mode,
    source.has_snapshot = row.has_snapshot, source.state = row.source_state
SET source.state = row.source_state
MERGE (version)-[support:SUPPORTED_BY]->(source)
SET support.excerpt = row.excerpt, support.checked_at = row.source_checked_at
RETURN row.id, coalesce(previous.id, ''), version.id
