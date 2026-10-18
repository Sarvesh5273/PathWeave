UNWIND $topics AS row
MERGE (t:Topic {key: row.key})
SET t.title = row.title, t.family = row.family, t.payload = row.payload
RETURN count(DISTINCT t)
