-- Migration 008: Enforce allowed project statuses including frozen
ALTER TABLE projects
DROP CONSTRAINT IF EXISTS projects_status_check;

ALTER TABLE projects
ADD CONSTRAINT projects_status_check
CHECK (status IN ('active', 'inactive', 'completed', 'frozen'));
