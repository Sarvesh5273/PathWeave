MATCH (plan:Plan {profile_id: $profile_id})
WHERE plan.complete = true
RETURN plan.payload, plan.lifecycle_status, plan.stale
ORDER BY plan.created_at DESC, plan.id DESC
LIMIT 1
