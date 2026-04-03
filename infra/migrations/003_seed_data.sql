-- AI BA Agent - Seed Data (MVP Phase 1)
-- Database: PostgreSQL 15
-- Date: 2026-03-15
-- Purpose: Initialize test users and projects for development

-- ============================================================================
-- TEST USERS (for development and testing)
-- ============================================================================

-- Hash passwords using bcrypt (example hashes below - CHANGE IN PRODUCTION)
-- Password format: bcrypt hash of plain text password
-- For testing, all passwords are "password123"

-- Note: admin@ai-ba.local is already seeded in 001_initial_schema.sql
-- This file adds ADDITIONAL test users only
INSERT INTO users (user_id, email, password_hash, role, full_name) VALUES
    -- Business Analyst users (additional)
    ('550e8400-e29b-41d4-a716-446655440001', 'ba1@ai-ba.local',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKgMn0dMkHU4MIW', 'ba', 'BA User 1'),
    
    ('550e8400-e29b-41d4-a716-446655440002', 'ba2@ai-ba.local',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKgMn0dMkHU4MIW', 'ba', 'BA User 2'),
    
    -- Project Owner
    ('550e8400-e29b-41d4-a716-446655440003', 'owner@ai-ba.local',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKgMn0dMkHU4MIW', 'business_owner', 'Project Owner')
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role          = EXCLUDED.role,
    full_name     = EXCLUDED.full_name;

-- ============================================================================
-- TEST PROJECTS (for development and testing)
-- ============================================================================

INSERT INTO projects (project_id, name, owner_id, description, status) VALUES
    ('660e8400-e29b-41d4-a716-446655440000', 'Project Alpha',
     '550e8400-e29b-41d4-a716-446655440003',
     'MVP test project for AI BA Agent development',
     'active'),
    
    ('660e8400-e29b-41d4-a716-446655440001', 'Project Beta',
     '550e8400-e29b-41d4-a716-446655440003',
     'Secondary test project for multi-project testing',
     'active')
ON CONFLICT (project_id) DO NOTHING;

-- ============================================================================
-- USER-PROJECT ASSIGNMENTS (RBAC)
-- ============================================================================

INSERT INTO user_projects (user_id, project_id, role) VALUES
    -- Admin has access to all projects
    ('550e8400-e29b-41d4-a716-446655440000', '660e8400-e29b-41d4-a716-446655440000', 'ba'),
    ('550e8400-e29b-41d4-a716-446655440000', '660e8400-e29b-41d4-a716-446655440001', 'ba'),
    
    -- BA users in Project Alpha
    ('550e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440000', 'ba'),
    ('550e8400-e29b-41d4-a716-446655440002', '660e8400-e29b-41d4-a716-446655440000', 'ba'),
    
    -- BA user in Project Beta
    ('550e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440001', 'pm'),
    
    -- Owner in own projects
    ('550e8400-e29b-41d4-a716-446655440003', '660e8400-e29b-41d4-a716-446655440000', 'business_owner'),
    ('550e8400-e29b-41d4-a716-446655440003', '660e8400-e29b-41d4-a716-446655440001', 'business_owner')
ON CONFLICT (user_id, project_id) DO NOTHING;

-- ============================================================================
-- TEST DOCUMENTS (for development and testing)
-- ============================================================================

INSERT INTO documents (doc_id, project_id, title, doc_type, status, created_by) VALUES
    ('770e8400-e29b-41d4-a716-446655440000', '660e8400-e29b-41d4-a716-446655440000',
     'Q1 Planning Meeting Minutes', 'meeting_minutes', 'draft',
     '550e8400-e29b-41d4-a716-446655440001'),
    
    ('770e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440000',
     'Project Alpha BRD', 'brd', 'approved',
     '550e8400-e29b-41d4-a716-446655440001')
ON CONFLICT (doc_id) DO NOTHING;

-- ============================================================================
-- TEST VERSIONS (for document version control testing)
-- ============================================================================

INSERT INTO document_versions (version_id, doc_id, version_number, content, created_by, approval_status) VALUES
    ('880e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440000', 1,
     '# Q1 Planning Meeting Minutes
     
## Attendees
- BA User 1
- PM User
- Project Owner

## Decisions
- Launch product in Q2

## Action Items
- Backend team: Build API by 2026-04-30
- Frontend team: Build UI by 2026-04-15

## Risks
- Resource constraint in Q1
- Budget overrun risk',
     '550e8400-e29b-41d4-a716-446655440001', 'approved')
ON CONFLICT (version_id) DO NOTHING;

-- ============================================================================
-- STATISTICS & ANALYSIS
-- ============================================================================

-- Make sure the query planner has up-to-date statistics
ANALYZE;

-- ============================================================================
-- END OF SEED DATA
-- ============================================================================
