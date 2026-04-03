**VS Code Copilot 完整解決方案需求書模板**

使用方法：將整份填好的需求書，直接貼入 VS Code Copilot Chat 作為 Prompt 。

**開場指令**

（請保留呢句，貼入Copilot時放喺最前面）

請根據以下需求書，幫我規劃整個解決方案嘅架構，包括資料夾結構、技術選型、Port分配，並逐步指引我建立呢個系統 。如有任何我未填寫或「唔知」嘅部分，請根據我嘅需求自動建議最適合嘅方案 。

**1. 項目概覽**

| **項目** | **你的答案** |
| --- | --- |
| 項目名稱 | AI 智能業務助理（AI BA Agent） |
| 項目目的 | 將會議錄音、電郵、文件自動轉化為結構化會議紀錄、業務需求（BRD/URS）、合約及條款初稿，並支援版本控制、審批流程及可搜尋知識庫（RAG），以減少 BA 整理文件及跟進溝通時間。 |
| 目標用戶 | Business Analyst / IT BA、Project Manager / Scrum Master、Technical Lead / Architect、Business Owner / Stakeholder、Compliance / Legal、IT 同事 |
| 使用平台 | 網頁（Web）/ Telegram Bot（Chatbot 查詢） |
| 預計用戶數量 | 公司內部團隊使用（BA、PM、Tech Lead、Business Owner、Legal 等） |

**2. 技術環境**

提示：唔識可以填「唔知，請建議」 。

| **項目** | **你的答案** |
| --- | --- |
| 程式語言偏好 | Python（後端 AI 邏輯）/ JavaScript（前端）；n8n 作 Workflow 編排（無代碼）；ElevenLabs Scribe v2 作 STT |
| 前端框架 | 唔知，請建議最適合；Chat UI 最簡單可用 Telegram Bot / Webhook chat |
| 後端需求 | 需要；後端服務處理 STT（ElevenLabs Scribe v2）、LLM 調用、RAG 向量庫及文件生成邏輯 |
| 資料庫 | 需要儲存資料；向量庫：Qdrant / pgvector（RAG，以 Project 為單位）；文件追蹤：Excel / Google Sheets |
| 部署平台 | 唔知，請建議最適合；文件儲存：Google Drive / SharePoint / S3 |

**2b. 前端介面類型**

新增項目 #1 — 決定你嘅系統用咩介面呈現 。

**介面類型選擇：**

- [] Web（網頁） — 用瀏覽器打開，最通用
- [ ] App（手機應用） — 裝落手機，iOS / Android
- [✓] Web App（網頁應用） — 可以裝落手機主頁，兼具兩者優點
- [ ]唔知，請建議

**前端UI框架：**

- [✓] Bootstrap — 簡單易用，適合初學者，外觀整齊
- [✓] Tailwind CSS — 靈活度高，現代感強
- [ ] Material UI — Google風格設計
- [ ]唔知，請建議最適合

**2c. 系統架構要求**

提示：唔識可以全部填「唔知，請建議」 。

**項目規模預計：**

- [ ] 小型（個人用、簡單工具）
- [✓] 中型（公司內部系統、有登入功能）
- [ ] 大型（多用戶、對外服務、高流量）
- [ ] 唔知，請建議

**需要前後端分離嗎？**

- [✓] 係
- [ ] 否
- [ ] 唔知，請建議

**架構組件需求：**

| **組件** | **需要嗎？** | **放喺獨立資料夾？** |
| --- | --- | --- |
| Frontend（前端介面 — 用戶見到嘅畫面） | 係 | 係 |
| Backend（後端服務 — 幕後處理邏輯） | 係 | 係 |
| API Gateway（前後端之間嘅傳話閘口） | 係 | 係 |
| Database（資料庫 — 儲存所有資料） | 係 | 係 |
| Auth Service（登入驗證服務） | 係 | 係 |

**其他要求：**

- Port 端口分配：[ ] 唔知 [✓] 我想指定：前端 / 後端 / 資料庫
- 資料夾結構：[✓] 唔知 [ ] 我有特別要求：\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
- 將來需要擴展嗎？ [✓] 係 [ ] 否 [ ] 唔知

**2d. Integration / External Systems**

系統需要連接外部系統嗎？

[✓] Google Drive [ ] Notion [ ] Slack [✓] Email [ ] CRM [ ] Payment gateway [ ]

Other: SharePoint / S3 / Telegram / Excel / [✓] Google Sheets / [✓] ElevenLabs (Scribe v2 STT) [ ] 唔知，請建議

**3. 功能需求清單**

提示：唔需要技術詞彙，用日常語言描述即可 。

**主要功能（必須有）：**

# 1. 功能一：會議錄音、電郵及文件輸入（STT 語音轉文字使用 ElevenLabs Scribe v2；支援 Speaker Diarization 自動分辨講者、Keyterm Prompting 提升業務術語準確度、Webhook 回傳結果至 n8n）
# 2. 功能二：自動生成結構化會議紀錄、Action Items、業務需求（BRD/URS）草稿
# 3. 功能三：版本控制及審批流程（可配置），附完整 audit log
# 4. 功能四：RAG 知識庫（以 Project 為單位），支援 Chatbot 查詢及引用來源
# 5. 功能五：Backlog / 跟進管理（每日掃描狀態，Telegram 通知 owner；每週自動生成週報）
# 6. 功能六：Human-in-the-loop 確認機制（所有法律、金額及高風險內容必須人工批核）

**次要功能（有最好，冇都OK）：**

- 合約／條款審查及風險標記（第二期）
- 成本分析功能（第二期）
- 新增：所有 AI 輸出附原文證據引用；資料不足時自動生成「待確認問題清單」

**3b. Workflow / Sub-Workflow 設計**

**系統是否包含多個 Workflow？**

定義系統是否需要子流程 (Sub-Workflow)。
 這有助 IDE / AI 在設計系統架構時預留擴展能力。

- [ ] 單一流程（Simple Workflow）
- [✓] 多個子流程（Sub-Workflow）
- [ ] 唔知，請建議

**如果使用Sub-Workflow**  (**請簡單描述可能存在的子流程)**：

| **Sub-Workflow 名稱** | **功能描述** |
| --- | --- |
| Workflow A | 主流程：會議錄音（ElevenLabs Scribe v2 STT + Speaker Diarization + Keyterm Prompting）／電郵／文件輸入 → 清洗抽取 → 人工確認 → 寫入 RAG → 生成 BRD/URS → 審批 → 發佈 |
| Workflow B | 子流程 B：Email Human-in-loop 選擇入庫 — Gmail Trigger → 列出 thread → 寫入候選清單 → BA 勾選 Include=Yes → 入 RAG + 抽取 Requirement |
| Workflow C | 子流程 C：Backlog / 跟進 — Cron 每日掃 Sheet，status=Blocked/Overdue/Waiting approval → Telegram 通知 owner；每週自動生成週報 |
| Workflow D | 子流程 D：Contract/T&C 分析（第二期）— 上傳合約 → clause extraction → red flags → 建議修改 → HITL 法務審批 → 發佈版本 |

- 子流程是否需要獨立部署？ [ ] 是 [✓] 否 [ ] 唔知 ，請建議:\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
- Workflow Engine / Automation 工具：[✓] n8n [ ] Temporal [ ] Airflow [ ] LangGraph [ ] Custom [ ] 唔知 ，請建議:\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**4. 介面設計要求**

| **項目** | **你的答案** |
| --- | --- |
| 整體風格 | 簡潔專業 / 企業商務風 |
| 主要顏色 | 淺海洋藍包 + 白色 |
| 語言顯示 | 繁體中文+英文為主，有個制可以轉中英文（介面及文件輸出） |
| 特別版面要求 | 要有側邊欄選單（Project 切換）、文件版本比較畫面、審批狀態追蹤列表 |
| 需要響應式設計？  （手機都睇到）？ | 唔知，請建議最適合 |

**5. 數據與安全要求**

| **項目** | **你的答案** |
| --- | --- |
| 需要用戶登入功能？ | 係（需要登入，按 Project 分隔權限） |
| 有幾多種用戶權限？ | 管理員（Admin）、BA / PM / Tech Lead（普通用戶）、Business Owner / Legal（審批用戶）、IT 同事（只讀查詢） |
| 資料需要保密嗎？ | 有，涉及 PII、合約內容及業務需求（需遮罩、權限控制、保留政策） |
| 需要備份功能？ | 係 |
| 需要操作記錄（Log）？ | 係 （完整 audit log，包括審批人、時間、結果） |

**5b. AI 智能架構要求**

提示：如果唔需要 AI 功能，本章節可以跳過 。

**AI Orchestration（AI 協調方式）：**

- [ ] LangChain -最流行，功能豐富，適合大部分場景
- [ ] LlamaIndex -專門處理文件同知識庫搜尋
- [ ] AutoGen -適合多個AI Agent互相對話協作
- [✓] CrewAI -適合分工明確嘅多Agent團隊任務
- [ ] 唔知，請根據需求建議

**RAG Knowledge Source：**

- [✓] Files [✓] Database [ ] Website [✓] Google Drive [ ] Notion [ ] API

[ ] 唔知 ，請建議:\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**Scheduling / Cron Skill：**

定時執行任務：係（每日 Cron 掃 Backlog Sheet；每週自動生成週報）

**LLM 大型語言模型選擇：**

| **我的選擇** | **模型類型** | **費用** | **我的選擇** |
| --- | --- | --- | --- |
| OpenRouter | 可以一個接口用多款模型 | 收費，較靈活 | ✓ 選用 |
| DeepSeek | 中文能力強，性價比高 | 收費，較便宜 | ✓ 選用 |

**AI Agent 清單：**

| **Agent 名稱** | **功能說明** | **需要嗎？** |
| --- | --- | --- |
| Prompt Injection Agent | 防止惡意用戶透過輸入文字攻擊系統 | 係 |
| RAG Verification Agent | 確保 AI 回答嘅內容係基於你提供嘅知識庫，唔會亂講 | 係 |
| Data Extraction Agent | 自動從文件、網頁或郵件提取重要資訊 | 係 |
| Summarization Agent | 自動將長文件或對話濃縮成摘要 | 係 |
| Routing Agent | 判斷用戶問題應該交俾邊個Agent處理 | 係 |
| Memory Agent | 記住用戶嘅對話歷史，提供連貫回應 | 係 |
| Validation Agent | 檢查 AI 輸出嘅格式同內容係咪正確 | 係 |
| **其他自定義 Agent** | （請描述你需要嘅功能）\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ | 否 |

**5c. System Skills / Capability Requirements**

| **Skill 類型** | **功能說明** | **需要嗎？** |
| --- | --- | --- |
| Document Processing Skill | 處理 PDF / Word / Excel 文件 | 係 |
| OCR Skill | 從圖片或掃描文件提取文字 | 係 |
| Web Search Skill | 即時搜尋互聯網資訊 | 否 |
| Knowledge Base Search Skill | 從內部知識庫 / RAG 搜尋資料 | 係 |
| Data Analysis Skill | 數據分析與統計計算 | 否 |
| Summarization Skill | 將長文件或資料摘要 | 係 |
| Translation Skill | 多語言翻譯 | 係 |
| Email Automation Skill | 發送 / 接收 Email | 係 |
| File Management Skill | 管理、分類和儲存檔案 | 係 |
| External API Integration Skill | 連接第三方 API（包括 ElevenLabs Scribe v2 STT API、OpenRouter LLM API、Deepgram 備用 STT） | 係 |
| Notification Skill | 發送通知（Email / Telegram / Slack） | 係 |
| Workflow Decision Skill | 根據條件決定流程走向 | 係 |

**6. 雲端部署要求**

**雲端託管平台選擇：**

| **平台** | **特點** | **適合** | **費用** | **我的選擇** |
| --- | --- | --- | --- | --- |
| **Railway**  （推薦初學者） | 簡單易用，部署快，適合初學者 | 中小型項目 | 有免費額度 | ✓ 選用 |
| **Render** | 類似Railway，操作簡單 | 中小型項目 | 有免費額度 |  |
| **Vercel**  （純前端） | 專門做前端，速度快 | 純前端項目 | 有免費額度 |  |
| **AWS** | 功能最強大，可擴展性高 | 大型企業項目 | 按使用量收費 |  |
| **Azure** | Microsoft出品，與Office整合好 | 企業環境 | 按使用量收費 |  |
| **Google Cloud** | 與Google服務整合好 | 需要AI/ML功能 | 按使用量收費 |  |
| **本地伺服器** | 資料唔出外，完全控制 | 私隱要求高 | 需要自備硬件 |  |
| **唔知** | 請建議最適合方案 |  |  |  |

**強制部署次序：**

# 1. 第一步：Database（資料庫） ← 必須最先建立，其他服務依賴佢
# 2. 第二步：Backend（後端服務） ← 連接資料庫後才啟動
# 3. 第三步：Frontend（前端網頁）← 確認後端正常運作後才部署

**額外部署要求：**

- 每個步驟部署完成後，請先測試確認正常才進行下一步
- 需要提供每個步驟嘅驗證方法（即係點知道部署成功）
- 需要回滾方案（即係部署失敗時點還原）
- 唔知，請建議最佳部署流程

**6b. Docker / Container Deployment**

# 1. Container Deployment：[ ] 不使用 [ ] 使用 Docker [✓] 使用 Docker Compose [ ] 唔知
# 2. 本地開發環境：[ ] 不使用 [ ] 使用 Docker [✓] 使用 Docker Compose [ ] 唔知
# 3. 服務 Containerization：[✓] Frontend [✓] Backend API [✓] Database [✓]AI service
# 4. Gateway / Reverse Proxy：[✓] 需要 [ ] 不需要[] 唔知
# 5. Port Strategy：Multi-port

**6c. Dependency Version Management（依賴版本管理）**

提示：Library 版本唔 pin 實，係日後出問題嘅主因。請逐項確認。

# 1. Python 版本鎖定策略：[✓] 全部用 == pin 死（推薦） [ ] 用 >= （唔推薦） [ ] 唔知，請建議
# 2. Node.js 版本鎖定策略：[✓] 移除所有 ^ 同 ~（推薦） [ ] 保留 ^ / ~（唔推薦） [ ] 唔知，請建議
# 3. Docker base image 版本：[✓] Pin 指定版本（例：python:3.11-slim）（推薦） [ ] 用 latest（唔推薦） [ ] 唔知
# 4. Python 版本衝突檢查：[ ] 要求 Copilot 喺 build 後跑 pip check（零衝突先算完成） [ ] 唔需要 [✓] 唔知
# 5. Node security audit：[ ] 要求 Copilot 喺 build 後跑 npm audit（critical=0 先算完成） [ ] 唔需要 [✓] 唔知
# 6. 需要獨立 requirements 文件：[✓] 係（requirements.txt + requirements-dev.txt 分開） [ ] 唔需要 [ ] 唔知
# 7. 需要版本文件：[✓] 係，生成 docs/08\_dependency\_versions.md 記錄所有版本及原因 [ ] 唔需要 [ ] 唔知

**7. 參考資料**

- 需求畫布 (Canvas) 內容（見 Project\_1 Architecture Canvas 1 & Canvas 2 文件）
- 參考網站或App （類似 Notion 文件管理 + Jira 追蹤功能，簡化版）
- 技術限制：唔知，請建議最適合；文件儲存可選 Google Drive 或 SharePoint；需要 ElevenLabs API Key（Scribe v2 STT）
- 時間要求（MVP 第一階段優先；第二階段（合約/RAG Chatbot）後期再加）
- 其他特別要求（所有法律、金額及高風險內容必須加 Human-in-the-loop；token budget 及長度限制；以 Project 作檢索邊界）

**結尾指令**（請保留呢句，貼入Copilot時放喺最後面）

請根據以上所有需求：

# 1. 幫我總結並確認你理解嘅系統需求
# 2. 建議最適合嘅技術架構同資料夾結構
# 3. 列出建議嘅Port分配
# 4. 列出建議嘅 AI Agent 組合及理由
# 5. 確認雲端部署平台建議
# 6. 嚴格按照「資料庫 → 後端 → 前端」嘅次序制定部署計劃
# 7. 告訴我第一步應該點開始
# 8. 如有任何不清楚嘅地方，請向我提問
# 9. 如果我答唔知/請Copilot建議，記得提出嘅意見同建議都要問我。不可自己建議唔問我就做 。

溫馨提示：

- 凡係唔知點填嘅，直接寫「唔知，請建議最適合嘅方案」
- 你嘅工作係描述業務需要，技術架構交俾 Copilot 決定
- 填好後，將整份文件內容完整複製貼入 VS Code Copilot Chat 即可 。