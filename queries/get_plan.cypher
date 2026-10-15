MATCH (plan:Plan {id: $plan_id})
WHERE plan.complete = true
RETURN plan.payload, plan.lifecycle_status, plan.stale
