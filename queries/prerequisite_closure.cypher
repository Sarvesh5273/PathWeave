MATCH (o:Opportunity)
WHERE o.id IN $selected_ids AND o.recipe_ready = true
MATCH path = (o)-[:REQUIRES]->(:Deliverable)<-[:SUPPORTS]-(:PrepTask)-[:DEPENDS_ON*0..8]->(task:PrepTask)
OPTIONAL MATCH (task)-[:DEPENDS_ON]->(prerequisite:PrepTask)
RETURN DISTINCT o.id, task.id, task.payload,
       [node IN nodes(path) | node.id],
       [edge IN relationships(path) | type(edge)], collect(DISTINCT prerequisite.id)
ORDER BY o.id, task.id
LIMIT 1001
