-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
