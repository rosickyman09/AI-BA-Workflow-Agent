-- Migration 007: Add is_active column to users table
-- Supports user deactivation without data deletion

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
