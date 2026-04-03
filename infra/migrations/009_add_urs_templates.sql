-- URS Templates table
CREATE TABLE IF NOT EXISTS urs_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_format VARCHAR(10) NOT NULL,
    google_drive_link VARCHAR(500),
    google_drive_file_id VARCHAR(255),
    detected_placeholders JSONB DEFAULT '[]',
    uploaded_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated URS Documents table
CREATE TABLE IF NOT EXISTS urs_generated_docs (
    generated_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES urs_templates(template_id),
    project_id UUID REFERENCES projects(project_id),
    title VARCHAR(255) NOT NULL,
    google_drive_link VARCHAR(500),
    google_drive_file_id VARCHAR(255),
    google_drive_folder VARCHAR(50) DEFAULT 'pending',
    source_doc_ids JSONB DEFAULT '[]',
    generated_content TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    generated_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW()
);
