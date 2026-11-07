-- An empty row keeps the revision after clearing, so old clients cannot resurrect it.
CREATE TABLE planning_contexts (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    summary TEXT NOT NULL CHECK(length(summary) <= 1000),
    preferences TEXT NOT NULL,
    plan_id TEXT REFERENCES plans(id) ON DELETE SET NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    updated_at TEXT NOT NULL
);

-- Deleting the linked plan clears its context too, while retaining the version counter.
CREATE TRIGGER clear_deleted_plan_context BEFORE DELETE ON plans
BEGIN
    UPDATE planning_contexts SET summary='', preferences='[]', plan_id=NULL,
        revision=revision+1, updated_at=strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
        WHERE plan_id=OLD.id;
END;
