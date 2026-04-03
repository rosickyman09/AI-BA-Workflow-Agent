# API Specification Document
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1  

---

## 1. API Overview

### 1.1 Base URLs

| Environment | URL | Protocol | Port |
|-------------|-----|----------|------|
| Development | `http://localhost` | HTTP | 80 |
| Staging | `https://staging.example.com` | HTTPS | 443 |
| Production | `https://api.example.com` | HTTPS | 443 |

### 1.2 API Standards

- **Format:** REST with JSON
- **Authentication:** JWT Bearer Token
- **Request Content-Type:** `application/json`
- **Response Content-Type:** `application/json`
- **API Version:** v1
- **Rate Limiting:** 100 req/min per user

### 1.3 Common Response Structure

```json
{
  "status": "success|error",
  "code": 200,
  "message": "Operation completed successfully",
  "data": { /* payload */ },
  "timestamp": "2026-03-15T10:30:00Z",
  "request_id": "req_abc123xyz"
}
```

---

## 2. Authentication & Security

### 2.1 JWT Token Structure

```bash
Header
{
  "alg": "HS256",
  "typ": "JWT"
}

Payload
{
  "sub": "user_id_12345",
  "email": "user@example.com",
  "roles": ["user", "analyst"],
  "iat": 1678953000,
  "exp": 1678956600  // 1 hour expiry
}

Signature
HMACSHA256(base64(header) + "." + base64(payload), secret_key)
```

### 2.2 Token Endpoints

#### POST /api/v1/auth/login
**Purpose:** Generate JWT token  
**Auth:** None (public)  
**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password123"
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "user_12345",
      "email": "user@example.com",
      "name": "John Doe",
      "roles": ["user", "analyst"]
    }
  }
}
```

**Error (401):**
```json
{
  "status": "error",
  "code": 401,
  "message": "Invalid credentials"
}
```

#### POST /api/v1/auth/refresh
**Purpose:** Refresh expired JWT  
**Auth:** Bearer Token (not yet expired)  
**Request:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  }
}
```

#### POST /api/v1/auth/logout
**Purpose:** Invalidate JWT token  
**Auth:** Bearer Token  
**Request:** Empty body  
**Response (200):**
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

---

## 3. User Management API

### 3.1 User Endpoints

#### POST /api/v1/users/register
**Purpose:** Create new user account  
**Auth:** None (public)  
**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure_password123",
  "name": "Jane Smith",
  "company": "Acme Corp"
}
```

**Response (201):**
```json
{
  "status": "success",
  "code": 201,
  "data": {
    "id": "user_67890",
    "email": "newuser@example.com",
    "name": "Jane Smith",
    "roles": ["user"],
    "created_at": "2026-03-15T10:30:00Z"
  }
}
```

#### GET /api/v1/users/profile
**Purpose:** Get current user profile  
**Auth:** Bearer Token (required)  
**Request:** No body  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "user_12345",
    "email": "user@example.com",
    "name": "John Doe",
    "company": "Tech Corp",
    "roles": ["user", "analyst"],
    "created_at": "2026-01-15T08:00:00Z",
    "last_login": "2026-03-15T09:45:00Z"
  }
}
```

#### PUT /api/v1/users/{user_id}
**Purpose:** Update user profile  
**Auth:** Bearer Token (self or admin)  
**Request:**
```json
{
  "name": "John Smith",
  "company": "New Company"
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "user_12345",
    "email": "user@example.com",
    "name": "John Smith",
    "company": "New Company"
  }
}
```

#### DELETE /api/v1/users/{user_id}
**Purpose:** Delete user account  
**Auth:** Bearer Token (self or admin)  
**Request:** No body  
**Response (204):** No content

---

## 4. Document/Knowledge Base API

### 4.1 Document Endpoints

#### POST /api/v1/documents/upload
**Purpose:** Upload document for processing  
**Auth:** Bearer Token  
**Content-Type:** `multipart/form-data`  
**Request:**
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: [binary PDF/DOCX/XLSX]
category: "knowledge_base|training|reference"
title: "Annual Report 2026"
```

**Response (202 - Accepted):**
```json
{
  "status": "success",
  "code": 202,
  "message": "Document queued for processing",
  "data": {
    "document_id": "doc_abc123",
    "status": "processing",
    "file_name": "Annual_Report_2026.pdf",
    "size_bytes": 2048000,
    "created_at": "2026-03-15T10:30:00Z"
  }
}
```

#### GET /api/v1/documents/{document_id}
**Purpose:** Get document details  
**Auth:** Bearer Token  
**Request:** No body  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "doc_abc123",
    "title": "Annual Report 2026",
    "file_name": "Annual_Report_2026.pdf",
    "size_bytes": 2048000,
    "status": "processed",
    "category": "knowledge_base",
    "pages": 85,
    "chunks_created": 120,
    "embedding_status": "completed",
    "uploaded_by": "user_12345",
    "created_at": "2026-03-15T10:30:00Z",
    "processed_at": "2026-03-15T11:15:00Z"
  }
}
```

#### GET /api/v1/documents
**Purpose:** List all documents  
**Auth:** Bearer Token  
**Query Params:**
- `category`: Filter by category
- `status`: Filter by status (processing|processed|failed)
- `page`: Pagination (default 1)
- `limit`: Items per page (default 20)

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "id": "doc_abc123",
        "title": "Annual Report 2026",
        "status": "processed",
        "created_at": "2026-03-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 45,
      "pages": 3
    }
  }
}
```

#### DELETE /api/v1/documents/{document_id}
**Purpose:** Delete document and embeddings  
**Auth:** Bearer Token (owner or admin)  
**Response (204):** No content

---

## 5. Query/Search API

### 5.1 Query Endpoints

#### POST /api/v1/queries/search
**Purpose:** Search knowledge base (vector + semantic)  
**Auth:** Bearer Token  
**Request:**
```json
{
  "query": "What is the revenue forecast for Q3 2026?",
  "top_k": 5,
  "filters": {
    "category": "knowledge_base",
    "document_id": "doc_abc123"
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "query": "What is the revenue forecast for Q3 2026?",
    "results": [
      {
        "rank": 1,
        "document_id": "doc_abc123",
        "document_title": "Annual Report 2026",
        "chunk_id": "chunk_001",
        "content": "Q3 2026 revenue is projected to reach $50M based on current trajectory...",
        "similarity_score": 0.92,
        "page_number": 42
      },
      {
        "rank": 2,
        "document_id": "doc_xyz789",
        "document_title": "Q2 Financial Review",
        "chunk_id": "chunk_045",
        "content": "Based on Q2 performance, we expect Q3 growth of 15%...",
        "similarity_score": 0.87,
        "page_number": 18
      }
    ],
    "search_time_ms": 145
  }
}
```

#### POST /api/v1/queries/ai-answer
**Purpose:** Get AI-powered answer with citations  
**Auth:** Bearer Token  
**Request:**
```json
{
  "query": "What is the revenue forecast for Q3 2026?",
  "context": "Previous context information",
  "model": "gpt-4-turbo",
  "temperature": 0.7
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "query": "What is the revenue forecast for Q3 2026?",
    "answer": "According to the Annual Report 2026 and Q2 Financial Review, revenue for Q3 2026 is projected to reach $50M with an anticipated growth of 15% compared to Q2...",
    "citations": [
      {
        "source": "Annual Report 2026",
        "page": 42,
        "quote": "Q3 2026 revenue is projected to reach $50M"
      },
      {
        "source": "Q2 Financial Review",
        "page": 18,
        "quote": "we expect Q3 growth of 15%"
      }
    ],
    "confidence_score": 0.94,
    "model_used": "gpt-4-turbo",
    "tokens_used": {
      "input": 156,
      "output": 98
    }
  }
}
```

#### POST /api/v1/queries/conversation
**Purpose:** Multi-turn conversation with context  
**Auth:** Bearer Token  
**Request:**
```json
{
  "conversation_id": "conv_abc123",
  "messages": [
    {
      "role": "user",
      "content": "What is the revenue forecast?"
    }
  ],
  "model": "gpt-4-turbo",
  "max_tokens": 1000
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "conversation_id": "conv_abc123",
    "message": {
      "role": "assistant",
      "content": "Based on the Annual Report 2026...",
      "citations": [ /* ... */ ]
    },
    "conversation_history": [ /* ... */ ],
    "tokens_used": {
      "input": 156,
      "output": 98
    }
  }
}
```

---

## 6. Task/Workflow API

### 6.1 Task Endpoints

#### POST /api/v1/tasks
**Purpose:** Create new task/workflow  
**Auth:** Bearer Token  
**Request:**
```json
{
  "title": "Analyze Q2 Financial Data",
  "description": "Generate insights from Q2 reports",
  "workflow_type": "multi_step_analysis",
  "assigned_to": "agent_001",
  "priority": "high",
  "due_date": "2026-03-30T18:00:00Z"
}
```

**Response (201):**
```json
{
  "status": "success",
  "code": 201,
  "data": {
    "id": "task_xyz789",
    "title": "Analyze Q2 Financial Data",
    "status": "created",
    "assigned_to": "agent_001",
    "created_at": "2026-03-15T10:30:00Z"
  }
}
```

#### GET /api/v1/tasks/{task_id}
**Purpose:** Get task status and results  
**Auth:** Bearer Token  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "task_xyz789",
    "title": "Analyze Q2 Financial Data",
    "status": "in_progress",
    "progress": 65,
    "workflow_steps": [
      {
        "step_id": "step_001",
        "name": "Data Extraction",
        "status": "completed",
        "duration_ms": 2500
      },
      {
        "step_id": "step_002",
        "name": "Analysis",
        "status": "in_progress",
        "duration_ms": 5000
      }
    ],
    "results": null,
    "created_at": "2026-03-15T10:30:00Z",
    "started_at": "2026-03-15T10:32:00Z"
  }
}
```

#### GET /api/v1/tasks
**Purpose:** List tasks with filters  
**Auth:** Bearer Token  
**Query Params:**
- `status`: Filter by status
- `assigned_to`: Filter by assignee
- `page`: Pagination

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "tasks": [
      {
        "id": "task_xyz789",
        "title": "Analyze Q2 Financial Data",
        "status": "in_progress",
        "progress": 65
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 12
    }
  }
}
```

---

## 7. Agent Management API

### 7.1 Agent Endpoints

#### GET /api/v1/agents
**Purpose:** List all available agents  
**Auth:** Bearer Token  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "agents": [
      {
        "id": "agent_001",
        "name": "Financial Analyst Agent",
        "description": "Analyzes financial data and generates reports",
        "capabilities": ["data_analysis", "report_generation", "forecasting"],
        "status": "active",
        "version": "1.0.0"
      },
      {
        "id": "agent_002",
        "name": "Customer Service Agent",
        "description": "Handles customer queries and support",
        "capabilities": ["qa", "ticket_creation", "escalation"],
        "status": "active",
        "version": "1.2.0"
      }
    ]
  }
}
```

#### GET /api/v1/agents/{agent_id}
**Purpose:** Get agent details and metrics  
**Auth:** Bearer Token  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "agent_001",
    "name": "Financial Analyst Agent",
    "description": "Analyzes financial data and generates reports",
    "capabilities": ["data_analysis", "report_generation", "forecasting"],
    "status": "active",
    "version": "1.0.0",
    "metrics": {
      "tasks_completed": 245,
      "success_rate": 0.96,
      "avg_response_time_ms": 2350,
      "last_active": "2026-03-15T10:15:00Z"
    },
    "skills": [
      {
        "name": "extract_data",
        "description": "Extract data from documents"
      },
      {
        "name": "generate_report",
        "description": "Generate analysis report"
      }
    ]
  }
}
```

---

## 8. Analytics API

### 8.1 Analytics Endpoints

#### GET /api/v1/analytics/dashboard
**Purpose:** Get dashboard metrics  
**Auth:** Bearer Token  
**Query Params:**
- `period`: "day|week|month|year"
- `start_date`: ISO date
- `end_date`: ISO date

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "period": "month",
    "metrics": {
      "total_queries": 1245,
      "successful_queries": 1203,
      "success_rate": 0.9662,
      "avg_response_time_ms": 856,
      "documents_processed": 45,
      "active_users": 23,
      "agents_utilized": 5
    },
    "trends": {
      "queries_by_day": [ /* daily data */ ],
      "response_time_trend": [ /* trend data */ ]
    }
  }
}
```

#### GET /api/v1/analytics/usage/{user_id}
**Purpose:** Get user-specific usage analytics  
**Auth:** Bearer Token  
**Response (200):**
```json
{
  "status": "success",
  "data": {
    "user_id": "user_12345",
    "queries_made": 156,
    "documents_uploaded": 12,
    "avg_query_length": 45,
    "favorite_agents": ["agent_001", "agent_002"],
    "top_queries": [
      {
        "query": "revenue forecast",
        "count": 12
      }
    ]
  }
}
```

---

## 9. Error Handling

### 9.1 HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 202 | Accepted | Request queued (async) |
| 204 | No Content | Successful deletion |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Maintenance/overload |

### 9.2 Error Response Format

```json
{
  "status": "error",
  "code": 400,
  "message": "Invalid request parameters",
  "errors": [
    {
      "field": "query",
      "message": "Query cannot be empty"
    },
    {
      "field": "top_k",
      "message": "top_k must be between 1 and 100"
    }
  ],
  "timestamp": "2026-03-15T10:30:00Z",
  "request_id": "req_abc123xyz"
}
```

---

## 10. Rate Limiting

### 10.1 Rate Limit Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1678956600
```

### 10.2 Rate Limits by Endpoint

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Search | 100 req/min | Per minute |
| AI Answer | 50 req/min | Per minute |
| Document Upload | 20 req/hour | Per hour |
| Conversation | 200 req/hour | Per hour |

---

## 11. Webhooks

### 11.1 Webhook Events

The system can emit real-time events via webhooks:

| Event | Trigger | Payload |
|-------|---------|---------|
| `document.processed` | Document processing complete | Document details |
| `task.completed` | Task finished | Task results |
| `agent.error` | Agent encountered error | Error details |

### 11.2 Webhook Configuration

```bash
POST /api/v1/webhooks
{
  "event_type": "document.processed",
  "url": "https://yourapp.com/webhook",
  "active": true
}
```

---

## 12. API Client Examples

### 12.1 Python (Backend)

```python
import httpx
import json

# Initialize client
client = httpx.AsyncClient(
    base_url="http://localhost/api/v1",
    headers={"Authorization": f"Bearer {token}"}
)

# Search documents
response = await client.post(
    "/queries/search",
    json={
        "query": "revenue forecast",
        "top_k": 5
    }
)
results = response.json()["data"]["results"]
```

### 12.2 JavaScript (Frontend)

```javascript
const api = axios.create({
  baseURL: "http://localhost/api/v1",
  headers: {
    Authorization: `Bearer ${token}`
  }
});

// Search documents
const response = await api.post("/queries/search", {
  query: "revenue forecast",
  top_k: 5
});
const results = response.data.data.results;
```

---

## 13. Documentation & Tools

### 13.1 Swagger/OpenAPI
- **Endpoint:** `http://localhost/api/docs`
- **ReDoc:** `http://localhost/api/redoc`

### 13.2 Postman Collection
- Import: `/docs/postman_collection.json`

---

## END OF API SPECIFICATION DOCUMENT
