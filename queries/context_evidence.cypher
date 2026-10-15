MATCH (o:Opportunity)
WHERE o.id IN $selected_ids AND o.recipe_ready = true
MATCH dependency = (o)-[:REQUIRES]->(:Deliverable)<-[:SUPPORTS]-(:PrepTask)-[:DEPENDS_ON*0..8]->(task:PrepTask)
MATCH evidence = (task)-[:USES_FACT]->(fact:Fact)-[:CURRENT]->(version:FactVersion)-[support:SUPPORTED_BY]->(source:Source)
WHERE source.id = fact.source_node_id
RETURN DISTINCT o.id, task.id,
       [node IN nodes(dependency) | node.id] + [node IN nodes(evidence) | node.id][1..],
       [edge IN relationships(dependency) | type(edge)] + [edge IN relationships(evidence) | type(edge)],
       source.url, support.excerpt
ORDER BY o.id, task.id
LIMIT 1001
