MATCH (plan:Plan {id: $plan_id})
SET plan.complete = true, plan.stale = $stale
RETURN plan.id
