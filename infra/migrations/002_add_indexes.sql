-- AI BA Agent - Performance Indexes & Optimization (MVP Phase 1)
-- Database: PostgreSQL 15
-- Date: 2026-03-15
-- Purpose: Add optimized indexes for high-frequency queries

-- ============================================================================
-- COMPOSITE INDEXES FOR COMMON QUERIES
-- ============================================================================

-- Project-scoped document queries (most common pattern)
CREATE INDEX IF NOT EXISTS idx_docs_project_status_created 
    ON documents(project_id, status, created_at DESC);

-- Version approval workflow tracking
CREATE INDEX IF NOT EXISTS idx_versions_doc_approval_created 
    ON document_versions(doc_id, approval_status, created_at DESC);

-- Approval workflow pending items
CREATE INDEX IF NOT EXISTS idx_workflows_project_status_step 
    ON approval_workflows(project_id, status, current_step);

-- User audit trail
CREATE INDEX IF NOT EXISTS idx_audit_user_entity_time 
    ON audit_logs(user_id, entity_type, created_at DESC);

-- ============================================================================
-- FULL-TEXT SEARCH INDEXES (for RAG fallback)
-- ============================================================================

-- Document content full-text search
CREATE INDEX IF NOT EXISTS idx_documents_fulltext_title 
    ON documents USING GIN(to_tsvector('english', title));

-- Document versions full-text search
CREATE INDEX IF NOT EXISTS idx_versions_fulltext_content 
    ON document_versions USING GIN(to_tsvector('english', content));

-- ============================================================================
-- JSONB INDEXES (for flexible querying)
-- ============================================================================

-- Agent state data queries
CREATE INDEX IF NOT EXISTS idx_agent_state_jsonb 
    ON agent_state USING GIN(state_data);

-- Audit log old/new values
CREATE INDEX IF NOT EXISTS idx_audit_logs_jsonb 
    ON audit_logs USING GIN(old_values, new_values);

-- Conversation context queries
CREATE INDEX IF NOT EXISTS idx_conversation_jsonb 
    ON conversation_history USING GIN(context_data);

-- ============================================================================
-- UNIQUE CONSTRAINTS (data integrity)
-- ============================================================================

-- Project email uniqueness per project (soft constraint by app logic)
-- Note: Database-level uniqueness would limit multi-user projects
-- Enforced at application level instead

-- ============================================================================
-- PARTITIONING STRATEGY (for future scaling - Phase 2)
-- ============================================================================

-- Recommendation: Partition audit_logs by date (monthly)
-- Recommendation: Partition agent_state by project_id for distributed queries
-- Deferred until data volume exceeds 100GB

-- ============================================================================
-- STATISTICS & QUERY OPTIMIZATION
-- ============================================================================

-- Analyze tables after index creation (improves query planner)
ANALYZE documents;
ANALYZE document_versions;
ANALYZE approval_workflows;
ANALYZE audit_logs;
ANALYZE agent_state;

-- ============================================================================
-- END OF OPTIMIZATION SCRIPT
-- ============================================================================
