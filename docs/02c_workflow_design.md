# Workflow Design: System Orchestration & Sub-Workflows
**Version:** 1.0  
**Date:** 2026-03-14  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Status:** MVP Phase 1 Workflow Architecture

---

## Document Overview

This document details the complete workflow orchestration strategy for the AI BA Agent system, including:
- **Main Workflow:** End-to-end process orchestrating all 6 functional modules
- **Sub-Workflows:** 5 parallel workflows (A, B, C, D, E) with detailed steps
- **Event Triggers:** 5 event types that initiate workflows
- **Orchestration Engine:** CrewAI + PostgreSQL state management
- **Failure Handling:** Error types, escalation paths, guardrails
- **Retry Strategy:** Transient vs permanent errors, exponential backoff, circuit breaker
- **Human-in-the-Loop (HITL):** 7 approval gates and escalation conditions

---

## 1. Main Workflow Architecture

### 1.1 System-Level Workflow Overview

The main workflow orchestrates all 6 functional modules into a cohesive end-to-end process:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MAIN WORKFLOW: Document Ingestion                   │
│                   → Processing → Generation → Approval                   │
└─────────────────────────────────────────────────────────────────────────┘

               ┌──────────────────────────────────┐
               │  Module 1: Document Ingestion    │
               │  (Accept Input)                  │
               └──────────────┬───────────────────┘
                              │
                     ┌────────▼────────┐
                     │  Routing Agent  │ ◄─── Classify input type
                     └────────┬────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼───┐         ┌─────┬▼──┐          ┌──────▼────┐
   │ AUDIO  │         │  EMAIL   │          │ DOCUMENT  │
   │ FILE   │         │ THREAD   │          │ (PDF/DOC)│
   └────┬───┘         └─────┬───┘          └──────┬────┘
        │                   │                     │
        │     (3 parallel streams)               │
        │                                        │
   ┌────▼────────────────────────────────────────▼───────┐
   │  Module 2: STT / Content Extraction                 │
   │  - Parse input                                      │
   │  - Extract entities (decisions, action items, reqs) │
   │  - Apply speaker diarization (if audio)             │
   └────┬──────────────────────────────────────────────┬─┘
        │                                               │
        │                                               │
   ┌────▼────────────────────────────────────────────┬─▼──────┐
   │  Module 3: RAG Knowledge Integration            │        │
   │  - Search vector DB for similar docs            │        │
   │  - Cross-reference extracted content            │        │
   │  - Generate source citations                    │        │
   │  - Confidence scoring                           │        │
   └────┬──────────────────────────────────────────┬─┘│       │
        │                                           │  │       │
   ┌────▼──────────────────────────────────────────▼──▼───┐   │
   │  Module 4: Document Generation (Summarization)      │   │
   │  - Meeting minutes                                  │   │
   │  - BRD/URS drafts                                   │   │
   │  - Weekly digests                                   │   │
   │  - Format & style application                       │   │
   └────┬───────────────────────────────────────────────┬┘   │
        │                                               │     │
   ┌────▼──────────────────────────────────────────────▼──┐  │
   │  Module 5: Validation & Risk Detection             │  │
   │  - Format compliance check                         │  │
   │  - Risk flagging (legal, financial, security)      │  │
   │  - Confidence aggregation                          │  │
   │  - Business rule validation                        │  │
   │  - Redundancy check                                │  │
   └────┬───────────────────────────────────────────────┬──┘
        │                                               │
   ┌────▼──────────────────────────────────────────────▼──┐
   │  Module 6: Human-in-the-Loop Approval              │
   │  - Route to appropriate approver/specialist        │
   │  - Approval workflow tracking                      │
   │  - Version management & publishing                 │
   │  - Audit logging                                   │
   └────┬───────────────────────────────────────────────┬──┘
        │                                               │
        └───────────────────────┬──────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │   RAG Indexing        │
                    │   (Store in Qdrant)   │
                    └───────────┬────────────┘
                                │
                        ┌───────▼──────────┐
                        │ Notification      │
                        │ (Telegram/Email)  │
                        └───────────────────┘
```

### 1.2 Module Responsibilities in Main Workflow

| # | Module | Role in Main Workflow | Owner Agent(s) | Output |
|---|--------|----------------------|-----------------|--------|
| **1** | Document Ingestion & STT | Accept input; route to processing | Routing Agent | Classified input, metadata |
| **2** | Content Extraction | Parse & extract structured entities | Data Extraction Agent | Decisions, action items, requirements, risks |
| **3** | RAG Integration | Ground content in knowledge base | RAG Verification Agent | Verified claims, citations, confidence scores |
| **4** | Document Generation | Create business artifacts | Summarization Agent | Formatted documents (minutes, BRDs, digests) |
| **5** | Validation & Risk | Quality gate before approval | Validation Agent | Risk flags, compliance check, final confidence |
| **6** | HITL Approval | Human review & publishing | Memory Agent + n8n workflow | Approved content, version records, audit logs |

### 1.3 Data Flow Across Modules

```
User Input
  │
  ├─ {file_type, metadata, user_id, project_id}
  │
  ▼
Routing Agent
  │
  ├─ Routes to appropriate sub-workflow (A, B, C, D, or E)
  │
  ▼
Data Extraction Agent
  │
  ├─ Outputs: {transcript, entities, decisions, action_items, requirements, risks}
  │
  ▼
RAG Verification Agent
  │
  ├─ Outputs: {verified_claims, citations, confidence_scores, ungrounded_items}
  │
  ▼
Summarization Agent
  │
  ├─ Outputs: {document_md, sections, format_valid, readability_score}
  │
  ▼
Validation Agent
  │
  ├─ Outputs: {compliant, risk_flags, confidence, required_approvers, ready_for_approval}
  │
  ▼
HITL Approval Workflow
  │
  ├─ Outputs: {approval_status, approver_decision, version_id, audit_log}
  │
  ▼
RAG Indexing + Notification
  │
  └─ {embeddings_stored, notification_sent, completion_timestamp}
```

---

## 2. Sub-Workflows (Workflows A, B, C, D, E)

### 2.1 Workflow A: Document Ingestion & BRD Generation (9-Step Pipeline)

**Trigger:** User uploads meeting recording, document, or initiates document ingestion  
**Frequency:** On-demand  
**Expected Duration:** 3-10 minutes per document  
**Entry Point:** User upload via web interface or email integration

#### Step-by-Step Execution

| Step | Agent | Action | Input | Output | SLA | Error Handling |
|------|-------|--------|-------|--------|-----|--------|
| **1** | Routing | Classify file type | File + metadata | {workflow_type, processing_path} | <5s | Default to Data Extraction if uncertain |
| **2** | n8n (STT Webhook) | Trigger async STT | Audio file | {transcript, speakers, confidence, segments} | <5 min/hour | Fallback to Deepgram if ElevenLabs fails; retry 3x exponential backoff |
| **3** | Data Extraction | Extract entities | Transcript + doc type | {decisions, action_items, requirements, risks, marked_questions} | <2 min | Mark uncertain as "NEEDS_CONFIRMATION"; fallback to manual review |
| **4** | RAG Verification | Ground in KB | Extracted entities + project context | {verified_claims, citations, confidence, ungrounded_items} | <1 min | Mark <40% confidence as "NEEDS_CONFIRMATION" |
| **5** | Summarization | Generate document | Verified content + template | {document_md, format_valid, sections_present} | <2 min | Use template-based fallback if LLM fails; escalate if critical |
| **6** | Validation | Quality gate | Generated document + rules | {compliant, risk_flags, confidence, required_approvers} | <1 min | Reject if schema invalid; request reformatting |
| **7** | HITL Approval | Route to approver | Document + risk flags | {approval_request, assigned_approver, deadline} | <24h | Send reminder after 12h; escalate after 48h |
| **8** | Approval Workflow | Store version | Approved content | {version_id, status_published, audit_log} | <5 sec | Log rejection reason; revert to draft if rejected |
| **9** | RAG Indexing | Index document | Approved content | {embeddings_stored, search_enabled, timestamp} | <1 min | Skip if indexing fails; alert admin; fallback to keyword search |

#### Handoff Conditions (Agent to Agent)

```yaml
Step 1 → Step 2:
  CONDITION: file_type in [audio, recording, meeting]
  IF_FALSE: Skip to Step 3 (no STT needed)

Step 2 → Step 3:
  CONDITION: STT confidence >= 60% AND transcript.length > 0
  IF_FALSE: Mark as [NEEDS_CONFIRMATION]; retry once with keyterm prompting
  FALLBACK: User can manually upload transcript

Step 3 → Step 4:
  CONDITION: extraction_complete AND entities_count > 0
  IF_FALSE: Log as empty extraction; notify user

Step 4 → Step 5:
  CONDITION: RAG_verification_complete
  IF_CONFIDENCE < 40%: Mark ungrounded items; continue with flag
  IF_CONFIDENCE < 60%: Generate document but add [NEEDS_VERIFICATION] tags

Step 5 → Step 6:
  CONDITION: document_generation_complete
  ALWAYS: Proceed (summarization never blocks validation)

Step 6 → Step 7:
  CONDITION: validation_complete
  IF_NO_CRITICAL_RISKS: Route to standard approver (e.g., BA/PM)
  IF_LEGAL_RISK_DETECTED: Route to Legal specialist
  IF_FINANCIAL_RISK_DETECTED: Route to Finance/Business Owner
  IF_CONFIDENCE < 0.4: Route to Technical Lead (revision needed)

Step 7 → Step 8:
  CONDITION: Human approval received
  IF_APPROVED: Store as version; proceed to Step 9
  IF_REJECTED: Revert to draft; notify author; cycle back to Step 3 (revision)

Step 8 → Step 9:
  CONDITION: status == "approved"
  IF_FALSE: Skip indexing; mark as draft-only

Step 9 → Complete:
  CONDITION: Embeddings stored OR fallback search enabled
  ALWAYS: Send completion notification (Telegram/Email)
```

#### Workflow A Diagram (ASCII)

```
User Uploads File
    │
    ▼
[Routing Agent] ──────────────┐
    │ Classify                 │
    ├─────────────┬────────────┤
    │             │            │
   AUDIO      DOCUMENT      EMAIL
    │             │            │
    ▼             │            │
[STT Pipeline]   │            │
(ElevenLabs)     │            │
    │             │            │
    └──────┬──────┴────────────┘
           │
           ▼
[Data Extraction Agent]
  Extract: decisions, action_items
    │
    ▼
[RAG Verification Agent]
  Cross-reference KB
    │
    ▼
[Summarization Agent]
  Generate BRD/Minutes
    │
    ▼
[Validation Agent]
  Format compliance
  Risk detection
    │
    ▼
[HITL Approval]
  Route by risk type
    │ ┌─ If Rejected: Loop back
    │ │  to revision
    │ │
   APPROVED
    │
    ▼
[Version Storage]
  Update audit log
    │
    ▼
[RAG Indexing]
  Add to Qdrant KB
    │
    ▼
[Notification]
  Telegram + Email
```

---

### 2.2 Workflow B: Email Ingestion Sub-workflow (6-Step)

**Trigger:** Scheduled daily at 8:00 AM (cron job)  
**Frequency:** Daily  
**Expected Duration:** 2-5 minutes total  
**Integration:** Gmail API (poll unread emails tagged with project)

#### Step-by-Step Execution

| Step | Agent/Service | Action | Input | Output | SLA | Error Handling |
|------|---------------|--------|-------|--------|-----|--------|
| **1** | Gmail API | Fetch unread emails | {project_id, from: 8h ago, label: project_tagged} | [email_threads] | <30s | Fallback to retry after 5 min; max 3 retries |
| **2** | Data Extraction | Parse email content | {email_thread, participants, timestamp} | {senders, recipients, subject, body, action_items, decisions} | <1 min per email | Skip malformed emails; log error |
| **3** | Summarization | Create email digest | {parsed_emails, action_items, decisions} | {digest_md, item_count, stakeholder_summary} | <1 min | Return empty digest if no items found |
| **4** | Memory Agent | Store context | {email_thread_id, participants, decisions, timestamp} | {stored, project_context_updated} | <5 sec | Log storage errors; continue with process |
| **5** | Telegram Bot | Send notification | {digest_md, item_count, summary} | {notification_sent, message_id, timestamp} | <10 sec | Log error; retry once; skip if Telegram API down |
| **6** | RAG Indexing | Index email content | {digest_md, email_thread_id, embeddings} | {indexed, search_enabled, timestamp} | <1 min | Skip if Qdrant down; log for manual indexing |

#### Handoff & Filtering Logic

```yaml
Email Fetch (Step 1):
  Filter: unread AND created_after(8h) AND label="project_tagged"
  IF_NO_EMAILS: Skip Steps 2-6; send "No new items" notification (optional)
  IF_FETCH_FAILS: Retry 3x with exponential backoff (5s, 10s, 20s)

Email Parsing (Step 2):
  FOREACH email IN email_threads:
    Action: Extract action_items, decisions, mentions
    ERROR: Skip if parsing fails; log email_id for review
  IF_ALL_FAIL: Send alert to admin; skip downstream steps

Digest Generation (Step 3):
  Aggregate all action_items from all emails
  Group by owner/assignee
  Flag overdue items (due_date < today)
  Flag blocked items (status = "blocked")

Context Storage (Step 4):
  Store conversation thread metadata
  Track participants and their roles
  Enable "context from email" in future queries

Notification (Step 5):
  Send ONLY if digest.item_count > 0
  Include: summary, links to action items, approvers
  Format: Telegram message with inline buttons (optional)

Indexing (Step 6):
  Create embeddings for: subject, body, key decisions
  Tag with: email_thread_id, timestamp, participants
  SKIP_IF_QDRANT_DOWN: Fallback to PostgreSQL keyword search
```

#### Workflow B Diagram

```
Cron: 8:00 AM
    │
    ▼
[Gmail API]
Fetch unread emails (8h batch)
    │
    ├─ No emails? ──→ Skip to Step 5 (optional notification)
    │
    ▼
[Data Extraction Agent]
Parse email threads
Extract action items + decisions
    │
    ▼
[Summarization Agent]
Create email digest
Aggregate by owner
    │
    ▼
[Memory Agent]
Store context
  (thread_id, participants, decisions)
    │
    ▼
[Telegram Bot]
Send notification
    │
    ▼
[RAG Indexing]
Add email digest to KB
    │
    ▼
Mark emails as "processed"
Done
```

---

### 2.3 Workflow C: Daily Backlog Scan Cron Job (5-Step)

**Trigger:** Scheduled daily at 8:30 AM (30 min after email fetch)  
**Frequency:** Once per business day  
**Expected Duration:** 2-3 minutes  
**Data Source:** Google Sheets (project backlog)

#### Step-by-Step Execution

| Step | Agent/Service | Action | Input | Output | SLA | Error Handling |
|------|---------------|--------|-------|--------|-----|--------|
| **1** | Google Sheets API | Fetch backlog | {project_id, sheet_id, range: "A:G"} | {backlog_rows, headers, metadata} | <30s | Retry 3x; fallback to cache if available |
| **2** | Validation Agent | Filter & categorize | {backlog_rows, today_date} | {overdue, blocked, waiting_approval, completed_this_week} | <10s | Log parsing errors; continue with valid rows |
| **3** | Memory Agent | Retrieve context | {owner_ids, project_id, last_update} | {owner_contact_info, preference, timezone} | <5 sec | Use default contact if preferences unavailable |
| **4** | Telegram Bot | Send notifications | {filtered_items, owner_contact_info} | {notification_sent_count, timestamp} | <15 sec | Log failures; continue with other items |
| **5** | RAG Logging | Record scan event | {scan_timestamp, items_processed, action_summary} | {audit_log_entry, metrics_recorded} | <5 sec | Non-blocking; log errors separately |

#### Query & Filtering Logic

```sql
-- Step 1: Fetch backlog
SELECT * FROM google_sheets.backlog 
WHERE project_id = {project_id} 
  AND status IN ('New', 'In Progress', 'Blocked', 'Waiting Approval')
ORDER BY due_date ASC;

-- Step 2: Categorize
CASE 
  WHEN due_date < TODAY() AND status != 'Completed' 
    THEN 'OVERDUE' (🔴 Red flag)
  WHEN status = 'Blocked' 
    THEN 'BLOCKED' (🟡 Yellow flag)
  WHEN status = 'Waiting Approval' AND updated_at < TODAY() - INTERVAL 2 days
    THEN 'WAITING_APPROVAL_2PLUS_DAYS' (⏳ Time flag)
  WHEN updated_at = TODAY()
    THEN 'COMPLETED_THIS_WEEK'
  ELSE 'ON_TRACK'
END AS category;

-- Step 3: Count metrics
COUNT(*) GROUP BY category;

-- Generate notification message
Message Structure:
  Header: "📋 **Daily Backlog Update** - [Date]"
  
  Section 1 - OVERDUE (🔴):
    • [Task Title] (Due: [Date]) @Owner
    
  Section 2 - BLOCKED (🟡):
    • [Task Title] (Blocker: [Type]) @Owner
    
  Section 3 - WAITING APPROVAL (⏳):
    • [Task Title] (Waiting [N] days) @Approver
    
  Section 4 - METRICS (✅):
    Completed this week: [N] items
    Still pending: [N] items
```

#### Notification Telegram Template

```
📋 **Daily Backlog Update** - 2026-03-14

🔴 **OVERDUE** (3 items):
  • Project kick-off meeting notes (Due: 2026-03-12) @Alice
  • Payment module design doc (Due: 2026-03-10) @Bob
  • Security audit report (Due: 2026-03-11) @Charlie

🟡 **BLOCKED** (2 items):
  • Integration API testing (Blocker: Waiting for 3rd party API) @Bob
  • Database migration (Blocker: Waiting for DBA approval) @Charlie

⏳ **WAITING APPROVAL** (1 item):
  • Cost estimate for Phase 2 (Waiting 2+ days) [Link to approver: @DigitalOwner]

✅ **METRICS**:
  • Completed this week: 8 items
  • Still pending: 14 items
  • On-track completion rate: 64%
```

#### Workflow C Diagram

```
Cron: 8:30 AM
    │
    ▼
[Google Sheets API]
Fetch backlog (status != Completed)
    │
    ▼
[Validation Agent]
Categorize:
  - OVERDUE (due_date < today)
  - BLOCKED (status = blocked)
  - WAITING_APPROVAL_2+_DAYS
  - COMPLETED_THIS_WEEK
    │
    ▼
[Memory Agent]
Get owner contact info + preferences
    │
    ▼
[Telegram Bot]
Format + send notification
  (one message per category)
    │
    ▼
[RAG Logging]
Record audit entry
  (metrics, timestamp, action summary)
    │
    ▼
Done (waiting for Friday 5PM for Workflow D)
```

---

### 2.4 Workflow D: Weekly Digest Report (Scheduled Friday 5PM)

**Trigger:** Time-based cron, Friday at 5:00 PM  
**Frequency:** Weekly (once per week)  
**Expected Duration:** 3-5 minutes  
**Scope:** Aggregate all backlog changes for the week

#### Step-by-Step Execution

| Step | Agent/Service | Action | Input | Output | SLA | Error Handling |
|------|---------------|--------|-------|--------|-----|--------|
| **1** | Google Sheets API | Fetch weekly activity | {project_id, week_start_date, week_end_date} | {backlog_changes, completed_items, newly_blocked} | <30s | Fallback to cache; retry 2x |
| **2** | Data Extraction | Parse activity log | {backlog_changes, approvals, updates} | {summary_items, metrics, trends} | <1 min | Log parsing errors; continue with available data |
| **3** | Summarization | Generate digest | {weekly_summary, metrics, trends} | {digest_md, readability_score} | <2 min | Use template fallback if LLM fails |
| **4** | Telegram Bot | Send digest | {digest_md, project_context} | {digest_sent, message_id, timestamp} | <10 sec | Retry 3x exponential backoff |
| **5** | RAG Indexing | Archive digest | {digest_md, week_id} | {indexed, searchable, timestamp} | <1 min | Non-blocking; log separately |

#### Weekly Digest Template

```markdown
# **Weekly Digest** — [Week of Mon-Fri, YYYY-MM-DD]

## 📊 Metrics Summary
- ✅ Completed this week: **8 items**
- 🟡 Blocked items: **2 items** (same as last week)
- ⏳ Waiting approval: **3 items** (↑ +1 from last week)
- 🔴 Overdue items: **1 item** (↓ -1 from last week)

## ✅ Completed This Week (8 items)
1. [Title] — Completed [Day] by @Owner
2. [Title] — Completed [Day] by @Owner
...

## 🟡 Still Blocked (2 items)
1. [Title] — Blocker: [Type] — *Since [N] days* → @Owner
2. [Title] — Blocker: [Type] — *Since [N] days* → @Owner

## ⏳ Waiting Approval (3 items)
1. [Title] — Waiting [N] days → @ApproverName
2. [Title] — Waiting [N] days → @ApproverName
3. [Title] — Waiting [N] days → @ApproverName

## 🔴 Overdue (1 item)
1. [Title] — Due [Date] → @Owner (⚠️ **ACTION REQUIRED**)

## 📈 Trends & Insights
- Completion rate: **57%** (↑ +5% from last week)
- Average time to approval: **2.3 days** (↓ -0.5 days)
- Most common blocker: **3rd-party API delays** (affects 2 items)

## 🎯 Top Priority Next Week
1. **Resolve 3rd-party API blocker** → Unblock 2 items
2. **Approve pending cost estimate** → Unblock Phase 2 planning
3. **Close overdue security audit** → Compliance requirement

---
*Digest generated automatically at 5:00 PM every Friday*
*Questions? Contact your Project Manager*
```

#### Workflow D Diagram

```
Cron: Friday 5:00 PM
    │
    ▼
[Google Sheets API]
Fetch weekly backlog activity
(Mon-Fri changes, completions, blocks)
    │
    ▼
[Data Extraction Agent]
Parse activity log
Aggregate metrics
    │
    ▼
[Summarization Agent]
Generate digest report
Format with trends + insights
    │
    ▼
[Telegram Bot]
Send weekly digest
    │
    ▼
[RAG Indexing]
Archive digest for searchability
    │
    ▼
Done (next digest: next Friday)
```

---

### 2.5 Workflow E: Approval Reminders (Event-Driven, 2-Day Threshold)

**Trigger:** Event-driven (document status changes to "waiting_approval")  
**Frequency:** Per approval document  
**Expected Duration:** <1 minute per check  
**Escalation:** Reminder after 2 days; escalate after 4 days

#### Step-by-Step Execution

| Step | Agent/Service | Action | Input | Output | SLA | Error Handling |
|------|---------------|--------|-------|--------|-----|--------|
| **1** | PostgreSQL Query | Check approval age | {project_id, status: "waiting_approval", created_at < 2d ago} | {pending_approvals, owner_info, approver_contact} | <5 sec | Fallback to cache; non-critical |
| **2** | Memory Agent | Retrieve approver preferences | {approver_id, project_id} | {contact_method, language, timezone} | <3 sec | Use defaults if preferences unavailable |
| **3** | Telegram Bot | Send reminder | {doc_title, approver_name, doc_link, due_date} | {reminder_sent, timestamp} | <5 sec | Log failure; continue with next item |
| **4** | PostgreSQL Update | Log reminder event | {approval_id, reminder_sent_timestamp, reminder_count} | {logged, updated_row_count} | <3 sec | Non-blocking; continue process |
| **5** | Escalation Check | If >=4 days, escalate | {approval_age, escalation_threshold = 4 days} | {escalated_to_manager, notification_sent} | <5 sec | Log escalation; notify project admin |

#### Reminder Logic & Thresholds

```yaml
Approval Age Tracking:
  - 0-2 days: Silent (no reminder)
  - 2 days: Send first reminder (Telegram)
  - 3+ days: Send daily reminder (Telegram + Email)
  - 4+ days: **ESCALATE** to approver's manager + project PM
  - 6+ days: **ESCALATE** to project executive sponsor

Reminder Escalation Path:
  Document: BRD v2.0
  Approver: Alice (PM)
    │
    ├─ If no response after 2 days:
    │  ├─ Send reminder to Alice (Telegram)
    │
    ├─ If no response after 3 days:
    │  ├─ Daily reminder to Alice (Email)
    │
    ├─ If no response after 4 days:
    │  ├─ Escalate to Bob (Alice's Manager)
    │  ├─ Send message to Charlie (Project PM)
    │  └─ Send notification to admin dashboard
    │
    ├─ If no response after 6 days:
    │  ├─ Escalate to Executive Sponsor
    │  ├─ Send alert to project admin
    │  └─ Block related downstream tasks (optional)
```

#### Reminder Message Template

```
**📨 Approval Reminder**

Document: [Document Title] (v[N])
Submitted by: @Author
**Awaiting approval for [N] days**

👤 Approver: @ApproverName
📅 Due: [Date]
🔗 [Open approval link]

This is a friendly reminder. Please review and approve/reject by [deadline].
If you have questions, reply to this message or contact @ProjectManager.

---
*Automated reminder after 2 days of waiting*
*You will receive daily reminders until approval*
```

#### Workflow E Diagram

```
Event: Document status = "waiting_approval"
    │
    ▼
[Recurring Check] Every 4 hours
    │
    ├─ Query: approval age >= 2 days?
    │  └─ YES ──→ Continue
    │  └─ NO ───→ Skip
    │
    ▼
[Memory Agent]
Get approver contact + preferences
    │
    ├─ If approval_age == 2 days:
    │  └─ Send first reminder (Telegram)
    │
    ├─ If approval_age >= 3 days:
    │  └─ Send daily reminder (Email)
    │
    ├─ If approval_age >= 4 days:
    │  └─ Escalate to manager + PM
    │
    ├─ If approval_age >= 6 days:
    │  └─ Escalate to Executive Sponsor
    │  └─ Block downstream tasks (optional)
    │
    ▼
[PostgreSQL Update]
Log reminder sent + count
    │
    ▼
Done (check again in 4 hours)
    
    [Resolves when approver responds]
```

---

## 3. Event Triggers

### 3.1 Event Trigger Categories

| Event Type | Source | Trigger Condition | Action | Target Workflow |
|-----------|--------|------------------|--------|------------------|
| **Upload Event** | User Web UI | Document/recording file uploaded | Classify file type | Workflow A (Doc Ingestion) → Workflow A |
| **Email Event** | Gmail API | New email arrives for project | Parse email thread | Workflow B (Email Ingestion) |
| **Cron Event (Daily)** | Scheduler | 8:00 AM UTC | Fetch backlog status | Workflow C (Daily Backlog) |
| **Cron Event (Weekly)** | Scheduler | Friday 5:00 PM UTC | Aggregate metrics | Workflow D (Weekly Digest) |
| **Approval Event** | PostgreSQL trigger | Document status = "waiting_approval" | Check age & remind | Workflow E (Approval Reminders) |
| **API Event** | External webhook | 3rd-party system posts data | Ingest & process | Workflow A (Doc Ingestion) |
| **Manual Escalation** | User / Admin | User clicks "escalate approval" | Route to specialist | Workflow E (Approval → Escalation) |

### 3.2 Event Trigger Detailed Specifications

#### 3.2.1 Upload Event (Workflow A)

```yaml
Event Name: DocumentUpload
Source: HTTP POST /api/upload
Payload:
  file: {filename, size_bytes, mime_type}
  project_id: uuid
  user_id: uuid
  document_type: "meeting_recording" | "email_export" | "document"
  upload_timestamp: ISO8601

Trigger Condition:
  - file.size_bytes > 0 AND file.size_bytes < 500MB
  - mime_type IN [audio/*, video/*, application/pdf, application/vnd.ms-word*]
  - project_id exists AND user has access

Action (CrewAI Router):
  IF document_type == "meeting_recording":
    → Route to Workflow A with STT enabled
  ELIF document_type == "email_export":
    → Route to Workflow B (Email Ingestion)
  ELIF document_type == "document":
    → Route to Workflow A with document parsing

Success Criteria:
  - File persisted to Google Drive
  - Workflow routed within 5 seconds
  - User receives "processing started" notification
```

#### 3.2.2 Email Event (Workflow B)

```yaml
Event Name: EmailIngestCron (Pull-based, not push-based for MVP)
Source: Scheduled task (n8n webhook or Airflow)
Trigger Time: Daily 8:00 AM UTC
Payload:
  project_id: uuid
  from_timestamp: NOW() - 24 hours
  label_filter: "project_tagged" (configurable)

Trigger Condition:
  - Cron expression: "0 8 * * *" (daily 8 AM)
  - Gmail API available (health check)
  - Unread emails count > 0

Action:
  1. Fetch emails from Gmail
  2. Parse each email
  3. Extract action items + decisions
  4. Generate digest
  5. Send Telegram notification

Success Criteria:
  - All unread emails processed
  - Notification sent within 2 minutes
  - Processed emails marked as read
```

#### 3.2.3 Daily Backlog Scan (Workflow C)

```yaml
Event Name: DailyBacklogScan
Source: Scheduled task
Trigger Time: Daily 8:30 AM UTC (30 min after email fetch)
Payload:
  project_id: uuid
  scan_date: TODAY()
  google_sheets_range: "A:G"

Trigger Condition:
  - Cron expression: "30 8 * * *" (daily 8:30 AM)
  - Google Sheets API available
  - Backlog has records

Action:
  1. Fetch backlog from Google Sheets
  2. Categorize: OVERDUE | BLOCKED | WAITING | COMPLETED
  3. Send Telegram notification per category
  4. Update memory with owner contact info
  5. Log metrics for weekly digest

Success Criteria:
  - Backlog fetched successfully
  - Notification categories sent
  - Metrics logged
```

#### 3.2.4 Weekly Digest (Workflow D)

```yaml
Event Name: WeeklyDigestDueGeneration
Source: Scheduled task
Trigger Time: Friday 5:00 PM UTC
Payload:
  project_id: uuid
  week_start: Monday (calculated from Friday)
  week_end: Friday (current date)

Trigger Condition:
  - Cron expression: "0 17 * * 5" (Friday 5 PM)
  - MIN 1 completed item this week OR MIN 1 blocked item

Action:
  1. Fetch weekly activity from Google Sheets + audit logs
  2. Aggregate metrics (completed, blocked, overdue)
  3. Calculate trends (week-over-week changes)
  4. Generate digest markdown
  5. Send via Telegram

Success Criteria:
  - Digest generated within 3 minutes
  - Sent to configured Telegram group
  - Archived for future search
```

#### 3.2.5 Approval Reminder (Workflow E)

```yaml
Event Name: ApprovalAgeCheck
Source: PostgreSQL trigger OR recurring query
Trigger Frequency: Every 4 hours (or real-time if using DB trigger)
Trigger Condition (Check):
  approval.status == "waiting_approval"
  AND approval.created_at < NOW() - 2 DAYS
  AND approval.reminder_last_sent < NOW() - 24 HOURS (avoid spam)

Action (Per threshold):
  IF approval_age == 2 days:
    → Send first gentle reminder (Telegram)
  ELIF approval_age >= 3 days AND approval_age < 4 days:
    → Send daily reminder + escalate to email
  ELIF approval_age >= 4 days:
    → Escalate to approver's manager + project PM
  ELIF approval_age >= 6 days:
    → Escalate to executive sponsor + block downstream tasks

Success Criteria:
  - Reminder sent within 30 seconds of trigger
  - No duplicate reminders within 24 hours
  - Escalation logged in audit trail
```

### 3.3 Event-to-Workflow Routing Matrix

```
Event Received
    │
    ├─ Upload (Audio/Video) ────→ Workflow A (STT enabled)
    │
    ├─ Upload (Document) ────────→ Workflow A (document parsing)
    │
    ├─ Email Fetch (8:00 AM) ────→ Workflow B (email digest)
    │   │
    │   └─ Triggers Workflow C at 8:30 AM
    │
    ├─ Backlog Scan (8:30 AM) ───→ Workflow C (daily update)
    │
    ├─ Friday 5:00 PM ───────────→ Workflow D (weekly digest)
    │
    ├─ Approval Status Change ───→ Workflow E (reminder schedule)
    │
    └─ Manual Escalation ───────→ Workflow E (priority escalation)
```

---

## 4. Workflow Orchestration

### 4.1 Orchestration Engine & Framework

**Selected:** CrewAI (Multi-Agent Framework)

**Rationale:**
- Clear role division (each agent owns specific skills)
- Team-focused task execution (agents coordinate via shared context)
- Built-in state management (agent_state table in PostgreSQL)
- Flexible handoff mechanism (agent → agent → human)

**Alternative Considered:**
- LangChain: More flexible but requires custom orchestration logic
- LangGraph: Explicit state graphs; more verbose but clear control flow
- n8n: No-code/low-code visual workflows; selected for HITL approval steps (Phase 2)
- Temporal: Distributed durable workflows; overkill for MVP single-node

### 4.2 State Management Architecture

#### 4.2.1 Agent State Table (PostgreSQL)

```sql
CREATE TABLE agent_state (
    state_id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL,
    agent_name VARCHAR(50) NOT NULL,    -- "Routing", "Data Extraction", etc.
    project_id UUID NOT NULL,
    user_id UUID NOT NULL,
    
    -- State data
    state_data JSONB NOT NULL,           -- {current_step, extracted_entities, ...}
    
    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                -- For cleanup; NULL = persist
    
    -- Metadata
    parent_agent VARCHAR(50),            -- Who called this agent?
    next_agent VARCHAR(50),              -- Who should run next?
    handoff_data JSONB,                  -- Data to pass to next agent
    
    -- Status
    status VARCHAR(20),                  -- "in_progress", "completed", "failed"
    error_message TEXT,                  -- If status = "failed"
    
    -- Audit
    created_by UUID,
    last_updated_by UUID,
    
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Index for fast queries
CREATE INDEX idx_agent_state_workflow ON agent_state(workflow_id, agent_name);
CREATE INDEX idx_agent_state_status ON agent_state(status, expires_at);
```

#### 4.2.2 State Data Schema (JSONB)

```json
{
  "agent_name": "Data Extraction Agent",
  "current_step": 3,
  "workflow_type": "document_ingestion",
  
  "extracted_entities": {
    "decisions": [
      {
        "text": "We decided to use React for frontend",
        "stakeholders": ["Alice", "Bob"],
        "context": "During architecture discussion",
        "confidence": 0.95
      }
    ],
    "action_items": [
      {
        "owner": "Charlie",
        "task": "Review React component library",
        "due_date": "2026-03-21",
        "priority": "HIGH",
        "confidence": 0.88
      }
    ],
    "requirements": [...]
  },
  
  "extraction_stats": {
    "transcript_length": 5000,
    "entity_count": 42,
    "confidence_avg": 0.89
  },
  
  "processing_metadata": {
    "input_file": "meeting_2026-03-14.mp3",
    "file_hash": "abc123def456...",
    "processing_start_time": "2026-03-14T09:00:00Z",
    "processing_duration_ms": 45000
  },
  
  "errors": []
}
```

### 4.3 Agent Handoff Mechanism

#### 4.3.1 Handoff Process (Pseudo-code)

```python
class CrewAIOrchestrator:
    def handoff_to_next_agent(self, current_agent, state_data, next_agent_name):
        """
        Atomic handoff from one agent to the next.
        Ensures no data loss and clear state transitions.
        """
        
        # Step 1: Save current agent's state
        current_state_record = {
            "workflow_id": state_data["workflow_id"],
            "agent_name": current_agent.name,
            "state_data": state_data,
            "status": "completed",
            "next_agent": next_agent_name,
            "handoff_data": current_agent.output,
            "last_updated": now()
        }
        self.db.insert("agent_state", current_state_record)
        
        # Step 2: Prepare handoff data for next agent
        handoff_payload = {
            "workflow_id": state_data["workflow_id"],
            "project_id": state_data["project_id"],
            "user_id": state_data["user_id"],
            "previous_agent": current_agent.name,
            "previous_output": current_agent.output,
            "shared_context": state_data["shared_context"]
        }
        
        # Step 3: Initialize next agent
        next_agent = self.get_agent(next_agent_name)
        next_agent.initialize(handoff_payload)
        
        # Step 4: Execute next agent
        next_agent.execute()
        
        # Step 5: Log handoff in audit trail
        self.audit_log({
            "event": "agent_handoff",
            "from_agent": current_agent.name,
            "to_agent": next_agent_name,
            "workflow_id": state_data["workflow_id"],
            "timestamp": now()
        })
```

#### 4.3.2 Synchronous vs Asynchronous Execution

```
SYNCHRONOUS (Default for MVP):
┌────────────────────────────────────────────────────────┐
│ User Upload                                            │
├────────────────────────────────────────────────────────┤
│ Routing Agent (sync) ─→ blocks until classification   │
│ Data Extraction Agent (sync) ─→ blocks until extraction │
│ RAG Verification (sync) ─→ blocks until verification   │
│ Summarization Agent (sync) ─→ blocks until generation  │
│ Validation Agent (sync) ─→ blocks until validation     │
│ HITL Approval (async) ─→ returns approval request     │
└────────────────────────────────────────────────────────┘
Total time: ~8-12 minutes (mostly STT + validation)

ASYNCHRONOUS (Phase 2 optimization):
┌──────────────────────────────────┐
│ User Upload → Routing Agent      │ (user gets immediate confirmation)
├──────────────────────────────────┤
│ [Background Queue]               │
│  - Data Extraction (async job)   │
│  - RAG Verification (async job)  │
│  - Summarization (async job)     │
│  - Validation (async job)        │
│  - Notification on completion    │
└──────────────────────────────────┘
Total time: User doesn't wait; gets notification when ready
```

### 4.4 Parallel Processing

**Workflow A Parallelization:**
- Audio upload + document parsing can run in parallel (independent)
- Example: During STT (5+ min), other content extraction can proceed

```python
# Pseudo-code for parallel processing
async def process_multimodal_input(upload_request):
    tasks = []
    
    # Task 1: STT (if audio file)
    if upload_request.has_audio():
        tasks.append(
            run_stt_async(upload_request.audio_file)
        )
    
    # Task 2: Document parsing (if document)
    if upload_request.has_document():
        tasks.append(
            run_document_parsing_async(upload_request.document)
        )
    
    # Wait for all tasks
    results = await asyncio.gather(*tasks)
    
    # Merge results
    combined_content = merge_results(*results)
    
    # Pass to Data Extraction
    await data_extraction_agent.process(combined_content)
```

---

## 5. Failure Handling

### 5.1 Failure Categories & Responses

| Failure Type | Severity | Trigger | Handling | Escalation | Recovery |
|--------------|----------|---------|----------|-----------|----------|
| **STT Timeout** | HIGH | ElevenLabs API >5 min | Retry with Deepgram (fallback) | Notify user if both fail | User provides manual transcript |
| **LLM API Rate Limit** | MEDIUM | OpenRouter quota exceeded | Queue request + exponential backoff | Fallback to DeepSeek model | Auto-retry in 5-10 min |
| **Database Connection** | CRITICAL | PostgreSQL unavailable | Return error; halt workflow | Page on-call DBA | Automatic reconnection retry |
| **Vector DB (Qdrant)** | HIGH | Qdrant service down | Fallback to keyword search (PostgreSQL) | Alert admin | Use fallback indefinitely until recovery |
| **Validation Failure** | MEDIUM | Format schema mismatch | Reject document; request reformatting | Notify author | Author fixes and resubmits |
| **HITL Approval Timeout** | MEDIUM | No response after 6 days | Escalate to manager + exec sponsor | Auto-escalation | Project PM manually approves or rejects |
| **Injection Attack** | CRITICAL | Prompt injection detected | Block input; log security event | Security alert | User receives feedback; retries with safe input |
| **Data Corruption** | CRITICAL | State data invalid | Revert to last known good state | Incident investigation | Restore from backup |

### 5.2 Error Propagation & Escalation Paths

```
Error Detected
    │
    ├─ TRANSIENT ERROR (rate limit, timeout)
    │  │
    │  ├─ Retry 1 (immediate)
    │  ├─ Retry 2 (5 sec delay)
    │  ├─ Retry 3 (10 sec delay)
    │  │
    │  └─ All retries fail:
    │     └─ Route to FALLBACK SERVICE (Deepgram, DeepSeek, keyword search)
    │        └─ If fallback succeeds: Continue
    │        └─ If fallback fails: Escalate to user/admin
    │
    ├─ PERMANENT ERROR (validation fail, injection attack, data corruption)
    │  │
    │  └─ Do NOT retry; escalate immediately
    │     ├─ Validation error → Notify author; request resubmission
    │     ├─ Injection attack → Block; log security event; notify security team
    │     ├─ Data corruption → Rollback to backup; incident investigation
    │     └─ Database unavailable → Page on-call; switch to read-only if needed
    │
    └─ APPROVAL TIMEOUT (>2 days waiting)
       │
       ├─ Day 2: Gentle reminder (Telegram)
       ├─ Day 3: Daily reminder (Email)
       ├─ Day 4: Escalate to approver's manager
       ├─ Day 6: Escalate to executive sponsor
       └─ Day 7: Auto-approve or block (configurable per project)
```

### 5.3 Graceful Degradation Strategy

```yaml
Scenario 1: Qdrant Vector DB Down
  Normal Path:
    Data Extraction → RAG Verification (semantic search) → Summarization
  Degraded Path:
    Data Extraction → RAG Verification (keyword search fallback) → Summarization
  Impact: Slower RAG results; less accurate citations; continue processing
  Notification: "Knowledge base search temporarily using basic search; results may be less relevant"

Scenario 2: ElevenLabs STT Unavailable
  Normal Path:
    Upload (audio) → STT (ElevenLabs) → Extraction
  Fallback Path 1:
    Upload (audio) → STT (Deepgram) → Extraction
  Fallback Path 2 (Manual):
    Upload (audio) + Manual Transcript → Extraction
  Impact: Delayed processing; manual intervention required
  Notification: "STT service unavailable. Please retry or upload transcript manually."

Scenario 3: LLM API Rate Limit
  Normal Path:
    Extraction → LLM Inference (OpenRouter) → Summarization
  Degraded Path:
    [Queue request, exponential backoff, use cached responses if available]
  Fallback Path:
    Extraction → LLM Inference (DeepSeek via fallback) → Summarization
  Impact: Slower document generation; potential queueing
  Risk Level: MEDIUM (can complete, just slower)

Scenario 4: PostgreSQL Database Down
  Normal Path: All state stored in PostgreSQL
  Impact: CRITICAL — Cannot continue ANY workflow
  Escalation: Auto-page on-call DBA
  Recovery: Manual failover to read replica; restore from backup
```

### 5.4 Circuit Breaker Pattern

For flaky external APIs (ElevenLabs, OpenRouter), implement circuit breaker:

```python
class CircuitBreaker:
    states = ["CLOSED", "OPEN", "HALF_OPEN"]
    
    def __init__(self, failure_threshold=5, timeout_seconds=60):
        self.state = "CLOSED"
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.last_failure_time = None
    
    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if self.is_timeout_expired():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenException()
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = now()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"  # Stop calling; use fallback
    
    def is_timeout_expired(self):
        return (now() - self.last_failure_time).seconds > self.timeout_seconds

# Usage
elevenlabs_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

try:
    transcript = elevenlabs_breaker.call(elevenlabs_stt, audio_file)
except CircuitBreakerOpenException:
    # Switch to Deepgram fallback
    transcript = deepgram_stt(audio_file)
```

---

## 6. Retry Strategy

### 6.1 Transient vs Permanent Errors

| Error Type | Transient? | Max Retries | Backoff Strategy | Action on Failure |
|-----------|-----------|-------------|------------------|------------------|
| **Rate Limit (429)** | ✅ YES | 5 | Exponential + jitter | Fallback service or queue |
| **Timeout (504)** | ✅ YES | 3 | Exponential (5s, 10s, 20s) | Fallback service |
| **Connection Error** | ✅ YES | 3 | Exponential (3s, 6s, 12s) | Fallback or retry later |
| **Validation Error (400)** | ❌ NO | 0 | N/A | Return error to user; request correction |
| **Authorization Error (401/403)** | ❌ NO | 0 | N/A | Log security event; escalate |
| **Not Found (404)** | ❌ NO | 0 | N/A | Return error; check resource ID |
| **Server Error (500)** | ⚠️ MAYBE | 2 | Exponential (5s, 10s) | Check service status; escalate if persistent |
| **Bad Gateway (502)** | ✅ YES | 3 | Exponential (5s, 10s, 20s) | Switch to fallback service |
| **Service Unavailable (503)** | ✅ YES | 5 | Exponential + circuit breaker | Queue or fallback |

### 6.2 Exponential Backoff with Jitter

```python
def calculate_backoff_delay(attempt_number, base_delay=1, max_delay=60):
    """
    Calculate exponential backoff delay with jitter to avoid thundering herd.
    Formula: min(max_delay, base_delay * 2^attempt + random(-jitter, +jitter))
    """
    import random
    
    exponential_delay = base_delay * (2 ** attempt_number)
    jitter = random.uniform(-0.1 * exponential_delay, 0.1 * exponential_delay)
    delay = min(max_delay, exponential_delay + jitter)
    
    return delay

# Example retry sequence for API call
def retry_with_backoff(func, *args, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func(*args)
        except TransientError as e:
            if attempt == max_retries - 1:
                raise  # Give up after max retries
            
            delay = calculate_backoff_delay(attempt, base_delay)
            logger.warning(f"Transient error on attempt {attempt+1}. "
                         f"Retrying in {delay:.2f}s. Error: {e}")
            time.sleep(delay)
        except PermanentError as e:
            logger.error(f"Permanent error (non-retryable): {e}")
            raise  # Don't retry permanent errors

# Usage
transcript = retry_with_backoff(
    elevenlabs_stt,
    audio_file,
    max_retries=5,
    base_delay=1  # Start with 1 second
)
```

**Backoff Sequence Example:**
```
Attempt 1: Immediate retry
Attempt 2: ~2-3 seconds (2^1 = 2 + jitter)
Attempt 3: ~4-5 seconds (2^2 = 4 + jitter)
Attempt 4: ~8-10 seconds (2^3 = 8 + jitter)
Attempt 5: ~16-20 seconds (2^4 = 16 + jitter)
Attempt 6+: Max 60 seconds (ceiling)
```

### 6.3 Timeout Thresholds

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| STT (audio) | 300 sec (5 min/hour) | ElevenLabs SLA + audio duration |
| LLM Inference | 30 sec | Typical response time; fail fast |
| Database Query | 10 sec | Fast indexed queries; slow = prob. issue |
| Vector Search (Qdrant) | 5 sec | SLA target <500ms; 10x buffer |
| External API (Gmail, Drive) | 15 sec | Google API standard timeout |
| Approval Notification | 10 sec | Non-critical; best-effort |
| Full Workflow (Workflow A) | 15 min | Hard limit; escalate if exceeded |

### 6.4 Dead-Letter Queue (DLQ) for Failed Tasks

For critical async tasks that fail after all retries:

```sql
-- Dead-letter queue table
CREATE TABLE task_dlq (
    dlq_id UUID PRIMARY KEY,
    original_workflow_id UUID,
    task_type VARCHAR(100),  -- "stt", "extraction", "llm_inference", etc.
    payload JSONB,
    error_message TEXT,
    retry_count INT,
    last_error_time TIMESTAMP,
    created_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_action VARCHAR(100),  -- "manual_intervention", "deleted", "retried"
    
    FOREIGN KEY (original_workflow_id) REFERENCES workflows(workflow_id)
);

-- Process DLQ periodically
SELECT * FROM task_dlq 
WHERE resolved_at IS NULL AND created_at < NOW() - INTERVAL 1 hour
ORDER BY last_error_time ASC
LIMIT 10;  -- Batch process
```

---

## 7. Human-in-the-Loop (HITL) Design

### 7.1 HITL Approval Gates

| Gate # | Trigger | What Human Sees | Approver Role | Action Options | Timeout Behavior |
|--------|---------|-----------------|---------------||----|
| **1** | Any legal/contractual terms detected | Document + risk flags + context | Legal Specialist | Approve / Reject / Request Revisions | 48h SLA; escalate @ 72h |
| **2** | Financial figures (cost, budget, pricing) | Document + flagged amounts | Finance Manager | Approve / Reject / Request Revisions | 24h SLA; escalate @ 48h |
| **3** | High-risk business decisions | Document + decision summary | Business Owner/PM | Approve / Reject / Request Expert Review | 24h SLA; escalate @ 48h |
| **4** | Extraction confidence <60% | Document + uncertainty map | Subject Matter Expert | Confirm / Revise / Reject | 24h SLA; auto-escalate @ 36h |
| **5** | PII or sensitive data detected | Document + masked preview | Data Privacy Officer | Approve / Redact / Reject | 12h SLA; escalate @ 24h |
| **6** | Format/compliance issue | Document + non-compliant sections | Document Admin | Fix / Approve / Reject | 12h SLA; auto-fix @ 18h |
| **7** | Multi-approval workflow (BRD) | Document + approval chain | BA → PM → Business Owner | Approve at each step | 24h per step; escalate @ 36h |

### 7.2 Approval Workflow State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                 APPROVAL WORKFLOW STATE MACHINE             │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │ Draft (Initial)  │
                    └────────┬─────────┘
                             │ Validation passes
                             ▼
        ┌────────────────────────────────────────┐
        │ Pending Approval (Awaiting Review)     │
        │ - Route to appropriate approver(s)    │
        │ - Set deadline (24h default)          │
        │ - Send notification                   │
        └─────┬────────────────────────┬────────┘
              │                        │
          Approved                  Rejected
              │                        │
              ▼                        ▼
        ┌──────────────┐    ┌──────────────────────┐
        │ Step N Pass  │    │ Returned to Draft     │
        │ (if multi)   │    │ - Author notified    │
        └────┬─────────┘    │   of feedback        │
             │              │ - Can revise         │
        All steps ──────────│─ and resubmit        │
        approved?           └──────────────────────┘
             │
             ▼
        ┌──────────────┐
        │ Final Approved│
        │ - Store as version
        │ - Publish
        │ - Index in RAG
        └────┬──────────┘
             │
             ▼
        ┌──────────────┐
        │ Published    │
        │ (Searchable) │
        └──────────────┘


Timeout Escalation Path:
┌─────────────────────────────────────┐
│ Awaiting [Role] Review              │
├─────────────────────────────────────┤
│ @ 24 hours: Send 1st reminder       │
│ @ 36 hours: Escalate to manager     │
│ @ 48 hours: Escalate to exec        │
│ @ 6 days: Auto-approve OR block     │
│            (configurable)           │
└─────────────────────────────────────┘
```

### 7.3 Approval UI Components (MVP Web)

**Approval Request Card:**
```
┌─────────────────────────────────────────────┐
│ 📄 Approval Request                         │
├─────────────────────────────────────────────┤
│                                             │
│ Document: BRD v2.0 - Payment Module        │
│ Submitted by: @Alice (BA)                  │
│ Submitted at: 2026-03-14 14:00              │
│                                             │
│ Awaiting: BA → PM → Legal → Business Owner  │
│ Current Step: PM Review ⏳                   │
│ Time Remaining: 18 hours                    │
│                                             │
│ ⚠️ Risk Flags:
│   🔴 LEGAL: Contract terms detected
│   🟡 FINANCIAL: Budget amount $50K
│                                             │
│ [View Full Document] [Compare Versions]    │
│                                             │
├─────────────────────────────────────────────┤
│ Action:                                     │
│ ☑ Approve                                   │
│ ○ Request Revisions (comment...)            │
│ ○ Reject (reason...)                        │
│                                             │
│ [Submit] [Cancel]                           │
└─────────────────────────────────────────────┘
```

### 7.4 HITL Context & Supporting Info

When a human approver is presented with a document, provide:

```json
{
  "approval_context": {
    "document_id": "doc_abc123",
    "document_type": "brd_urs",
    "version": 2,
    "created_by": "Alice (BA)",
    "created_at": "2026-03-14T14:00:00Z",
    "submission_timestamp": "2026-03-14T14:00:00Z"
  },
  
  "confidence_scores": {
    "extraction_confidence": 0.89,
    "rag_verification_confidence": 0.76,
    "overall_confidence": 0.82,
    "interpretation": "MEDIUM-HIGH (minor gaps exist)"
  },
  
  "risk_summary": {
    "legal_terms_found": true,
    "legal_terms_count": 3,
    "financial_figures_found": true,
    "financial_total": "$50,000",
    "pii_detected": false,
    "high_risk_decisions": 2
  },
  
  "ungrounded_items": [
    {
      "claim": "Expected delivery by Q2 2026",
      "confidence": 0.42,
      "recommendation": "NEEDS_CONFIRMATION"
    }
  ],
  
  "change_summary": {
    "compared_to_version": 1,
    "added_sections": 2,
    "modified_sections": 3,
    "removed_sections": 0,
    "new_requirements_count": 5
  },
  
  "historical_context": {
    "similar_past_documents": [
      {
        "doc_id": "doc_xyz789",
        "title": "BRD v1.0 - Payment Module",
        "approval_time": "3 days",
        "approvers": ["PM", "Legal", "Business Owner"]
      }
    ],
    "typical_approval_sla": "2-3 business days"
  },
  
  "ai_assessment": {
    "format_compliant": true,
    "ready_for_approval": true,
    "required_approvers": ["PM", "Legal", "Business Owner"],
    "suggested_next_step": "Route to PM for standards review"
  }
}
```

### 7.5 HITL Notification Channels

**Primary:** Telegram (real-time, fast, mobile)  
**Secondary:** Email (formal record, detailed info)  
**Tertiary:** In-app notification (for web users)

**Telegram Message Template:**
```
📄 **Approval Request: BRD v2.0**

Document: Payment Module Requirements
Submitted by: @Alice
👤 Assigned to: @You (PM)

⚠️ **Risk Summary:**
  🟡 Contains financial figures: $50K
  🔴 Legal terms detected (contracts)

⏳ **Time Remaining:** 18 hours
🎯 **Step:** 1 of 4 (PM Review)

[Open in App] [Approve] [Request Changes]
```

---

## 8. Monitoring & SLA Metrics

### 8.1 Workflow SLA Dashboard

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Workflow A completion time | <10 min | >15 min |
| Workflow B (email) completion | <2 min | >5 min |
| Workflow C (backlog scan) completion | <2 min | >5 min |
| Workflow D (weekly digest) completion | <3 min | >5 min |
| Workflow E (reminder) latency | <30 sec | >1 min |
| HITL approval turn-around | <24h | >36h |
| STT accuracy (confidence) | >85% | <70% |
| RAG verification confidence | >60% | <40% |
| Overall document confidence | >80% | <60% |

### 8.2 Health Check Endpoints

```
GET /health - Overall system health
GET /workflow/{workflow_id}/status - Single workflow status
GET /api/health - Backend API status
GET /rag/health - RAG service status
GET /db/health - Database connectivity
```

---

## Summary

This workflow design provides:

✅ **5 parallel sub-workflows** (A: doc ingestion, B: email, C: daily backlog, D: weekly digest, E: approval reminders)  
✅ **7-layer fault handling** (transient/permanent errors, fallback services, graceful degradation)  
✅ **Exponential backoff retry strategy** with circuit breaker pattern  
✅ **7 HITL approval gates** with escalation paths and SLA monitoring  
✅ **CrewAI-based orchestration** with PostgreSQL state management  
✅ **Event-driven architecture** with 5 trigger types (upload, email, daily, weekly, approval events)  
✅ **Comprehensive audit logging** for compliance and debugging

**Ready for Phase 1 MVP implementation.**

---

**End of Workflow Design Document**
