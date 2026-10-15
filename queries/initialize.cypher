MERGE (meta:GraphMetadata {id: 'just-chill-schema'})
ON CREATE SET meta.version = 1
RETURN meta.version
