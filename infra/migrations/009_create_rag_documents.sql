CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    added_by UUID NOT NULL REFERENCES users(user_id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CONSTRAINT rag_documents_status_check CHECK (status IN ('indexed', 'pending')),
    CONSTRAINT rag_documents_doc_id_unique UNIQUE (doc_id)
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_project_id ON rag_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_rag_documents_status ON rag_documents(status);
