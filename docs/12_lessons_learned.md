# Lessons Learned -- AI BA Agent

## Issue 1: Nginx Cookie Stripping (2026-03-18)

### Problem
Nginx routed `/api/auth/*` directly to `auth_service`,
bypassing the Next.js cookie middleware.
The `Set-Cookie` header was stripped -- browser never received the session cookie.

### Symptom
- Login returned `200 OK` (appeared to succeed)
- Browser had no `access_token` cookie after login
- Every subsequent request was unauthenticated (401)
- Frontend threw `Session not established` error

### Root Cause
`gateway/nginx.conf` had:
```nginx
location /api/auth/ {
    rewrite ^/api/auth/(.*)$ /auth/$1 break;
    proxy_pass http://auth_service;   # WRONG: bypasses Next.js
}

location /api/ {
    proxy_pass http://backend_api;    # WRONG: no token injection
}
```
Instead of:
```nginx
location /api/auth/ {
    proxy_pass http://frontend;       # CORRECT: Next.js sets cookie
}

location /api/ {
    proxy_pass http://frontend;       # CORRECT: Next.js injects Bearer token
}
```

### Fix Applied
All `/api/*` routes now proxy to `frontend:3000`.
Next.js API routes (`/pages/api/auth/login.ts` etc.) handle:
- Setting the `HttpOnly; SameSite=Lax` cookie on login
- Reading the cookie and injecting `Authorization: Bearer <token>` on subsequent requests

### Prevention
1. `.copilot-instructions.md` has **Gateway Routing Rules** section
2. `docs/04_architecture_freeze.md` section **3.2a** has Gateway Routing Checklist
3. `gateway/nginx.conf` has routing intent comments in the server block
4. Rule: After ANY `nginx.conf` change, run the cookie flow test:
   - `POST /api/auth/login` -> `Set-Cookie` must be non-empty
   - `GET /api/auth/me` -> must return user info

---

## Issue 2: PostgreSQL Connection Pool Exhaustion (2026-03-18)

### Problem
`/projects` page loaded forever (infinite spinner, no error message).
Backend container entered `unhealthy` state within seconds of the page loading.

### Symptom
- `/projects` page showed infinite spinner
- Nginx logs: `504 Gateway Time-out` on `/api/documents`
- `docker ps` showed `ai_ba_backend (unhealthy)`
- All other API calls also hung while documents page was open

### Root Cause
`frontend/pages/api/documents/index.ts` used an unbounded `Promise.all()`:
```typescript
// WRONG -- fires N simultaneous DB queries (N = number of documents)
const documents = await Promise.all(
    documentItems.map(async (doc) => {
        const versions = await axios.get(`/documents/${doc.id}/versions`);
        return { ...doc, versions: versions.data };
    })
);
```
With 13+ documents, this fired 13+ simultaneous requests to the backend.
Each request opened a PostgreSQL connection.
The pool maximum is 10 connections -- all slots consumed, new queries queued forever.
Backend health check timed out -> container marked unhealthy -> all requests 504.

### Fix Applied
Replaced with a batched loop (max 3 concurrent, 5 s timeout per call):
```typescript
// CORRECT -- max 3 concurrent DB requests
const BATCH_SIZE = 3;
const documents: DocumentWithVersions[] = [];
for (let i = 0; i < documentItems.length; i += BATCH_SIZE) {
    const batch = documentItems.slice(i, i + BATCH_SIZE);
    const results = await Promise.all(
        batch.map(async (doc) => {
            const versions = await axios.get(
                `${BACKEND_SERVICE_URL}/documents/${doc.id}/versions`,
                { timeout: 5000 }
            );
            return { ...doc, versions: versions.data };
        })
    );
    documents.push(...results);

## Issue 8: Google Drive File Allocation Restructure (2026-03-22)

### Change Made
Removed project-based flat folder structure.
Implemented status-based folder allocation.

### Old Structure
```
AI-BA-Agent Documents/
  └── [Project Name]/
        └── file
```

### New Structure
```
AI-BA-Agent Documents/
  ├── Pending documents/
  │     └── [Project Name]/
  └── Approved documents/
        └── [Project Name]/
```

### Rules
1. Upload → Pending documents/[Project]/
2. Approved → Move to Approved documents/[Project]/
3. All other states stay in Pending
4. Move wrapped in try/except for safety

### Key Files Changed
- `google_drive.py`: `find_or_create_folder()`, `get_root_folders()`, `move_file_to_approved()`
- `workflow.py`: trigger move on final approval
- `documents.py`: pass `project_name` to upload
}
```

### Prevention
1. `.copilot-instructions.md` has **Async & Database Rules** section
2. `docs/04_architecture_freeze.md` has **Performance & Stability Checklist**
3. Rule: NEVER use `Promise.all(items.map(...))` for unbounded backend/DB requests
4. Rule: Always set `timeout` on all `axios.get()` / `fetch()` calls in API routes
5. Rule: Test with 10+ documents before every deployment

---

## Summary Table

| # | Date       | Component                            | Symptom                     | Root Cause                          | Fix                                |
|---|------------|--------------------------------------|-----------------------------|-------------------------------------|------------------------------------|
| 1 | 2026-03-18 | `gateway/nginx.conf`                 | Session not established     | nginx bypassed Next.js cookie layer | All `/api/*` -> `frontend:3000`    |
| 2 | 2026-03-18 | `pages/api/documents/index.ts`       | Infinite spinner on /projects | Unbounded Promise.all exhausted PG pool | Batch size 3, timeout 5s |