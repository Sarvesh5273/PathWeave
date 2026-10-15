MATCH (plan:Plan)-[:HAS_TASK]->(decision:PlanTask)
MATCH path = (decision)-[:DEPENDS_ON*0..8]->(:PlanTask)-[:USED_FACT]->(version:FactVersion)
WHERE version.id IN $old_version_ids AND plan.complete = true
SET decision.stale = true, plan.stale = true
WITH plan, decision, version, path
OPTIONAL MATCH (version)-[support:SUPPORTED_BY]->(source:Source)
RETURN DISTINCT plan.id, '', decision.task_id,
       [plan.id] + [node IN nodes(path) | node.id] + CASE WHEN source IS NULL THEN [] ELSE [source.id] END,
       source.url, support.excerpt,
       ['HAS_TASK'] + [edge IN relationships(path) | type(edge)] + CASE WHEN source IS NULL THEN [] ELSE ['SUPPORTED_BY'] END
LIMIT 1001
