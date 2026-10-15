MATCH (o:Opportunity)
WHERE o.id IN $selected_ids
MATCH (o)-[:REQUIRES]->(:Deliverable)<-[:SUPPORTS]-(:PrepTask)-[:DEPENDS_ON*8]->(task:PrepTask)-[:DEPENDS_ON]->(:PrepTask)
RETURN o.id, task.id
LIMIT 1
