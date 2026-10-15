MERGE (plan:Plan {id: $plan_id})
ON CREATE SET plan.payload = $payload, plan.profile_id = $profile_id,
    plan.created_at = $created_at, plan.lifecycle_status = 'proposed',
    plan.complete = false, plan.stale = false
RETURN plan.payload, plan.complete
