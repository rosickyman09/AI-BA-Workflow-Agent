# Database Schema & Data Model
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1  
**Database:** PostgreSQL 15

---

## 1. Schema Overview

### 1.1 Database Design Principles

- **Normalization:** 3NF (Third Normal Form)
- **Foreign Keys:** All parent references enforced with CASCADE DELETE
- **Indexing:** Strategic indexing on frequently searched columns
- **Partitioning:** Large tables partitioned by date for performance
- **Backup:** Daily incremental backups + weekly full backup

### 1.2 Core Tables

```
Users (1) ──→ (M) Documents
Users (1) ──→ (M) Queries
Users (1) ──→ (M) Tasks
Documents (1) ──→ (M) Document_Chunks
Document_Chunks (1) ──→ (M) Embeddings
Tasks (1) ──→ (M) Task_Steps
Tasks (1) ──→ (M) Task_Results
Agents (1) ──→ (M) Agent_Executions
```

---

## 2. Core Tables

### 2.1 Users Table

**Purpose:** Store user accounts and authentication  
**Schema:**

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  company VARCHAR(255),
  password_hash VARCHAR(255) NOT NULL,
  roles TEXT[] DEFAULT ARRAY['user'],
  
  -- Account Status
  is_active BOOLEAN DEFAULT TRUE,
  is_verified BOOLEAN DEFAULT FALSE,
  verification_token VARCHAR(255),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_login TIMESTAMP,
  
  -- Indexes
  INDEX idx_email (email),
  INDEX idx_company (company),
  INDEX idx_created_at (created_at)
);
```

**Columns:**
- `id`: Unique user identifier (UUID)
- `email`: Unique email address
- `name`: User full name
- `company`: Organization name
- `password_hash`: bcrypt hash (cost: 12)
- `roles`: Array of role strings (user, analyst, admin)
- `is_active`: Account enabled flag
- `is_verified`: Email verification status
- `created_at`: Account creation date
- `last_login`: Last login timestamp

---

### 2.2 Documents Table

**Purpose:** Store uploaded documents and metadata  
**Schema:**

```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Document Info
  title VARCHAR(500) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(1000),
  file_size_bytes BIGINT,
  file_type VARCHAR(50), -- pdf, docx, xlsx, txt, etc.
  
  -- Processing Status
  status VARCHAR(50) DEFAULT 'pending', -- pending, processing, processed, failed
  error_message TEXT,
  
  -- Categories
  category VARCHAR(100), -- knowledge_base, training, reference, etc.
  tags TEXT[],
  
  -- Extraction Results
  total_pages INT,
  total_chunks INT,
  embedding_status VARCHAR(50), -- pending, in_progress, completed, failed
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_category (category),
  INDEX idx_created_at (created_at),
  FULLTEXT INDEX idx_title_search (title, file_name)
);
```

**Columns:**
- `id`: Document unique identifier
- `user_id`: Owner/uploader user ID
- `title`: Document title
- `file_name`: Original file name
- `file_path`: Storage location (S3/local)
- `file_size_bytes`: File size in bytes
- `file_type`: MIME type
- `status`: Processing status (pending → processing → processed/failed)
- `category`: Document classification
- `tags`: Custom tags for organization
- `total_pages`: Page count (for PDFs)
- `total_chunks`: Number of text chunks created
- `embedding_status`: Vector embedding status

---

### 2.3 Document_Chunks Table

**Purpose:** Store text chunks from documents (for RAG)  
**Schema:**

```sql
CREATE TABLE document_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  
  -- Chunk Content
  chunk_number INT NOT NULL,
  page_number INT,
  content TEXT NOT NULL,
  content_summary VARCHAR(1000),
  
  -- Embedding
  embedding_vector VECTOR(384), -- Qdrant will handle actual embeddings
  embedding_created_at TIMESTAMP,
  
  -- Metadata
  char_count INT,
  word_count INT,
  is_indexed BOOLEAN DEFAULT FALSE,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_document_id (document_id),
  INDEX idx_page_number (page_number),
  INDEX idx_is_indexed (is_indexed),
  FULLTEXT INDEX idx_content_search (content)
);
```

**Columns:**
- `id`: Chunk unique identifier
- `document_id`: Parent document ID
- `content`: Text content of the chunk
- `page_number`: Page reference (for PDFs)
- `embedding_vector`: Vector embedding (managed by Qdrant)
- `word_count`: Word count for token estimation
- `is_indexed`: Flag to track indexing status

---

### 2.4 Embeddings Table

**Purpose:** Store vector embeddings (redundant for Qdrant, but for backup)  
**Schema:**

```sql
CREATE TABLE embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
  
  -- Embedding Details
  embedding_model VARCHAR(100), -- all-MiniLM-L6-v2, etc.
  embedding_dimension INT, -- 384, 768, 1536, etc.
  embedding_vector VECTOR(1536), -- Max dimension
  
  -- Metadata
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Index
  INDEX idx_chunk_id (chunk_id),
  INDEX idx_embedding_model (embedding_model)
);
```

---

### 2.5 Queries Table

**Purpose:** Log and track user queries  
**Schema:**

```sql
CREATE TABLE queries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Query Content
  query_text TEXT NOT NULL,
  query_type VARCHAR(50), -- search, ai_answer, conversation
  conversation_id UUID, -- For multi-turn conversations
  
  -- Search Results
  results_count INT,
  top_result_relevance DECIMAL(3, 2),
  
  -- Response
  response_text TEXT,
  response_tokens_in INT,
  response_tokens_out INT,
  
  -- Performance
  duration_ms INT,
  model_used VARCHAR(100),
  
  -- Status
  status VARCHAR(50), -- success, partial, failed
  error_message TEXT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_conversation_id (conversation_id),
  INDEX idx_query_type (query_type),
  INDEX idx_created_at (created_at),
  FULLTEXT INDEX idx_query_text (query_text)
);
```

---

### 2.6 Conversations Table

**Purpose:** Store multi-turn conversation sessions  
**Schema:**

```sql
CREATE TABLE conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Conversation Metadata
  title VARCHAR(500),
  status VARCHAR(50) DEFAULT 'active', -- active, archived, deleted
  total_messages INT DEFAULT 0,
  
  -- Context
  context_type VARCHAR(100), -- general, document_focused, task_focused
  related_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
  
  -- Performance Tracking
  total_tokens_used INT,
  total_cost_usd DECIMAL(10, 4),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_message_at TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
```

---

### 2.7 Conversation_Messages Table

**Purpose:** Store individual messages in conversations  
**Schema:**

```sql
CREATE TABLE conversation_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  
  -- Message Content
  role VARCHAR(50), -- user, assistant, system
  content TEXT NOT NULL,
  message_number INT NOT NULL,
  
  -- Token Usage
  tokens_in INT,
  tokens_out INT,
  
  -- Metadata
  model_used VARCHAR(100),
  citations TEXT[], -- JSON references to sources
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_conversation_id (conversation_id),
  INDEX idx_role (role),
  INDEX idx_created_at (created_at)
);
```

---

### 2.8 Tasks Table

**Purpose:** Store workflow tasks and jobs  
**Schema:**

```sql
CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  
  -- Task Information
  title VARCHAR(500) NOT NULL,
  description TEXT,
  workflow_type VARCHAR(100), -- multi_step_analysis, data_extraction, etc.
  
  -- Assignment
  assigned_agent_id VARCHAR(100),
  priority VARCHAR(50), -- low, medium, high, critical
  
  -- Status
  status VARCHAR(50) DEFAULT 'created', 
  -- created → queued → in_progress → completed/failed/cancelled
  progress_percent INT DEFAULT 0,
  
  -- Results
  result_data JSONB,
  result_summary TEXT,
  
  -- Timings
  due_date TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_seconds INT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_assigned_agent_id (assigned_agent_id),
  INDEX idx_priority (priority),
  INDEX idx_created_at (created_at),
  INDEX idx_due_date (due_date)
);
```

---

### 2.9 Task_Steps Table

**Purpose:** Track sub-steps within tasks  
**Schema:**

```sql
CREATE TABLE task_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  
  -- Step Information
  step_number INT NOT NULL,
  step_name VARCHAR(255) NOT NULL,
  step_description TEXT,
  
  -- Status
  status VARCHAR(50), -- pending, in_progress, completed, failed, skipped
  
  -- Execution Details
  input_data JSONB,
  output_data JSONB,
  error_message TEXT,
  
  -- Timings
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_ms INT,
  
  -- Execution Info
  executed_by VARCHAR(100), -- Agent or system name
  retry_count INT DEFAULT 0,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_task_id (task_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
```

---

### 2.10 Agents Table

**Purpose:** Store AI agent definitions  
**Schema:**

```sql
CREATE TABLE agents (
  id VARCHAR(100) PRIMARY KEY, -- agent_001, agent_002, etc.
  
  -- Agent Information
  name VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  type VARCHAR(100), -- analyst, assistant, coordinator, etc.
  
  -- Capabilities
  capabilities TEXT[],
  skills JSONB, -- {skill_name: description, ...}
  
  -- Configuration
  model_used VARCHAR(100),
  temperature DECIMAL(3, 2),
  max_tokens INT,
  
  -- Status
  is_active BOOLEAN DEFAULT TRUE,
  version VARCHAR(50),
  
  -- Performance Tracking
  total_tasks_completed INT DEFAULT 0,
  success_rate DECIMAL(3, 2),
  avg_response_time_ms INT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used TIMESTAMP,
  
  -- Indexes
  INDEX idx_name (name),
  INDEX idx_type (type),
  INDEX idx_is_active (is_active)
);
```

---

### 2.11 Agent_Executions Table

**Purpose:** Track agent execution history  
**Schema:**

```sql
CREATE TABLE agent_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id VARCHAR(100) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
  
  -- Execution Details
  input_prompt TEXT,
  output_response TEXT,
  
  -- Performance
  duration_ms INT,
  tokens_used INT,
  cost_usd DECIMAL(10, 4),
  
  -- Status
  status VARCHAR(50), -- success, partial, failed
  error_message TEXT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_agent_id (agent_id),
  INDEX idx_task_id (task_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
```

---

## 3. Supporting Tables

### 3.1 Audit_Log Table

**Purpose:** Track user activity and system changes  
**Schema:**

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  
  -- Action
  action VARCHAR(100), -- login, upload_document, query, create_task, etc.
  resource_type VARCHAR(100), -- users, documents, queries, tasks, etc.
  resource_id VARCHAR(255),
  
  -- Changes
  change_data JSONB, -- {field: {old: value, new: value}, ...}
  
  -- Metadata
  ip_address VARCHAR(45),
  user_agent VARCHAR(500),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_action (action),
  INDEX idx_resource_type (resource_type),
  INDEX idx_created_at (created_at)
);
```

---

### 3.2 API_Keys Table

**Purpose:** Store API credentials for external services  
**Schema:**

```sql
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Key Information
  key_name VARCHAR(255),
  key_type VARCHAR(100), -- openai, openrouter, qdrant, etc.
  encrypted_key TEXT NOT NULL,
  
  -- Usage Tracking
  total_requests INT DEFAULT 0,
  last_used TIMESTAMP,
  
  -- Status
  is_active BOOLEAN DEFAULT TRUE,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP,
  
  -- Indexes
  INDEX idx_user_id (user_id),
  INDEX idx_key_type (key_type),
  INDEX idx_is_active (is_active)
);
```

---

### 3.3 System_Config Table

**Purpose:** Store system-wide configuration  
**Schema:**

```sql
CREATE TABLE system_config (
  id SERIAL PRIMARY KEY,
  
  -- Configuration
  config_key VARCHAR(255) NOT NULL UNIQUE,
  config_value TEXT NOT NULL,
  data_type VARCHAR(50), -- string, integer, boolean, json
  
  -- Metadata
  description TEXT,
  is_secret BOOLEAN DEFAULT FALSE,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Index
  INDEX idx_config_key (config_key)
);
```

---

## 4. Indexes & Performance

### 4.1 Critical Indexes

```sql
-- Query Performance
CREATE INDEX idx_queries_user_created 
  ON queries(user_id, created_at DESC);

CREATE INDEX idx_document_chunks_search 
  ON document_chunks USING FULLTEXT (content);

-- Task Performance
CREATE INDEX idx_tasks_user_status 
  ON tasks(user_id, status);

-- Conversation Performance
CREATE INDEX idx_conversations_user_updated 
  ON conversations(user_id, updated_at DESC);

-- Audit Performance
CREATE INDEX idx_audit_logs_temporal 
  ON audit_logs(created_at DESC, user_id);
```

### 4.2 Index Maintenance

**Rebuild Indexes (Weekly):**
```sql
ANALYZE;
REINDEX DATABASE ai_ba_agent;
```

---

## 5. Data Retention & Partitioning

### 5.1 Partition Strategy

**Large Tables:** Partition by date for performance

```sql
-- Queries partitioned by month
CREATE TABLE queries_2026_03 PARTITION OF queries
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE queries_2026_04 PARTITION OF queries
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

### 5.2 Retention Policies

| Table | Retention | Action |
|-------|-----------|--------|
| `audit_logs` | 2 years | Archive to cold storage |
| `queries` | 1 year | Archive or delete |
| `agent_executions` | 180 days | Archive or delete |
| `api_keys` | Never | Keep indefinitely |
| `users` | Never | Keep indefinitely (soft delete) |
| `documents` | No policy | User-controlled deletion |

---

## 6. Sample Queries

### 6.1 Find Recent User Queries

```sql
SELECT q.*, d.title as document_source
FROM queries q
LEFT JOIN documents d ON q.id = STRING_TO_ARRAY(q.response_text, ',')[1]::uuid
WHERE q.user_id = 'user_id' 
  AND q.created_at > NOW() - INTERVAL '30 days'
ORDER BY q.created_at DESC
LIMIT 50;
```

### 6.2 Document Processing Status

```sql
SELECT 
  id,
  title,
  status,
  total_pages,
  total_chunks,
  embedding_status,
  created_at,
  processed_at
FROM documents
WHERE user_id = 'user_id'
  AND status IN ('processing', 'pending')
ORDER BY created_at DESC;
```

### 6.3 Task Progress Tracking

```sql
SELECT 
  t.id,
  t.title,
  t.status,
  t.progress_percent,
  COUNT(ts.id) as total_steps,
  SUM(CASE WHEN ts.status = 'completed' THEN 1 ELSE 0 END) as completed_steps
FROM tasks t
LEFT JOIN task_steps ts ON t.id = ts.task_id
WHERE t.user_id = 'user_id'
GROUP BY t.id
ORDER BY t.created_at DESC;
```

---

## 7. Backup & Recovery

### 7.1 Backup Strategy

**Daily Schedule:**
```bash
# Full backup (weekly - Sunday)
pg_dump -h localhost -U postgres ai_ba_agent | gzip > /backups/full_$(date +%Y%m%d).sql.gz

# Incremental backup (daily)
pg_basebackup -h localhost -D /backups/incremental_$(date +%Y%m%d) -Ft
```

### 7.2 Recovery Procedure

```bash
# Restore from backup
gunzip < /backups/full_20260315.sql.gz | psql -h localhost -U postgres ai_ba_agent
```

---

## 8. Migration Strategy

### 8.1 Alembic Setup (Optional)

```bash
alembic init alembic
alembic revision -m "initial_schema"
alembic upgrade head
```

---

## END OF DATABASE SCHEMA DOCUMENT
