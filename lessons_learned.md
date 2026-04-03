# Lessons Learned — AI BA Agent

---

## 2026-03-21 | Tailwind CSS + Bootstrap Conflict: Navbar Disappeared After Adding `./src/**` to Tailwind Content Paths

### Problem
Adding `'./src/**/*.{js,ts,jsx,tsx}'` to `tailwind.config.ts` content paths (to fix `NotificationBell` SVG sizing) caused the entire navbar to go blank after rebuild.

### Root Cause
Tailwind scanned `Layout.tsx` and found the Bootstrap class name `collapse` (from `className="collapse navbar-collapse"`). It then generated the CSS utility class:
```css
.collapse { visibility: collapse; }
```
This silently **overrode** Bootstrap's own rule:
```css
.collapse { display: none; }
```
Bootstrap's navbar expand logic relies on toggling `.collapse` to show/hide the nav items. With visibility instead of display, all nav items became invisible (still in the DOM, just visually hidden — making the navbar appear completely empty).

Additionally, Tailwind's `preflight` (base reset) was overriding Bootstrap's normalize.css, causing further style conflicts.

### Fix
Added two `corePlugins` disables to `tailwind.config.ts`:
```typescript
corePlugins: {
  preflight: false,   // Don't override Bootstrap's base reset/normalize
  visibility: false,  // Prevent .collapse { visibility:collapse } overriding Bootstrap's .collapse
},
```

### Key Rule
**When mixing Tailwind CSS with Bootstrap in the same project:**
- Always set `preflight: false` to prevent Tailwind's base reset from overriding Bootstrap's normalize
- Always set `visibility: false` to prevent `.collapse` utility class from conflicting with Bootstrap's `.collapse { display: none }` pattern
- Be aware of any other Tailwind utility names that coincide with Bootstrap class names (`container`, `row`, `shadow`, `text-*`, etc.)

### Files Changed
- `frontend/tailwind.config.ts` — added `corePlugins: { preflight: false, visibility: false }`

---

## 2026-03-24 | Knowledge Base Search: Why It Took Many Steps to Fix

### Summary
Getting the knowledge base RAG search working end-to-end required fixing **7 separate bugs across 4 layers** (backend container, Python middleware, React state, and Next.js build config). Each bug was independently invisible until the previous one was fixed, creating a "bug chain" that made the feature appear completely broken from the outside.

---

### Root Cause Chain

**1. Docker image was never rebuilt after new routes were added**
- `knowledge_base.py` grew from 91 lines (only `/rag` routes) to 595 lines (added `/search` routes) during development.
- The backend Docker container was **not rebuilt** after the new code was added.
- The running container still had the 91-line file, so `POST /api/knowledge-base/search` returned 404.
- This was invisible because `docker compose ps` showed the container as "healthy" — health checks only test `/health`, not every route.
- **Root cause:** No "route smoke test" step in the development workflow; `docker compose up` does not rebuild unless explicitly told to.

**2. JWT `projects` claim was a list of dicts, but the security check expected flat strings**
- `auth_service` encodes `projects` as `[{"project_id": "uuid", "role": "ba"}]` in the JWT.
- `rbac.py`'s `TokenUser` stored it raw: `self.projects = payload.get("projects", [])`.
- `knowledge_base.py`'s security check did `if str(project_id) not in user_projects` — expects `["uuid"]`.
- Result: every search returned 403 Forbidden even for valid project members.
- **Root cause:** The JWT schema (dict list) and the consumer code (string list) were written independently with no shared type contract. No integration test caught the mismatch.

**3. `removeConsole` in Next.js build stripped all `console.*` calls in production**
- `next.config.js` had `compiler: { removeConsole: true }`.
- This silently removed debug logs from the search button handler, making it impossible to tell whether the frontend was even sending the request.
- **Root cause:** A production optimization was applied globally without realising it would obscure all debugging during development and testing.

**4. React checkbox double-toggle due to event bubbling**
- Document checkboxes were inside `<label>` elements. Clicking the `<input>` fired `onClick` on the input, which bubbled to the `<label>`, which re-fired the input's change event — resulting in a net zero toggle (add then immediately remove).
- Appeared as "checkboxes do nothing."
- **Root cause:** Standard HTML behaviour (`<label>` re-dispatches clicks to its associated input) was not accounted for in the event handler design.

**5. `selectedDocIds` used a `Set`, causing stale state in React**
- `Set` objects in React state do not satisfy referential equality checks. `useState` with a `Set` causes the component to see the same object reference even after mutation — closures capture the old reference.
- Selected document IDs appeared empty on every render despite being added.
- **Root cause:** React state must use immutable values. `Set` is mutable and its reference identity doesn't change on `.add()` / `.delete()`, so React's diffing skips re-renders.

**6. `handleSearch` had a stale closure over `selectedDocIds`**
- Even after switching from `Set` to `string[]`, `handleSearch` was defined as a plain `async` function inside the component, capturing `selectedDocIds` at creation time.
- When called, it always saw the empty initial value.
- **Root cause:** The function was not wrapped in `useCallback` with proper dependencies, and no `useRef` was used to provide a stable, always-current reference to the array.

**7. Agent pipeline showed letters (S/R/A/V) instead of step numbers (1/2/3/4)**
- The pipeline used `agent.icon` (single character shorthand) rendered inside the node circle.
- After switching to `String(index + 1)`, numbers 1–4 displayed correctly.
- **Root cause:** The initial icon design was a placeholder that was never updated when the UI shifted to a step-number convention.

---

### Why It Escalated to So Many Steps

| Layer | Category | Why Hard to See |
|-------|----------|-----------------|
| Docker container | Infrastructure drift | Container "healthy" but code was stale — no route-level health check |
| JWT / RBAC middleware | Contract mismatch | Two services wrote to the same field differently; no shared schema |
| Next.js build | Build config side-effect | `removeConsole` silently hid all frontend debug output |
| React event | HTML/browser behaviour | Double-fire is expected DOM behaviour, not a React error |
| React state (Set) | Immutability violation | No runtime error; silent stale reads |
| React closure | Async capture | No error; function always ran but with wrong data |
| UI copy | Design/copy drift | Cosmetic but added confusion during testing |

Each fix only revealed the next bug. The feature looked "totally broken" from the outside when in reality it was six separate smaller problems stacked on each other.

---

### Key Rules Going Forward

- **After adding new API routes, always verify them with a route listing command before testing the UI:**
  ```powershell
  docker exec <container> python3 -c "from app.main import app; [print(r.path) for r in app.routes]"
  ```
- **Define a shared JWT claims schema** (TypeScript interface or Pydantic model) that both `auth_service` and `backend` import — never let the shape drift silently.
- **Never use `removeConsole: true` globally** in Next.js during active development. Scope it to production CI/CD only, or use `removeConsole: { exclude: ['error'] }`.
- **Never store mutable objects (`Set`, `Map`, `object`) directly in React state.** Always use immutable primitives or spread-copy arrays/objects.
- **Use `useRef` + `useCallback` for any async handler that reads state** that changes after the handler is first created.
- **Hot-patch running containers** (`docker cp` + `docker restart` + `docker commit`) when a full rebuild is too slow, but always rebuild the image properly before the next deployment to avoid the same container-drift problem.
- **Write a smoke test script** that hits every registered API route after any backend change, not just the `/health` endpoint.

---
