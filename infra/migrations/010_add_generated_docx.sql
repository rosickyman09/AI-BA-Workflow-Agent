-- Store pre-built .docx bytes so download/save never re-runs the LLM
ALTER TABLE urs_generated_docs ADD COLUMN IF NOT EXISTS generated_docx BYTEA;
ALTER TABLE urs_generated_docs ADD COLUMN IF NOT EXISTS placeholder_summary JSONB DEFAULT '{}';
