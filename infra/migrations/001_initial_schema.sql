-- Initial PostgreSQL Schema for AI BA Agent
-- Run this migration after Docker containers start

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'ba',  -- admin, ba, pm, business_owner, legal, finance, viewer
    full_name VARCHAR(255),  
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(user_id),
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',  -- active, archived, draft
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-Project role mapping (RBAC)
CREATE TABLE IF NOT EXISTS user_projects (
    user_id UUID NOT NULL REFERENCES users(user_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    role VARCHAR(50) NOT NULL,  -- ba, pm, business_owner, legal, finance, viewer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, project_id)
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    title VARCHAR(500) NOT NULL,
    doc_type VARCHAR(100),  -- meeting_minutes, brd, urs, contract, email_digest
    status VARCHAR(50) DEFAULT 'draft',  -- draft, pending_approval, approved, published
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(255),
    google_drive_link TEXT,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document versions
CREATE TABLE IF NOT EXISTS document_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    content TEXT,
    content_hash VARCHAR(255),
    created_by UUID REFERENCES users(user_id),
    approval_status VARCHAR(50) DEFAULT 'pending',  -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Approval workflows
CREATE TABLE IF NOT EXISTS approval_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    version_id UUID REFERENCES document_versions(version_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    current_step INT DEFAULT 1,
    total_steps INT,
    status VARCHAR(50) DEFAULT 'in_progress',  -- in_progress, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Approval decisions
CREATE TABLE IF NOT EXISTS approval_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES approval_workflows(workflow_id),
    step_number INT NOT NULL,
    approver_id UUID NOT NULL REFERENCES users(user_id),
    decision VARCHAR(50) NOT NULL,  -- approved, rejected, pending
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id UUID,
    user_id UUID REFERENCES users(user_id),
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    succeeded BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent state (Workflow orchestration)
CREATE TABLE IF NOT EXISTS agent_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES approval_workflows(workflow_id),
    agent_name VARCHAR(100) NOT NULL,
    state_data JSONB NOT NULL,
    parent_agent VARCHAR(100),
    next_agent VARCHAR(100),
    handoff_data JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation history (Memory Agent)
CREATE TABLE IF NOT EXISTS conversation_history (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    user_message TEXT NOT NULL,
    agent_response TEXT,
    context_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document embeddings metadata (RAG indexing)
CREATE TABLE IF NOT EXISTS document_embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    section_number INT,
    section_title VARCHAR(255),
    embedding_vector_id VARCHAR(255),  -- Reference to Qdrant collection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_user_projects_user_id ON user_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_user_projects_project_id ON user_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_project_id ON audit_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_doc_id ON approval_workflows(doc_id);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_project_id ON approval_workflows(project_id);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_status ON approval_workflows(status);
CREATE INDEX IF NOT EXISTS idx_conversation_history_user_id ON conversation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_history_project_id ON conversation_history(project_id);
CREATE INDEX IF NOT EXISTS idx_document_embeddings_project_id ON document_embeddings(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_state_workflow_id ON agent_state(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_state_expires_at ON agent_state(expires_at);

-- Seed test admin user (password: password123)
INSERT INTO users (user_id, email, password_hash, role, full_name) 
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'admin@ai-ba.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKgMn0dMkHU4MIW', 'admin', 'Administrator')
ON CONFLICT (email) DO NOTHING;

-- Additional test users are seeded in 003_seed_data.sql

-- Seed test project
INSERT INTO projects (project_id, name, owner_id, description, status)
VALUES ('660e8400-e29b-41d4-a716-446655440000', 'AI BA Agent MVP', '550e8400-e29b-41d4-a716-446655440000', 'Test project for AI BA Agent', 'active')
ON CONFLICT (project_id) DO NOTHING;

-- Assign admin user to project
INSERT INTO user_projects (user_id, project_id, role)
VALUES ('550e8400-e29b-41d4-a716-446655440000', '660e8400-e29b-41d4-a716-446655440000', 'admin')
ON CONFLICT (user_id, project_id) DO NOTHING;
