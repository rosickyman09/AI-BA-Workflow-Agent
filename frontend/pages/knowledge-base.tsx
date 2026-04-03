import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Layout from '@/components/Layout'
import { ProgressBar } from '@/components/ProgressBar'
import { getCurrentUser } from '@/services/auth'
import { listProjects, type ProjectItem } from '@/services/projects'
import { listDocuments, type DocumentListItem } from '@/services/documents'
import {
  addDocumentsToRag,
  getRagDocuments,
} from '@/services/rag'
import 'bootstrap/dist/css/bootstrap.min.css'

type AgentKey = 'security' | 'retrieval' | 'reasoning' | 'validation'
type AgentState = 'idle' | 'active' | 'completed' | 'error'

interface PipelineAgent {
  key: AgentKey
  role: string
  subtitle: string
  icon: string
  activeText: string
  doneText: string
}

interface SearchJob {
  search_id: string
  status: 'processing' | 'completed' | 'error'
  stage_statuses: Record<AgentKey, 'idle' | 'working' | 'done' | 'error'>
  question: string
  answer: string | null
  sources: Array<{ doc_id: string; title: string; chunks_used: number }>
  confidence: 'high' | 'low' | null
  processing_time_ms: number | null
  error_message: string | null
}

interface ToastState {
  kind: 'success' | 'danger' | 'info'
  text: string
}

const PIPELINE_AGENTS: PipelineAgent[] = [
  { key: 'security',   role: 'Security',   subtitle: 'Gatekeeper', icon: '🔐', activeText: 'Verifying document access...', doneText: 'Access verified ✓' },
  { key: 'retrieval',  role: 'Retrieval',  subtitle: 'Librarian',  icon: '🗂️', activeText: 'Embedding into vector store...', doneText: 'Documents indexed ✓' },
  { key: 'reasoning',  role: 'Reasoning',  subtitle: 'Analyst',   icon: '🧠', activeText: 'Analysing against documents...', doneText: 'Analysis complete ✓' },
  { key: 'validation', role: 'Validation', subtitle: 'Editor',    icon: '✅', activeText: 'Validating answer...', doneText: 'Answer validated ✓' },
]

function stageToAgentState(s: 'idle' | 'working' | 'done' | 'error'): AgentState {
  if (s === 'working') return 'active'
  if (s === 'done') return 'completed'
  if (s === 'error') return 'error'
  return 'idle'
}

const INITIAL_PIPELINE: Record<AgentKey, AgentState> = {
  security: 'idle',
  retrieval: 'idle',
  reasoning: 'idle',
  validation: 'idle',
}

const STAGE_ORDER: AgentKey[] = ['security', 'retrieval', 'reasoning', 'validation']
const STAGE_PROGRESS: Record<AgentKey, { pct: number; label: string }> = {
  security:   { pct: 25,  label: 'Verifying document access...' },
  retrieval:  { pct: 50,  label: 'Embedding into vector store...' },
  reasoning:  { pct: 75,  label: 'Analysing with AI...' },
  validation: { pct: 100, label: 'Validating answer...' },
}

function normalizeUTC(iso?: string | null): string | null {
  if (!iso) return null
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

function formatDate(iso?: string | null): string {
  const value = normalizeUTC(iso)
  if (!value) return 'N/A'
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'Asia/Hong_Kong',
  })
}

function getFileTypeLabel(doc: DocumentListItem): string {
  const rawType = (doc.doc_type || '').toLowerCase()
  const title = doc.title || ''
  const ext = title.includes('.') ? title.split('.').pop()?.toLowerCase() || '' : ''
  const token = rawType || ext

  if (token.includes('pdf') || ext === 'pdf') return 'PDF'
  if (token.includes('docx') || token.includes('word') || ext === 'docx' || ext === 'doc') return 'DOC'
  if (token.includes('sheet') || token.includes('xlsx') || ext === 'xlsx' || ext === 'xls') return 'XLS'
  if (token.includes('ppt') || ext === 'ppt' || ext === 'pptx') return 'PPT'
  if (token.includes('text') || ext === 'txt') return 'TXT'
  return 'FILE'
}

function buildToastClass(kind: ToastState['kind']): string {
  if (kind === 'success') return 'alert alert-success'
  if (kind === 'danger') return 'alert alert-danger'
  return 'alert alert-info'
}

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState('')
  const [projectId, setProjectId] = useState('')
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [approvedDocs, setApprovedDocs] = useState<DocumentListItem[]>([])
  const [ragDocIds, setRagDocIds] = useState<string[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const selectedDocIdsRef = useRef<string[]>([])
  const [loading, setLoading] = useState(false)
  const [addingToRag, setAddingToRag] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [showLeftPanel, setShowLeftPanel] = useState(true)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [pipelineStates, setPipelineStates] = useState<Record<AgentKey, AgentState>>(INITIAL_PIPELINE)
  const [pipelineMessage, setPipelineMessage] = useState('')
  const [searchJob, setSearchJob] = useState<SearchJob | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchHistory, setSearchHistory] = useState<SearchJob[]>([])
  const [llmProvider, setLlmProvider] = useState('auto')
  const [searchProgress, setSearchProgress] = useState(0)
  const [progressStage, setProgressStage] = useState('')
  const [startTime, setStartTime] = useState<number | null>(null)

  const selectedCount = selectedDocIds.length

  const sortedDocs = useMemo(() => {
    return [...approvedDocs]
      .filter((doc) => (doc as any).is_active !== false)
      .sort((a, b) => {
      const aTime = normalizeUTC(a.updated_at) || ''
      const bTime = normalizeUTC(b.updated_at) || ''
      return bTime.localeCompare(aTime)
    })
  }, [approvedDocs])

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }

      try {
        const items = await listProjects()
        const activeProjects = items.filter((project) => {
          const normalizedStatus = (project.status || '').trim().toLowerCase()
          return normalizedStatus === 'active' && !project.is_frozen
        })
        setProjects(activeProjects)
        setProjectId(activeProjects[0]?.project_id || '')
      } catch {
        setProjects([])
        setProjectId('')
      }
    }

    void bootstrap()
  }, [])

  useEffect(() => {
    const syncViewport = () => {
      const small = window.innerWidth < 992
      setIsMobile(small)
      setShowLeftPanel(!small)
    }

    syncViewport()
    window.addEventListener('resize', syncViewport)
    return () => {
      window.removeEventListener('resize', syncViewport)
    }
  }, [])

  useEffect(() => {
    if (!projectId) {
      setApprovedDocs([])
      setRagDocIds([])
      setSelectedDocIds([])
      return
    }

    const loadProjectDocuments = async () => {
      try {
        const [docs, rag] = await Promise.all([
          listDocuments(projectId, 'approved'),
          getRagDocuments(projectId),
        ])

        setApprovedDocs(docs)
        setRagDocIds(rag.doc_ids || [])
      } catch {
        setApprovedDocs([])
        setRagDocIds([])
      } finally {
        setSelectedDocIds([])
      }
    }

    void loadProjectDocuments()
  }, [projectId])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 6000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [toast])

  const handleSearch = useCallback(async (event?: React.FormEvent) => {
    if (event) event.preventDefault()
    const currentDocIds = selectedDocIdsRef.current
    if (!query.trim()) {
      return
    }

    if (currentDocIds.length === 0) {
      setToast({ kind: 'info', text: 'Please select at least one document before searching' })
      return
    }

    if (!projectId || loading) {
      return
    }

    setLoading(true)
    setHasSearched(true)
    setSearchJob(null)
    setSearchError(null)
    setPipelineStates(INITIAL_PIPELINE)
    setPipelineMessage('')
    setSearchProgress(0)
    setProgressStage('Initialising search...')
    setStartTime(Date.now())

    let searchId: string
    try {
      const resp = await fetch('/api/knowledge-base/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: query.trim(),
          doc_ids: currentDocIds,
          project_id: projectId,
          llm_provider: llmProvider,
        }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.message || `Search request failed (${resp.status})`)
      }
      const data = await resp.json()
      searchId = data.search_id
    } catch (err: any) {
      setSearchError(err.message || 'Search failed. Please try again.')
      setLoading(false)
      return
    }

    // Polling
    const POLL_INTERVAL = 1500
    const TIMEOUT_MS = 60000
    const startedAt = Date.now()

    const intervalId = window.setInterval(async () => {
      if (Date.now() - startedAt > TIMEOUT_MS) {
        window.clearInterval(intervalId)
        setLoading(false)
        setSearchError('Search timed out. Please try again.')
        setPipelineStates(INITIAL_PIPELINE)
        return
      }

      try {
        const resp = await fetch(`/api/knowledge-base/search/${searchId}`)
        if (resp.status === 404) {
          window.clearInterval(intervalId)
          setLoading(false)
          setSearchError('Search job not found. Please try again.')
          return
        }
        if (!resp.ok) return

        const job: SearchJob = await resp.json()
        setSearchJob(job)

        // Update agent display from stage_statuses
        const newStates: Record<AgentKey, AgentState> = {
          security:   stageToAgentState(job.stage_statuses.security),
          retrieval:  stageToAgentState(job.stage_statuses.retrieval),
          reasoning:  stageToAgentState(job.stage_statuses.reasoning),
          validation: stageToAgentState(job.stage_statuses.validation),
        }
        setPipelineStates(newStates)

        // Advance progress bar based on completed stages
        let highestPct = 0
        let latestLabel = ''
        for (const key of STAGE_ORDER) {
          if (job.stage_statuses[key] === 'done') {
            highestPct = STAGE_PROGRESS[key].pct
            latestLabel = STAGE_PROGRESS[key].label
          }
        }
        if (highestPct > 0) {
          setSearchProgress(highestPct)
          setProgressStage(latestLabel)
        }

        if (job.status === 'completed' || job.status === 'error') {
          window.clearInterval(intervalId)
          setLoading(false)
          if (job.status === 'error') {
            setSearchError(job.error_message || 'Search failed.')
            setSearchProgress(0)
            setProgressStage('')
          }
          if (job.status === 'completed') {
            setSearchProgress(100)
            setProgressStage('Complete!')
            window.setTimeout(() => {
              setSearchProgress(0)
              setProgressStage('')
            }, 800)
          }
          if (job.status === 'completed' && job.answer) {
            setSearchHistory((prev) => [job, ...prev].slice(0, 5))
          }
        }
      } catch {
        // network hiccup — keep polling
      }
    }, POLL_INTERVAL)
  }, [query, projectId, loading, llmProvider, setToast, setLoading, setHasSearched, setSearchJob, setSearchError, setPipelineStates, setPipelineMessage, setSearchProgress, setProgressStage, setStartTime])

  const handleAddToRag = async () => {
    if (selectedDocIds.length === 0 || addingToRag) return

    setAddingToRag(true)
    const docIds = selectedDocIds

    try {
      const response = await addDocumentsToRag(docIds)
      const addedIds = response.doc_ids || []

      setRagDocIds((prev) => [...prev, ...addedIds.filter((id) => !prev.includes(id))])

      setSelectedDocIds([])
      if (response.added_count > 0) {
        setToast({
          kind: 'success',
          text: `${response.added_count} document(s) added to RAG`,
        })
      } else {
        setToast({
          kind: 'info',
          text: 'Documents already in RAG or no valid documents selected',
        })
      }
    } catch {
      setToast({ kind: 'danger', text: 'Failed to add selected documents to RAG' })
    } finally {
      setAddingToRag(false)
    }
  }

  return (
    <Layout>
      <div className="kb-page">
        {toast && (
          <div className="kb-toast-wrap">
            <div className={`${buildToastClass(toast.kind)} kb-toast`}>{toast.text}</div>
          </div>
        )}

        {isMobile && (
          <div className="kb-mobile-bar">
            <button
              type="button"
              className="btn btn-outline-primary btn-sm"
              onClick={() => setShowLeftPanel((prev) => !prev)}
            >
              {showLeftPanel ? 'Hide Documents' : 'Show Documents'}
            </button>
          </div>
        )}

        <div className="kb-grid">
          <aside className={`kb-panel kb-left ${showLeftPanel ? 'is-open' : 'is-closed'}`}>
            <div className="kb-section-title">Project</div>
            <select
              className="form-select kb-project-select"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={projects.length === 0}
            >
              {projects.length === 0 ? (
                <option value="">No active projects</option>
              ) : (
                projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))
              )}
            </select>

            <div className="kb-divider" />
            <div className="kb-section-title">Approved Documents</div>

            <div className="kb-doc-list">
              {sortedDocs.length === 0 ? (
                <div className="kb-doc-empty">No approved documents.</div>
              ) : (
                sortedDocs.map((doc) => {
                  const checked = selectedDocIds.includes(doc.doc_id)
                  const inRag = ragDocIds.includes(doc.doc_id)

                  return (
                    <label className="kb-doc-row" key={doc.doc_id}>
                      <input
                        type="checkbox"
                        className="form-check-input kb-check"
                        checked={checked}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => {
                          const id = doc.doc_id
                          setSelectedDocIds((prev) => {
                            const next = e.target.checked
                              ? [...prev, id]
                              : prev.filter((x) => x !== id)
                            selectedDocIdsRef.current = next
                            return next
                          })
                        }}
                      />

                      <div className="kb-file-icon">{getFileTypeLabel(doc)}</div>

                      <div className="kb-doc-content">
                        <div className="kb-doc-title" title={doc.title}>
                          {doc.title}
                        </div>
                        <div className="kb-doc-subtitle">Upload date: {formatDate(doc.updated_at)}</div>
                      </div>

                      <div className="kb-doc-badges">
                        {inRag && <span className="kb-rag-indicator" title="Already indexed">◆</span>}
                        <span className="kb-approved-badge">Approved</span>
                      </div>
                    </label>
                  )
                })
              )}
            </div>

            {selectedCount > 0 && (
              <div className="kb-floating-action">
                <span>{selectedCount} document(s) selected</span>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => void handleAddToRag()}
                  disabled={addingToRag}
                >
                  {addingToRag ? 'Adding...' : 'Add to RAG'}
                </button>
              </div>
            )}
          </aside>

          <section className="kb-panel kb-center">
            <h1 className="kb-title">Knowledge Base Search</h1>
            <form onSubmit={(event) => void handleSearch(event)} className="kb-search-form">
              <div className="input-group input-group-lg">
                <input
                  type="text"
                  className="form-control"
                  placeholder="Ask a question about your documents..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  disabled={!projectId}
                />
                <button
                  className="btn kb-search-btn"
                  type="button"
                  disabled={loading || !projectId}
                  onClick={() => void handleSearch()}
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>
              <div style={{ marginTop: 8 }}>
                <select
                  className="form-select form-select-sm kb-llm-select"
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                >
                  <optgroup label="Auto">
                    <option value="auto">LLM: Auto (DeepSeek → OpenRouter)</option>
                  </optgroup>
                  <optgroup label="DeepSeek">
                    <option value="deepseek">LLM: DeepSeek</option>
                  </optgroup>
                  <optgroup label="OpenRouter">
                    <option value="openrouter">LLM: OpenRouter (GPT-4o-mini)</option>
                    <option value="gemini-2.5-pro">LLM: Gemini 2.5 Pro (OpenRouter)</option>
                    <option value="minimax-m2.5">LLM: MiniMax M2.5 (OpenRouter)</option>
                    <option value="claude-haiku-4-5">LLM: Claude Haiku 4.5 (OpenRouter)</option>
                  </optgroup>
                </select>
              </div>
            </form>

            <ProgressBar
              show={loading}
              progress={searchProgress}
              stage={progressStage}
              title="Processing your search..."
              startTime={startTime ?? undefined}
            />

            {/* Loading skeleton — shown only before first stage completes */}
            {loading && searchProgress === 0 && (
              <div className="kb-skeleton-wrap">
                <div className="kb-skeleton-line" style={{ width: '90%' }} />
                <div className="kb-skeleton-line" style={{ width: '75%' }} />
                <div className="kb-skeleton-line" style={{ width: '60%' }} />
              </div>
            )}

            {/* Error state */}
            {!loading && searchError && (
              <div className="kb-answer-card kb-answer-error">
                <div className="kb-answer-icon">⚠</div>
                <div className="kb-answer-body">{searchError}</div>
              </div>
            )}

            {/* No answer fallback */}
            {!loading && !searchError && searchJob?.status === 'completed' && !searchJob.answer && (
              <div className="kb-answer-card">
                <div className="kb-answer-body" style={{ color: '#5a7a8a', fontStyle: 'italic' }}>
                  The search completed but no relevant information was found in the selected documents.
                </div>
              </div>
            )}

            {/* Answer card */}
            {!loading && !searchError && searchJob?.status === 'completed' && searchJob.answer && (
              <div className="kb-answer-card">
                <div className="kb-answer-question">🔍 &ldquo;{searchJob.question}&rdquo;</div>
                <hr className="kb-answer-divider" />
                <div className="kb-answer-body">{searchJob.answer}</div>
                {searchJob.sources.length > 0 && (
                  <>
                    <hr className="kb-answer-divider" />
                    <div className="kb-answer-sources-label">Sources:</div>
                    <div className="kb-answer-sources">
                      {searchJob.sources.map((src) => (
                        <span key={src.doc_id} className="kb-source-pill" title={`${src.chunks_used} chunk(s) used`}>
                          {src.title}
                        </span>
                      ))}
                    </div>
                  </>
                )}
                <div className="kb-answer-footer">
                  <span className={`kb-confidence-dot ${searchJob.confidence === 'high' ? 'high' : 'low'}`} />
                  <span className="kb-confidence-label">
                    Confidence: {searchJob.confidence === 'high' ? 'High' : 'Low'}
                  </span>
                  {searchJob.processing_time_ms != null && (
                    <span className="kb-proc-time">{(searchJob.processing_time_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
              </div>
            )}

            {/* Previous Q&A history (last 5) */}
            {searchHistory.length > 0 && !(loading && !searchJob) && (
              <div className="kb-history-section">
                {searchHistory
                  .filter((h) => h.search_id !== searchJob?.search_id)
                  .map((job) => (
                    <div className="kb-answer-card kb-history-card" key={job.search_id}>
                      <div className="kb-answer-question">🔍 &ldquo;{job.question}&rdquo;</div>
                      <hr className="kb-answer-divider" />
                      <div className="kb-answer-body">{job.answer}</div>
                      {job.sources.length > 0 && (
                        <>
                          <hr className="kb-answer-divider" />
                          <div className="kb-answer-sources">
                            {job.sources.map((src) => (
                              <span key={src.doc_id} className="kb-source-pill" title={`${src.chunks_used} chunk(s) used`}>
                                {src.title}
                              </span>
                            ))}
                          </div>
                        </>
                      )}
                      <div className="kb-answer-footer">
                        <span className={`kb-confidence-dot ${job.confidence === 'high' ? 'high' : 'low'}`} />
                        <span className="kb-confidence-label">
                          {job.confidence === 'high' ? 'High' : 'Low'}
                        </span>
                        {job.processing_time_ms != null && (
                          <span className="kb-proc-time">{(job.processing_time_ms / 1000).toFixed(1)}s</span>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            )}

            {/* Empty state */}
            {!hasSearched && !loading && (
              <div className="kb-empty-state">
                <div className="kb-empty-icon">🔍</div>
                <div className="kb-empty-text">
                  Select documents from the left panel and ask a question to search the knowledge base
                </div>
              </div>
            )}
          </section>

          <aside className="kb-panel kb-right">
            <div className="kb-pipeline-header">⚙ AGENT PIPELINE</div>

            <div className="kb-pipeline-list">
              {PIPELINE_AGENTS.map((agent, index) => {
                const state = pipelineStates[agent.key]
                const isActive = state === 'active'
                const isCompleted = state === 'completed'
                const isError = state === 'error'

                return (
                  <div className="kb-pipeline-item" key={agent.key}>
                    <div className="kb-node-wrap">
                      <div className={`kb-node ${state}`}>
                        {isCompleted ? '✓' : isError ? '✗' : agent.icon}
                      </div>
                      {index < PIPELINE_AGENTS.length - 1 && <div className="kb-node-line" />}
                    </div>
                    <div className="kb-agent-copy">
                      <div className={`kb-agent-role ${isActive ? 'active' : ''} ${isError ? 'error' : ''}`}>{agent.role}</div>
                      <div className="kb-agent-subtitle">{agent.subtitle}</div>
                      {isActive && <div className="kb-agent-progress">{agent.activeText}</div>}
                      {isCompleted && agent.doneText && <div className="kb-agent-done">{agent.doneText}</div>}
                      {isError && <div className="kb-agent-error-text">Failed — see search result for details</div>}
                    </div>
                  </div>
                )
              })}
            </div>

            {pipelineMessage && <div className="kb-pipeline-message">{pipelineMessage}</div>}
          </aside>
        </div>
      </div>

      <style jsx>{`
        .kb-page {
          background: #e6f3f7;
          min-height: calc(100vh - 130px);
          padding: 16px;
        }

        .kb-mobile-bar {
          margin-bottom: 12px;
        }

        .kb-grid {
          display: grid;
          grid-template-columns: 300px minmax(0, 1fr) 220px;
          gap: 14px;
        }

        .kb-panel {
          background: #f0f8fb;
          border: 1px solid #c8e0ea;
          border-radius: 12px;
          padding: 14px;
          box-shadow: 0 2px 8px rgba(26, 74, 98, 0.08);
        }

        .kb-left {
          position: relative;
          min-height: 640px;
          display: flex;
          flex-direction: column;
        }

        .kb-section-title {
          font-size: 1.05rem;
          font-weight: 700;
          color: #1f2f36;
          margin-bottom: 8px;
        }

        .kb-project-select {
          background: #fff;
          border: 1px solid #cbd5e0;
          border-width: 1px;
          padding-right: 2rem;
          color: #1f2f36;
          font-weight: 500;
          cursor: pointer;
          transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
          appearance: none;
          -webkit-appearance: none;
          -moz-appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 20 20'%3E%3Cpath fill='%234a5568' d='M5.3 7.8a1 1 0 0 1 1.4 0L10 11.1l3.3-3.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 0-1.4z'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 0.62rem center;
          background-size: 14px 14px;
        }

        .kb-project-select:hover:not(:disabled) {
          border-color: #8fb7cb;
          background-color: #f8fcff;
        }

        .kb-project-select:focus {
          border-color: #1f87db;
          box-shadow: 0 0 0 0.2rem rgba(31, 135, 219, 0.2);
        }

        .kb-project-select:disabled {
          cursor: not-allowed;
          opacity: 0.78;
        }

        .kb-divider {
          border-top: 1px solid #d4e7ef;
          margin: 12px 0;
        }

        .kb-doc-list {
          overflow: auto;
          max-height: calc(100vh - 320px);
          padding-right: 2px;
          display: block;
        }

        .kb-doc-empty {
          color: #6c757d;
          font-size: 0.92rem;
          padding: 8px 0;
        }

        .kb-doc-row {
          display: grid;
          grid-template-columns: 18px 20px minmax(0, 1fr) auto;
          gap: 6px;
          align-items: center;
          background: transparent;
          border-bottom: 1px solid #d9e8ef;
          border-radius: 0;
          padding: 8px 6px;
          margin-bottom: 0;
          cursor: pointer;
          width: 100%;
          overflow: hidden;
        }

        .kb-doc-row:hover {
          background: #d1eaf4;
        }

        .kb-check {
          appearance: none;
          -webkit-appearance: none;
          width: 16px;
          height: 16px;
          min-width: 16px;
          min-height: 16px;
          margin-top: 1px;
          flex-shrink: 0;
          cursor: pointer;
          border: 2px solid #365469;
          border-radius: 4px;
          background-color: #ffffff;
          background-position: center;
          background-repeat: no-repeat;
          background-size: 11px 11px;
          transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
        }

        .kb-check:hover {
          border-color: #1f6aa5;
          box-shadow: 0 0 0 2px rgba(31, 106, 165, 0.12);
        }

        .kb-check:focus-visible {
          outline: none;
          box-shadow: 0 0 0 3px rgba(31, 135, 219, 0.28);
        }

        .kb-check:checked {
          border-color: #1f87db;
          background-color: #1f87db;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='white' stroke-linecap='round' stroke-linejoin='round' stroke-width='2.1' d='M3 8.5l3.1 3.1L13 4.7'/%3E%3C/svg%3E");
        }

        .kb-check:checked:hover {
          border-color: #196ea9;
          background-color: #196ea9;
        }

        .kb-file-icon {
          width: 20px;
          height: 20px;
          border-radius: 5px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.53rem;
          font-weight: 700;
          color: #1f6aa5;
          background: #e6f1fb;
          border: 1px solid #c3ddf5;
        }

        .kb-doc-content {
          min-width: 0;
          overflow: hidden;
          width: 100%;
        }

        .kb-doc-title {
          font-size: 0.88rem;
          font-weight: 500;
          color: #1f2f36;
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          line-height: 1.2;
          word-break: break-word;
          overflow-wrap: anywhere;
        }

        .kb-doc-subtitle {
          font-size: 12px;
          color: #6b7280;
          margin-top: 2px;
          line-height: 1.25;
        }

        .kb-doc-badges {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-left: 6px;
        }

        .kb-approved-badge {
          background: #4caf50;
          color: #fff;
          font-size: 0.64rem;
          font-weight: 700;
          border-radius: 999px;
          padding: 2px 6px;
          white-space: nowrap;
        }

        .kb-rag-indicator {
          color: #2196f3;
          font-size: 0.8rem;
          font-weight: 700;
        }

        .kb-floating-action {
          position: sticky;
          bottom: 0;
          margin-top: auto;
          background: rgba(15, 41, 54, 0.92);
          color: #fff;
          border-radius: 10px;
          padding: 10px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          z-index: 5;
        }

        .kb-center {
          background: #edf7fb;
          min-height: 640px;
        }

        .kb-title {
          margin: 4px 0 14px;
          font-size: 2.1rem;
          font-weight: 700;
          color: #1e2930;
        }

        .kb-search-form {
          margin-bottom: 14px;
        }

        .kb-search-btn {
          background: #2196f3;
          color: #fff;
          border: 1px solid #2196f3;
          min-width: 120px;
          font-weight: 600;
        }

        .kb-search-btn:hover,
        .kb-search-btn:focus {
          background: #1f87db;
          color: #fff;
          border-color: #1f87db;
        }

        .kb-empty-canvas {
          background: rgba(255, 255, 255, 0.5);
          border: 1px dashed #b7d3e2;
          border-radius: 10px;
          min-height: 460px;
        }

        .kb-no-results {
          color: #5d6d75;
          font-size: 0.95rem;
          background: rgba(255, 255, 255, 0.75);
          border: 1px solid #cae1ec;
          border-radius: 10px;
          padding: 12px;
        }

        .kb-results {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .kb-result-card {
          background: #fff;
          border: 1px solid #cadeea;
          border-radius: 10px;
          padding: 12px;
        }

        .kb-result-text {
          color: #1f2f36;
          font-size: 0.95rem;
          line-height: 1.45;
        }

        .kb-result-meta {
          margin-top: 8px;
          font-size: 0.8rem;
          color: #587280;
          display: flex;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
        }

        .kb-score {
          font-weight: 600;
        }

        .kb-right {
          min-height: 640px;
        }

        .kb-pipeline-header {
          font-size: 1.03rem;
          font-weight: 700;
          color: #29424f;
          margin-bottom: 12px;
        }

        .kb-pipeline-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .kb-pipeline-item {
          display: flex;
          flex-direction: row;
          align-items: flex-start;
          gap: 10px;
          min-width: 0;
        }

        .kb-agent-copy {
          flex: 1;
          min-width: 0;
          overflow: visible;
          display: flex;
          flex-direction: column;
        }

        .kb-node-wrap {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          flex-shrink: 0;
          width: 28px;
        }

        .kb-node {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.77rem;
          font-weight: 700;
          color: #1e4860;
          border: 2px solid #96c5da;
          background: #b8d9e8;
          transition: all 0.25s ease;
        }

        .kb-node-line {
          width: 2px;
          height: 38px;
          background: #a9ccdc;
          margin-top: 4px;
        }

        .kb-node.active {
          color: #fff;
          background: #2196f3;
          border-color: #2196f3;
          box-shadow: 0 0 0 0 rgba(33, 150, 243, 0.6);
          animation: kbPulse 1.2s infinite;
        }

        .kb-node.completed {
          color: #fff;
          background: #4caf50;
          border-color: #4caf50;
          animation: none;
        }

        .kb-agent-role {
          display: block;
          font-size: 1.02rem;
          font-weight: 700;
          color: #556a75;
          line-height: 1.2;
          white-space: nowrap;
          overflow: visible;
        }

        .kb-agent-role.active {
          color: #1e5170;
        }

        .kb-agent-role.error {
          color: #c0392b;
        }

        .kb-agent-subtitle {
          display: block;
          color: #6f7f87;
          font-size: 0.84rem;
          white-space: nowrap;
          overflow: visible;
        }

        .kb-agent-progress {
          margin-top: 3px;
          font-size: 0.78rem;
          color: #1f6aa5;
        }

        .kb-agent-done {
          margin-top: 3px;
          font-size: 0.78rem;
          color: #27ae60;
        }

        .kb-agent-error-text {
          margin-top: 3px;
          font-size: 0.78rem;
          color: #c0392b;
        }

        .kb-node.error {
          background: #fdecea;
          color: #c0392b;
          border-color: #e74c3c;
        }

        /* Answer card */
        .kb-answer-card {
          margin-top: 18px;
          padding: 18px 20px;
          background: #ffffff;
          border: 1px solid #b8d9e8;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(26, 74, 98, 0.1);
        }

        .kb-answer-card.kb-answer-error {
          border-color: #e74c3c;
          background: #fff9f9;
        }

        .kb-answer-error .kb-answer-icon {
          font-size: 1.5rem;
          color: #c0392b;
          margin-bottom: 8px;
        }

        .kb-answer-question {
          font-size: 0.9rem;
          color: #5a7a8a;
          font-style: italic;
          margin-bottom: 4px;
        }

        .kb-answer-divider {
          border-color: #d0e8f0;
          margin: 10px 0;
        }

        .kb-answer-body {
          font-size: 0.96rem;
          color: #1a3a4e;
          line-height: 1.6;
          white-space: pre-wrap;
        }

        .kb-answer-sources-label {
          font-size: 0.78rem;
          color: #5a7a8a;
          margin-bottom: 6px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .kb-answer-sources {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .kb-source-pill {
          display: inline-block;
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          background: #dceef5;
          color: #1a4a62;
          border-radius: 20px;
          padding: 2px 10px;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: default;
        }

        .kb-answer-footer {
          margin-top: 10px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.8rem;
          color: #6f7f87;
        }

        .kb-confidence-dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        .kb-confidence-dot.high { background: #27ae60; }
        .kb-confidence-dot.low  { background: #e67e22; }

        .kb-confidence-label { color: #4a6a7a; }

        .kb-proc-time {
          margin-left: auto;
          font-size: 0.76rem;
          color: #8a9fa8;
        }

        /* Skeleton */
        .kb-skeleton-wrap {
          margin-top: 24px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .kb-skeleton-line {
          height: 16px;
          border-radius: 8px;
          background: linear-gradient(90deg, #d0e8f0 25%, #e8f4f8 50%, #d0e8f0 75%);
          background-size: 200% 100%;
          animation: kb-shimmer 1.4s infinite;
        }

        @keyframes kb-shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        /* Empty state */
        .kb-empty-state {
          margin-top: 60px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 14px;
        }

        .kb-empty-icon {
          font-size: 3rem;
          opacity: 0.45;
        }

        .kb-empty-text {
          max-width: 360px;
          color: #7a9aaa;
          font-size: 0.95rem;
          line-height: 1.5;
        }

        .kb-pipeline-message {
          margin-top: 10px;
          font-size: 0.82rem;
          color: #2b5d7a;
          font-weight: 600;
        }

        .kb-llm-select {
          width: auto;
          display: inline-block;
          font-size: 0.82rem;
          border: 1px solid #cbd5e0;
          border-radius: 6px;
          color: #4a5568;
        }

        .kb-history-section {
          margin-top: 12px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .kb-history-card {
          opacity: 0.75;
          border-color: #d0e0ea;
        }

        .kb-history-card:hover {
          opacity: 1;
        }

        .kb-toast-wrap {
          position: fixed;
          top: 84px;
          right: 20px;
          z-index: 1200;
          width: min(360px, 92vw);
        }

        .kb-toast {
          margin-bottom: 0;
          box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
        }

        @keyframes kbPulse {
          0% {
            box-shadow: 0 0 0 0 rgba(33, 150, 243, 0.52);
          }
          70% {
            box-shadow: 0 0 0 10px rgba(33, 150, 243, 0);
          }
          100% {
            box-shadow: 0 0 0 0 rgba(33, 150, 243, 0);
          }
        }

        @media (max-width: 1200px) {
          .kb-grid {
            grid-template-columns: 300px minmax(0, 1fr);
          }

          .kb-right {
            display: none;
          }
        }

        @media (max-width: 991px) {
          .kb-grid {
            grid-template-columns: 1fr;
          }

          .kb-left.is-closed {
            display: none;
          }

          .kb-left,
          .kb-center {
            min-height: auto;
          }

          .kb-doc-list {
            max-height: 360px;
          }

          .kb-title {
            font-size: 1.8rem;
          }

          .kb-empty-canvas {
            min-height: 280px;
          }
        }
      `}</style>
    </Layout>
  )
}
