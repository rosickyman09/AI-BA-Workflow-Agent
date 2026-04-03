**Step to start using Vibe coding inVSCode to build solution**

**Stage 0 — Workspace setup**

**目的**

先令 Copilot 全程有一致規則。

**做法**

1. **Finetune “Create .copilot-instructions.md”**

1.1 先喺 project root 建：

* .copilot-instructions.md
* docs/
* prompts/（可選）
* requirements/（可選）
* frontend/（可選,先預留）
* backend/（可選,先預留）
* gateway/（可選,先預留）
* infra/（可選,先預留）

1.2 After create .copilot-instructions.md之後：

* 在你的 project root 建一個檔案
* .copilot-instructions.md
* 把上面內容貼入
* Ask Copilot Run 整個 project 都會參考這些規則

**建議加入 Docker 規則**
 在 .copilot-instructions.md 加入：

* All major services should be containerized
* Each major service should have its own Dockerfile
* Use docker-compose.yml to orchestrate services
* Gateway should be containerized if single-port architecture is used
* Ports and service names must align with the approved system architecture
* Do not change Docker structure unless explicitly asked

**Stage 1 — Prepare requirement inputs**

**做法**

1. Ready User Requirement Document
2. Fill in “VS Code Copilot 完整解決方案需求書模板”

**輸出**

一份完整需求來源，俾 AI 再拆解。

**Stage 2 — Generate 4 core txt documents**

**做法**

用填好嘅模板，叫 AI 產出以下文件：

* 01\_project\_requirement.txt
* 02\_ai\_agent\_architecture.txt
* 03\_system\_architecture.txt
* 04\_deployment\_plan.txt

**建議**

你個 file name 建議統一格式，改為：

* 01\_project\_requirement.txt
* 02\_ai\_agent\_architecture.txt
* 03\_system\_architecture.txt
* 04\_deployment\_plan.txt

**Docker-wise 建議**
🐳在 03\_system\_architecture.txt 同 04\_deployment\_plan.txt 應已開始包含：

* containerized services
* service boundaries
* gateway needed or not
* single-port vs multi-port
* Docker Compose as deployment method

**Stage 3 — Ask mode 做 requirement analysis**

**Input**

01\_project\_requirement.txt

**Copilot Mode:** Ask Mode

**Prompt**

你原本嗰段基本上可以用，但我建議微調成更完整版本：

Here is my project requirement.

Please analyze and structure it into:

1. Business goal

2. Functional modules

3. Non-functional requirements

4. Data requirements

5. AI capabilities required

6. Risks, assumptions, and dependencies

7. Deployment and containerization assumptions

Then convert them into system modules and create:

* + docs/01\_requirement\_analysis.md

**Docker-wise 建議加入分析項目**
🐳✅ 建議在 prompt 加多兩點：

* deployment constraints
* containerization / environment assumptions

**Stage 4 — Plan mode 做 AI agent design**

**Input**

* 02\_ai\_agent\_architecture.txt
* docs/01\_requirement\_analysis.md

**Copilot Mode:** Plan Mode

**重點**

唔好只放 02\_ai\_agent\_architecture.txt。
最好連 Stage 3 輸出都一齊俾佢睇，因為 agent design 應該建基於真實 requirement，而唔係單靠 architecture 願景。

**Prompt**

Based on the following AI agent architecture document and requirement analysis,

design a multi-agent system.

Please provide:

1. Agent roles

2. Agent workflow

3. RAG pipeline

4. Memory design

5. Tools required for each agent

6. API interaction between agents

7. Guardrails, validation, and fallback logic

Create:

docs/02\_agent\_design.md

**補充**

加 guardrails, validation, fallback logic 會實用好多，尤其你做 AI BA / document / RAG 系統。

**Stage 4B — Plan mode 做 agent capability mapping**

**Input**
• docs/01\_requirement\_analysis.md
• docs/02\_agent\_design.md

**Copilot Mode:** Plan Mode

**重點**

呢一步係將 agent design 進一步落實成 skill mapping。
唔好跳過，因為 system architecture 應該建基於：
• agent roles
• agent workflow
• skills owned by each agent
• skills callable by each agent
• tools used by each skill
• input / output
• validation / fallback
• handoff to next agent

**Prompt**

Based on the requirement analysis and agent design,
create an agent capability mapping document.

For each AI agent, define:
1. Agent name
2. Agent responsibility
3. Skills owned by this agent
4. Skills callable by this agent
5. Tools used by each skill
6. Input / output of each skill
7. Validation / fallback
8. Handoff to next agent 9. Backend container 10. Separate AI service container 11. External managed service

Create:
docs/02b\_agent\_skill\_matrix.md

原因
system architecture 唔應該只根據 agent design 去畫，
而係要進一步根據每個 agent 對應嘅 skills 去決定：
• service boundaries
• module design
• API design
• data flow
• RAG / tool integration • Docker-wise

**Stage 5 — Workflow Design**

**Input**

* docs/01\_requirement\_analysis.md
* docs/02\_agent\_design.md

**Copilot Mode:** Ask Mode

**Prompt**

Design the system workflow and sub-workflows.

Please include:

1. Main workflow

2. Sub-workflows

3. Event triggers

4. Workflow orchestration

5. Failure handling

6. Retry strategy

7. Human-in-the-loop points

Create:

docs/02c\_workflow\_design.md

原因：

你現在：

agent design

→ skill mapping

→ architecture

但 AI system 中間應該有：workflow design

否則 architecture 有時會不清楚。

**Stage 5b — Plan mode 做 system architecture**

**Input**

* 03\_system\_architecture.txt
* docs/01\_requirement\_analysis.md
* docs/02\_agent\_design.md
* docs/02b\_agent\_skill\_matrix.md
* docs/02c\_workflow\_design.md

**Prompt**

Based on the system architecture document, requirement analysis, agent design, and agent skill mapping,

design the complete system architecture.

Please include:

1. Folder structure

2. Frontend architecture

3. Backend services

4. API gateway

5. Database schema

6. RAG infrastructure

7. AI agent integration

8. Ports allocation

9. Authentication and authorization

10. Logging, monitoring, and error handling

11. Containerization strategy

12. Dockerfile ownership by service

13. Gateway / reverse proxy design

14. Internal vs external ports

15. Docker Compose service structure

16. Volumes / persistent storage

Create:

docs/03\_system\_architecture.md

**原因**

architecture 唔應該只睇 03\_system\_architecture.txt，
而係要同 requirement + agent design 一齊對齊。

**Stage 6 — Architecture review / freeze**

呢步你原本冇寫，但我覺得要加。

**做法**

用 Ask 或 Plan mode，叫 Copilot review：

Please review the requirement analysis, agent design, agent skill mapping, and system architecture.

Check for inconsistency, missing dependencies, architecture conflicts, skill-to-agent mismatch, and implementation risks.

If aligned, provide a final implementation-ready summary and freeze the architecture.

Check also:

Docker/container boundaries

service-to-container alignment

gateway necessity

internal vs external port exposure

persistent volume requirements

deployment consistency

Create:

docs/04\_architecture\_freeze.md

**好處**

之後 Agent mode build code 時，就有一份 frozen design 參考。

**Docker-wise**

呢度要 review 埋以下項目：

container boundaries are consistent

gateway is required or not

frontend/backend/gateway dockerization is confirmed

port exposure is correct

persistent services have volumes

startup dependency order is sensible

**Stage 7 — Agent mode build the project**

**Input**

* docs/02b\_agent\_skill\_matrix.md
* docs/02c\_workflow\_design.md
* docs/03\_system\_architecture.md
* docs/04\_architecture\_freeze.md

**Prompt**

你原本呢段可以再加強：

Build the project based on the approved architecture.

Create the project structure and code step by step.

Do not change the architecture unless explicitly stated.

Tech stack: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Frontend: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Backend: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Database: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

AI orchestration: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Vector DB: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Please:

1. Create folders first

2. Create base config files

3. Create backend services

4. Create frontend structure

5. Create database schema/migrations

6. Create AI agent modules

7. Add basic logging and error handling

8. Explain what you created after each step

9. Create Dockerfiles for containerized services
10. Create gateway config if gateway is required
11. Prepare docker-related folder structure under /infra or service folders
12. Keep all service names consistent with planned docker-compose design

13. Generate backend/requirements.txt with ALL library versions pinned using == (e.g. fastapi==0.104.1, pydantic==2.5.0). Do NOT use >= or ~=
14. Generate frontend/package.json with ALL versions locked (remove ^ and ~)
15. Generate docs/08\_dependency\_versions.md listing every library, its pinned version, and reason for that version choice
16. After each module is built, run a per-module health check before proceeding to the next module:
 - Database built: docker compose up db, then verify connection and schema
 - Backend built: pytest backend/tests/ and curl-test all API endpoints
 - AI module built: test agent response, RAG retrieval, and fallback logic
 - Frontend built: npm test and browser verification
 Do NOT proceed to next module if current module test fails

\*\*Explanation: **13.** backend/requirements.txt — 所有 library 用 == pin 版本（e.g. fastapi==0.104.1），禁用 >= 或 ~= **14.** frontend/package.json — 所有版本 lock 死，移除 ^ 同 ~ **15.** docs/08\_dependency\_versions.md — 記錄每個 library 版本及選擇原因 **16.** 逐模組 health check gate：DB → Backend → AI → Frontend，唔通過唔可以繼續下一模組

Create:

* frontend/Dockerfile
* backend/Dockerfile
* gateway/Dockerfile（如需要）
* gateway/nginx.conf（如 single-port）
* 可先建立 infra/ folder

**重點**

加咗一句：

**Do not change the architecture unless explicitly stated.**

呢句好重要，防止佢 build build 下自己改設計。

**Stage 8 — Deployment and infra**

**8A — Ask mode 產出 deployment design**

Input:

* 04\_deployment\_plan.txt
* docs/03\_system\_architecture.md

Prompt:

Based on the deployment plan document and system architecture,

generate the deployment design.

Please include:

1. Docker compose structure

2. Environment variables

3. Service startup sequence

4. Health checks

5. Rollback strategy

6. Local development vs production setup

7. Dockerfiles required by each service
8. Reverse proxy / gateway routing rules
9. Docker volumes and persistent data
10. Container dependency order
11. Network segmentation
12. Image naming / build strategy

Create:

docs/05\_deployment\_plan.md

**8B — Agent mode 真正生成 infra files**

之後再用 Agent mode：

Based on docs/05\_deployment\_plan.md, generate the deployment files.

Please create:

- docker-compose.yml

- .env.example

- frontend/Dockerfile

- backend/Dockerfile

- gateway/Dockerfile（如需要）

- gateway/nginx.conf（如需要）

- deployment scripts

- health check configuration

- startup documentation

**原因**

Ask mode 適合先設計。
Agent mode 適合真係落手建 file。

**Stage 9 — Testing / validation / refinement**

**建議產出**

* docs/06\_test\_plan.md
* docs/07\_runbook.md

**Prompt**

Based on the implemented project, generate:

1. Test plan

2. Smoke test checklist

3. API validation checklist

4. Deployment verification steps

5. Troubleshooting guide

6. Docker container verification checklist

7. Gateway routing verification

8. Persistence / volume verification

9. Integration test: Backend API <-> Database (CRUD operations, connection pooling, schema validation)
10. Integration test: Frontend <-> Backend API (all API calls succeed, auth flow works, error handling correct)
11. Integration test: AI agent module <-> Backend (agent calls backend correctly, RAG retrieval returns expected results)
12. End-to-end test: run the main workflow from frontend to database and back
13. Dependency version conflict check: run pip check (must show No broken requirements) and npm audit (critical must equal 0)
14. Unit test coverage report: confirm coverage meets agreed threshold for backend and frontend

\*\*Explanation: **9.** Integration test：Backend ↔ Database **10.** Integration test：Frontend ↔ Backend API **11.** Integration test：AI agent ↔ Backend **12.** End-to-end test：主流程頭尾走一次 **13.** pip check（零衝突）+ npm audit（critical=0） **14.** Unit test coverage report 新增輸出：docs/08\_integration\_test\_report.md

Create:

docs/06\_test\_plan.md

docs/07\_runbook.md

docs/08\_integration\_test\_report.md

**Docker-wise 項目總表**

**建議新增的 Docker 交付物**

* + 1. frontend/Dockerfile
    2. backend/Dockerfile
    3. gateway/Dockerfile（如有 gateway）
    4. gateway/nginx.conf
    5. docker-compose.yml
    6. .env.example
    7. docs/05\_deployment\_plan.md
    8. docs/07\_runbook.md

**Revised Vibe Coding Flow in VS Code**

**Step 0**

Create .copilot-instructions.md first, so Copilot follows the same architecture rules, coding standards, and agent roles throughout the whole project.

**Step 1**

Prepare the User Requirement Document.

**Step 2**

Fill in the form VS Code Copilot 完整解決方案需求書模板.

**Step 3**

Ask AI to generate the following 4 core text files based on the completed template:

* 01\_project\_requirement.txt
* 02\_ai\_agent\_architecture.txt
* 03\_system\_architecture.txt
* 04\_deployment\_plan.txt

**Step 4**

Choose **Ask** mode in Copilot.
Provide 01\_project\_requirement.txt and ask Copilot to analyze:

* business goal
* functional modules
* non-functional requirements
* data requirements
* AI capabilities
* risks / assumptions / dependencies

Create:

* docs/01\_requirement\_analysis.md

**Step 5**

Choose **Plan** mode in Copilot.
Provide:

* 02\_ai\_agent\_architecture.txt
* docs/01\_requirement\_analysis.md

Ask Copilot to design:

* agent roles
* agent workflow
* RAG pipeline
* memory design
* tools per agent
* API interaction
* validation / fallback logic

Create:

* docs/02\_agent\_design.md

**Step 6**

Choose Plan mode in Copilot.
Provide:
• docs/01\_requirement\_analysis.md
• docs/02\_agent\_design.md

Ask Copilot to define:
• agent responsibility
• skills owned by each agent
• skills callable by each agent
• tools used by each skill
• input / output of each skill
• validation / fallback
• handoff to next agent

Create:
• docs/02b\_agent\_skill\_matrix.md

**Step 7**

Choose **Plan** mode in Copilot.
Provide:

* 03\_system\_architecture.txt
* docs/01\_requirement\_analysis.md
* docs/02\_agent\_design.md
* docs/02b\_agent\_skill\_matrix.md

Ask Copilot to design:

* folder structure
* frontend architecture
* backend services
* API gateway
* database schema
* RAG infrastructure
* AI integration
* ports
* auth
* logging and monitoring

Create:

* docs/03\_system\_architecture.md

**Step 8**

Choose **Ask** or **Plan** mode to review and freeze the architecture.

Create:

* docs/04\_architecture\_freeze.md

**Step 9**

Choose **Agent** mode in Copilot.
Use:

* docs/02b\_agent\_skill\_matrix.md
* docs/03\_system\_architecture.md
* docs/04\_architecture\_freeze.md

Ask Copilot to build the project step by step.

**Step 10**

Choose **Ask** mode in Copilot.
Provide:

* 04\_deployment\_plan.txt
* docs/03\_system\_architecture.md

Create:

* docs/05\_deployment\_plan.md

**Step 11**

Choose **Agent** mode in Copilot to generate deployment files:

* docker-compose.yml
* .env.example
* startup scripts
* health checks

**Step 12**

Generate:

* docs/06\_test\_plan.md
* docs/07\_runbook.md

**Remarks:**

* **Skill can be found in Github:**

[github/awesome-copilot: Community-contributed instructions, prompts, and configurations to help you make the most of GitHub Copilot.](https://github.com/github/awesome-copilot/tree/main)

![placeholder](./Readme  (Very important)_images\image_001.png)