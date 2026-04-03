# Dependency Versions & Management
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1

---

## 1. Backend Services (Python 3.11)

### 1.1 Core Framework

| Package | Version | Reason |
|---------|---------|--------|
| **fastapi** | 0.104.1 | Latest stable; full async support; best for microservices |
| **uvicorn** | 0.24.0 | ASGI server; minimal, fast, production-ready |
| **python-jose** | 3.3.0 | JWT token generation and validation |
| **passlib** | 1.7.4 | Password hashing (bcrypt integration) |
| **bcrypt** | 4.1.1 | Secure password hashing (cost: 12 rounds) |

### 1.2 Database & ORM

| Package | Version | Reason |
|---------|---------|--------|
| **sqlalchemy** | 2.0.23 | Latest 2.x; async support; ORM for PostgreSQL |
| **psycopg2-binary** | 2.9.9 | PostgreSQL adapter; precompiled for portability |
| **alembic** | 1.12.0 | (Optional) Schema migrations if needed |

### 1.3 Data Validation & Serialization

| Package | Version | Reason |
|---------|---------|--------|
| **pydantic** | 2.5.0 | Latest 2.x; fast JSON validation; type hints |
| **pydantic-settings** | 2.1.0 | Environment variable loading |

### 1.4 External APIs & LLM

| Package | Version | Reason |
|---------|---------|--------|
| **httpx** | 0.25.2 | Async HTTP client; preferred over requests |
| **openrouter** | 0.0.0 | OpenRouter API client (check availability) |
| **tenacity** | 8.2.3 | Retry logic with exponential backoff |
| **requests** | 2.31.0 | (Fallback) Synchronous HTTP client |

### 1.5 RAG Service Specific

| Package | Version | Reason |
|---------|---------|--------|
| **crewai** | 0.15.0 | Multi-agent orchestration framework |
| **sentence-transformers** | 2.2.2 | Text embeddings (all-MiniLM-L6-v2) |
| **qdrant-client** | 1.7.0 | Vector DB Python client |

### 1.6 Document Parsing

| Package | Version | Reason |
|---------|---------|--------|
| **PyPDF2** | 3.0.1 | PDF text extraction |
| **python-docx** | 0.8.11 | DOCX parsing |
| **openpyxl** | 3.1.2 | Excel file parsing |

### 1.7 Utilities

| Package | Version | Reason |
|---------|---------|--------|
| **python-multipart** | 0.0.6 | File upload support in FastAPI |

---

## 2. Frontend (Node.js 20 + React 18)

### 2.1 Core Framework

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **react** | 18.2.0 | Latest stable; excellent ecosystem; strict mode enforced | Pinned |
| **react-dom** | 18.2.0 | React DOM renderer | Pinned |
| **next** | 14.0.4 | Latest; app router; server components; built-in optimizations | Pinned |
| **typescript** | 5.3.3 | Strict type checking; latest stable | Pinned |

### 2.2 UI & Styling

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **bootstrap** | 5.3.2 | CSS framework; responsive design | Pinned |
| **tailwindcss** | 3.4.1 | Utility-first CSS; className-based | Pinned |
| **postcss** | 8.4.32 | CSS processing (for Tailwind) | Pinned |
| **autoprefixer** | 10.4.16 | Vendor prefix generation | Pinned |
| **classnames** | 2.3.2 | Conditional CSS class helper | Pinned |

### 2.3 State Management

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **zustand** | 4.4.1 | Lightweight store; React hooks; minimal boilerplate | Pinned |

### 2.4 Forms & Validation

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **react-hook-form** | 7.48.0 | Minimal re-renders; excellent performance | Pinned |
| **zod** | 3.22.4 | TypeScript-first schema validation | Pinned |

### 2.5 HTTP & API

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **axios** | 1.6.2 | Promise-based HTTP client; interceptors for auth | Pinned |

### 2.6 Type Definitions

| Package | Version | Reason | Lock Strategy |
|---------|---------|--------|---|
| **@types/react** |18.2.45 | React type definitions | Pinned |
| **@types/react-dom** | 18.2.18 | React DOM type definitions | Pinned |
| **@types/node** | 20.10.6 | Node.js type definitions | Pinned |

### 2.7 Development Dependencies

| Package | Version | Reason |
|---------|---------|--------|
| **eslint** | 8.55.0 | Code linting |
| **eslint-config-next** | 14.0.4 | Next.js ESLint config |
| **@typescript-eslint/eslint-plugin** | 6.14.0 | TypeScript ESLint |
| **@typescript-eslint/parser** | 6.14.0 | TypeScript parser |
| **prettier** | 3.1.0 | Code formatter |

---

## 3. Database Versions

| Service | Version | Reason |
|---------|---------|--------|
| **PostgreSQL** | 15 (Alpine) | Latest stable; excellent JSONB support; performance |
| **Qdrant** | 1.7 | Vector database; production-ready; good performance |
| **Redis** | 7 (Alpine) | In-memory cache; session storage; rate limiting |

---

## 4. System Software

| Service | Version | Reason |
|---------|---------|--------|
| **Node.js** | 20 (Alpine) | LTS; excellent npm ecosystem |
| **Python** | 3.11 (slim) | Latest stable 3.11; security updates; performance |
| **Nginx** | 1.25 (Alpine) | Latest stable; reverse proxy; TLS termination |
| **Docker** | 24.x+ | Latest; better compose file support |

---

## 5. Version Pinning Strategy

### 5.1 Production (Strict Pinning)

**Format:** Exact version numbers  
**Example:**  
```txt
fastapi==0.104.1
pydantic==2.5.0
```

**Reasoning:**
- Prevents surprise breaking changes in production
- Ensures reproducible deployments across environments
- Matches what was tested in development

### 5.2 Frontend (Lock Files)

**Strategy:** Use `package.json` without `^` or `~` operators  
**Example:**
```json
{
  "react": "18.2.0",
  "next": "14.0.4"
}
```

**Lock File:** `package-lock.json` (generated by `npm install`)  
**Commit:** Always commit `package-lock.json` for reproducibility

### 5.3 Backend (Requirements Management)

**Two-Tier Approach:**

1. **requirements.txt** - Direct dependencies (locked)
   ```
   fastapi==0.104.1
   sqlalchemy==2.0.23
   ```

2. **requirements-lock.txt** - All dependencies with transitive deps (optional)
   ```bash
   pip freeze > requirements-lock.txt
   ```

---

## 6. Dependency Conflict Resolution

### 6.1 Known Issues & Workarounds

| Issue | Packages | Solution |
|-------|----------|----------|
| SQLAlchemy 2.0 async | sqlalchemy + psycopg2 | Use `sqlalchemy>=2.0` with `psycopg2>=2.9` |
| Pydantic v1 vs v2 | pydantic + fastapi | Use Pydantic 2.x with FastAPI 0.104+ |
| Node version mismatch | node + npm | Lock Node.js to 20.x in `.nvmrc` |

### 6.2 Before Deploying

Run these checks:

**Backend:**
```bash
pip check  # Detect dependency conflicts
python -m pip list  # Verify all packages installed
```

**Frontend:**
```bash
npm audit  # Check for security vulnerabilities
npm list  # Verify all packages installed
```

---

## 7. Upgrade Strategy

### 7.1 Security Patches (Fast Track)

When: Critical security vulnerability discovered  
Process:
1. Update only the vulnerable package (e.g., `django==4.2.8`)
2. Run full test suite
3. Deploy immediately to production
4. Document the Security Advisory

### 7.2 Minor Updates (Quarterly)

When: New features, bug fixes available  
Process:
1. Update package to next minor version (e.g., `4.1.x` → `4.2.x`)
2. Run ALL tests including integration tests
3. Verify backward compatibility
4. Stage deployment to test environment
5. Deploy after 1 week validation

### 7.3 Major Updates (Annual)

When: Major version bump (e.g., React 17 → 18)  
Process:
1. Schedule major testing effort
2. Create isolated feature branch
3. Update ALL related packages together
4. Full regression testing (manual + automated)
5. UAT with stakeholders
6. Plan deployment during low-traffic period

---

## 8. Monitoring & Health Checks

### 8.1 Version Compliance

Add version check endpoint:

```python
# Backend health check
@app.get("/version")
def get_versions():
    return {
        "python_version": "3.11.x",
        "fastapi_version": "0.104.1",
        "sqlalchemy_version": "2.0.23"
    }
```

```javascript
// Frontend version check
export function getVersions() {
  return {
    react_version: "18.2.0",
    next_version: "14.0.4",
    typescript_version: "5.3.3"
  }
}
```

### 8.2 Outdated Dependency Detection

**Command (Quarterly Check):**
```bash
# Backend
pip list --outdated

# Frontend
npm outdated
```

### 8.3 Security Scanning

**Backend:**
```bash
pip install safety
safety check
```

**Frontend:**
```bash
npm audit
```

---

## 9. Version Summary Table

### Python Backend Packages

| Component | Total Packages | Locked Versions | Strategy |
|-----------|---|---|---|
| Core Framework | 8 | All | Pinned exact |
| Database | 3 | All | Pinned exact |
| External APIs | 4 | All | Pinned exact |
| **TOTAL** | **15+** | **All** | **Locked** |

### Frontend Packages

| Component | Total Packages | Locked Versions | Strategy |
|-----------|---|---|---|
| React/Next | 4 | All | package.json pinned |
| UI/Styling | 5 | All | package.json pinned |
| State Management | 1 | All | package.json pinned |
| Forms | 2 | All | package.json pinned |
| HTTP | 1 | All | package.json pinned |
| **TOTAL** | **13** | **All** | **package-lock.json** |

### Infrastructure (Docker Images)

| Service | Base Image | Version | Strategy |
|---------|-----------|---------|----------|
| PostgreSQL | postgres | 15-Alpine | Pinned tag |
| Qdrant | qdrant/qdrant | 1.7 | Pinned tag |
| Redis | redis | 7-Alpine | Pinned tag |
| Node | node | 20-Alpine | Pinned tag |
| Python | python | 3.11-slim | Pinned tag |
| Nginx | nginx | 1.25-Alpine | Pinned tag |

---

## 10. Dependency Installation

### 10.1 Backend Setup

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip check  # Verify no conflicts
```

### 10.2 Frontend Setup

```bash
cd frontend
node -v  # Verify 20.x
npm install --frozen-lockfile  # Use exact versions
npm run type-check  # TypeScript validation
```

### 10.3 RAG Service Setup

```bash
cd rag_service
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip check
```

---

## 11. Maintenance Calendar

| Frequency | Task | Owner |
|-----------|------|-------|
| **Weekly** | Check CI/CD test results | DevOps |
| **Monthly** | Security scanning (safety, npm audit) | Security Lead |
| **Quarterly** | Review outdated packages | Tech Lead |
| **Annually** | Major version upgrade planning | Engineering Team |

---

## END OF DEPENDENCY VERSIONS DOCUMENT
