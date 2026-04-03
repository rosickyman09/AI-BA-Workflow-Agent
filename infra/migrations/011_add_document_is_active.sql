-- 011_add_document_is_active.sql
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_documents_is_active
ON documents(is_active);

COMMENT ON COLUMN documents.is_active IS
'Active = visible in Generate URS and Knowledge Base.
Inactive = hidden from selection but not deleted.
Only project_owner/business_owner can change.';
