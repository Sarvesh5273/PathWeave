MATCH (version:FactVersion)
WHERE version.id IN $version_ids
RETURN version.id, version.fact_id
LIMIT 196
