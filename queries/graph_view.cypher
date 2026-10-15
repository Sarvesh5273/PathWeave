MATCH (o:Opportunity)
WHERE o.id IN $selected_ids
MATCH path = (o)-[:REQUIRES]->(:Deliverable)<-[:SUPPORTS]-(:PrepTask)-[:DEPENDS_ON*0..8]->(:PrepTask)
RETURN path
LIMIT 301
