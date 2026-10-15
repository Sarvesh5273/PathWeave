MATCH (o:Opportunity {id: $opportunity_id})
SET o.recipe_ready = true
RETURN o.id
