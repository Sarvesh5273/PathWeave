MATCH (f:Fact)
WHERE f.id STARTS WITH $prefix
OPTIONAL MATCH (f)-[old:MAPS_TO]->(:Topic)
DELETE old
RETURN count(f)
