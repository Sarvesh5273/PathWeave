MATCH (o:Opportunity {id: $opportunity_id})
OPTIONAL MATCH (o)-[requirement:REQUIRES]->(deliverable:Deliverable)
OPTIONAL MATCH (:PrepTask)-[support:SUPPORTS]->(deliverable)
DELETE support, requirement
RETURN o.id
