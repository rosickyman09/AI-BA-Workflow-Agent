-- Migration 004: Add Google Drive folder ID to projects table
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS google_drive_folder_id VARCHAR(255);
