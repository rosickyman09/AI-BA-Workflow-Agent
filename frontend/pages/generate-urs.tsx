import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { ProgressBar } from '@/components/ProgressBar'
import { getCurrentUser } from '@/services/auth'
import { CheckCircle, Trash2, Download, ExternalLink } from 'lucide-react'

interface TemplateItem {
  template_id: string
  name: string
  description?: string
  file_format: string
  detected_placeholders: string[]
  google_drive_link?: string | null
  created_at?: string | null
}

interface ProjectItem {
  project_id: string
  name: string
  status?: string
}

interface ApprovedDocItem {
  doc_id: string
  title: string
  doc_type?: string | null
  updated_at?: string | null
  is_active?: boolean | null
}

interface GeneratedDocResponse {
  generated_id: string
  content: string
  filename: string
  effective_format?: string
  status: string
  placeholder_summary?: {
    filled: string[]
    unfilled: string[]
    to_be_confirmed_count: number
  }
}

function normalizeUTC(iso: string): string {
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

function formatHKTime(iso?: string | null): string {
  if (!iso) return '-'
  return new Date(normalizeUTC(iso)).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Hong_Kong',
  })
}

function dateSuffixHK(): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Hong_Kong',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const year = parts.find((p) => p.type === 'year')?.value || '0000'
  const month = parts.find((p) => p.type === 'month')?.value || '01'
  const day = parts.find((p) => p.type === 'day')?.value || '01'
  return `${year}${month}${day}`
}

function getNextVersion(projectSlug: string, datestamp: string): number {
  const key = `urs_version_${projectSlug}_${datestamp}`
  const current = parseInt(localStorage.getItem(key) || '0', 10)
  const next = current + 1
  localStorage.setItem(key, String(next))
  return next
}

interface ToastInfo {
  message: string
  driveLink?: string | null
}

export default function GenerateUrsPage() {
  const router = useRouter()

  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [selectedTemplateData, setSelectedTemplateData] = useState<TemplateItem | null>(null)
  const [showUploadTemplate, setShowUploadTemplate] = useState(false)
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateDesc, setNewTemplateDesc] = useState('')
  const [templateFile, setTemplateFile] = useState<File | null>(null)
  const [uploadingTemplate, setUploadingTemplate] = useState(false)
  const [activeProjects, setActiveProjects] = useState<ProjectItem[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [approvedDocs, setApprovedDocs] = useState<ApprovedDocItem[]>([])
  const [selectedDocs, setSelectedDocs] = useState<string[]>([])
  const [generating, setGenerating] = useState(false)
  const [generatedDoc, setGeneratedDoc] = useState<GeneratedDocResponse | null>(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<ToastInfo | null>(null)
  const toastTimerRef = useRef<number | null>(null)
  const [loadingInitial, setLoadingInitial] = useState(true)
  const [error, setError] = useState('')
  const [allowed, setAllowed] = useState(false)
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [llmProvider, setLlmProvider] = useState('auto')
  const [outputFormat, setOutputFormat] = useState('docx')
  const [ursProgress, setUrsProgress] = useState(0)
  const [ursProgressStage, setUrsProgressStage] = useState('')
  const [ursStartTime, setUrsStartTime] = useState<number | null>(null)
  const ursTimersRef = useRef<number[]>([])
  const ursIntervalRef = useRef<number | null>(null)

  const showToast = useCallback((info: ToastInfo) => {
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current)
    setToast(info)
    toastTimerRef.current = window.setTimeout(() => setToast(null), 6000) as unknown as number
  }, [])

  const selectedProjectData = useMemo(
    () => activeProjects.find((project) => project.project_id === selectedProject) || null,
    [activeProjects, selectedProject]
  )
  const projectName = selectedProjectData?.name || 'Project'

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }

      const role = (user.role || '').trim().toLowerCase()
      const permitted = ['admin', 'ba', 'pm', 'business_owner'].includes(role)
      setAllowed(permitted)

      if (!permitted) {
        setLoadingInitial(false)
        return
      }

      try {
        const [templatesResponse, projectsResponse] = await Promise.all([
          fetch('/api/urs/templates'),
          fetch('/api/projects?status=active'),
        ])

        const templatesData = await templatesResponse.json()
        const projectsData = await projectsResponse.json()

        if (!templatesResponse.ok) {
          throw new Error(templatesData.message || 'Failed to load templates')
        }
        if (!projectsResponse.ok) {
          throw new Error(projectsData.message || 'Failed to load projects')
        }

        setTemplates((templatesData.templates || []) as TemplateItem[])
        const projects = (projectsData.items || projectsData.projects || []) as ProjectItem[]
        setActiveProjects(projects)
      } catch (err: any) {
        setError(err.message || 'Failed to initialize page')
      } finally {
        setLoadingInitial(false)
      }
    }

    void bootstrap()
  }, [router])

  useEffect(() => {
    const selected = templates.find((item) => item.template_id === selectedTemplate) || null
    setSelectedTemplateData(selected)
  }, [selectedTemplate, templates])

  const loadApprovedDocs = async (projectId: string) => {
    if (!projectId) {
      setApprovedDocs([])
      return
    }

    try {
      const response = await fetch(`/api/documents?project_id=${encodeURIComponent(projectId)}&status=approved`)
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || 'Failed to load approved documents')
      }
      setApprovedDocs((data.documents || []) as ApprovedDocItem[])
    } catch (err: any) {
      setError(err.message || 'Failed to load approved documents')
      setApprovedDocs([])
    }
  }

  const simulateProgress = () => {
    // Clear any running timers from a previous generation
    ursTimersRef.current.forEach((id) => window.clearTimeout(id))
    if (ursIntervalRef.current !== null) window.clearInterval(ursIntervalRef.current)
    ursTimersRef.current = []
    ursIntervalRef.current = null

    // 10 stages at 10% increments.
    // Total duration ~150s to match DeepSeek response time (60-180s).
    // Stage 10 (90→99%) uses a slow 1%/7s crawl to avoid a long freeze at 99%.
    const stages = [
      { target: 10, label: 'Parsing approved documents...',     duration: 8000  },
      { target: 20, label: 'Analysing requirements...',         duration: 12000 },
      { target: 30, label: 'Extracting key information...',     duration: 15000 },
      { target: 40, label: 'Structuring document outline...',   duration: 18000 },
      { target: 50, label: 'Generating document sections...',   duration: 20000 },
      { target: 60, label: 'Writing requirement details...',    duration: 20000 },
      { target: 70, label: 'Applying traceability mapping...',  duration: 18000 },
      { target: 80, label: 'Formatting document...',            duration: 15000 },
      { target: 90, label: 'Running quality validation...',     duration: 12000 },
      // Stage 10: crawl 90→99 at 1% per 7s (~63s). This keeps the bar moving
      // even if DeepSeek takes longer than expected, avoiding a frozen 99%.
      { target: 99, label: 'Finalising document...',            duration: 63000 },
    ]

    let currentStage = 0
    let currentPct = 0
    setUrsProgressStage(stages[0].label)

    const advance = () => {
      if (currentStage >= stages.length) return
      const stage = stages[currentStage]
      const steps = 20
      const step = (stage.target - currentPct) / steps
      const intervalMs = stage.duration / steps

      const id = window.setInterval(() => {
        currentPct += step
        if (currentPct >= stage.target) {
          currentPct = stage.target
          window.clearInterval(id)
          currentStage++
          if (currentStage < stages.length) {
            setUrsProgressStage(stages[currentStage].label)
            const tid = window.setTimeout(advance, 300) as unknown as number
            ursTimersRef.current.push(tid)
          }
        }
        setUrsProgress(Math.min(Math.round(currentPct), 99))
      }, intervalMs) as unknown as number

      ursIntervalRef.current = id
    }

    advance()
  }

  const handleUploadTemplate = async () => {
    if (!templateFile || !newTemplateName.trim()) return
    setUploadingTemplate(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('file', templateFile)
      formData.append('name', newTemplateName.trim())
      formData.append('description', newTemplateDesc.trim())

      const response = await fetch('/api/urs/templates/upload', { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || 'Template upload failed')
      }

      const nextTemplate = data as TemplateItem
      setTemplates((prev) => [nextTemplate, ...prev])
      setSelectedTemplate(nextTemplate.template_id)
      setShowUploadTemplate(false)
      setNewTemplateName('')
      setNewTemplateDesc('')
      setTemplateFile(null)
    } catch (err: any) {
      setError(err.message || 'Template upload failed')
    } finally {
      setUploadingTemplate(false)
    }
  }

  const handleGenerate = async () => {
    if (!selectedTemplate || !selectedProject || selectedDocs.length === 0) return

    setGenerating(true)
    setError('')
    setGeneratedDoc(null)
    setUrsProgress(0)
    setUrsProgressStage('')
    setUrsStartTime(Date.now())
    simulateProgress()

    try {
      const normalizedProjectName = projectName.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
      const response = await fetch('/api/urs/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplate,
          project_id: selectedProject,
          doc_ids: selectedDocs,
          output_filename: `URS_${normalizedProjectName || 'Project'}_${dateSuffixHK()}`,
          llm_provider: llmProvider,
          output_format: outputFormat,
        }),
      })
      let data: any = {}
      try {
        data = await response.json()
      } catch {
        throw new Error('Server returned an unexpected response. Please try again.')
      }
      if (!response.ok) {
        const detail: string = typeof data.message === 'string' ? data.message : 'Generate failed'
        // Translate backend error codes to human-readable messages
        const friendly = detail.startsWith('document_not_approved')
          ? 'One or more selected documents are not yet approved. Please check the document status.'
          : detail.startsWith('document_not_in_project')
          ? 'One or more selected documents do not belong to the chosen project.'
          : detail.startsWith('no_content_extracted')
          ? 'Could not extract content from the selected documents.'
          : detail.startsWith('template_content_empty')
          ? 'The selected template appears to be empty.'
          : detail.startsWith('urs_generation_failed')
          ? 'AI generation failed — please check your LLM provider settings and try again.'
          : detail
        throw new Error(friendly)
      }

      // Stop simulation and snap to 100%
      ursTimersRef.current.forEach((id) => window.clearTimeout(id))
      if (ursIntervalRef.current !== null) window.clearInterval(ursIntervalRef.current)
      setUrsProgress(100)
      setUrsProgressStage('Document ready!')
      const doneTimer = window.setTimeout(() => {
        setUrsProgress(0)
        setUrsProgressStage('')
      }, 1000)
      ursTimersRef.current.push(doneTimer)

      const generated = data as GeneratedDocResponse
      setGeneratedDoc(generated)
    } catch (err: any) {
      // Stop simulation on error
      ursTimersRef.current.forEach((id) => window.clearTimeout(id))
      if (ursIntervalRef.current !== null) window.clearInterval(ursIntervalRef.current)
      setUrsProgress(0)
      setUrsProgressStage('')
      setError(err.message || 'Generate failed')
    } finally {
      setGenerating(false)
    }
  }

  const handleDownloadAndSave = async () => {
    if (!generatedDoc) return
    setSaving(true)
    setError('')

    // Build auto-generated filename — use backend's effective_format (authoritative),
    // with outputFormat state as fallback for legacy responses
    const projectSlug = projectName.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'Project'
    const datestamp = dateSuffixHK()
    const version = getNextVersion(projectSlug, datestamp)
    const actualFormat = (generatedDoc.effective_format || outputFormat || 'docx').toLowerCase()
    const fileExt = actualFormat === 'pdf' ? '.pdf' : '.docx'
    const mimeType = actualFormat === 'pdf'
      ? 'application/pdf'
      : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    const autoFilename = `URS_${projectSlug}_${datestamp}_v${version}${fileExt}`

    // 1. Download formatted file from backend
    let downloadOk = false
    try {
      const dlResponse = await fetch(`/api/urs/download/${generatedDoc.generated_id}`)
      if (dlResponse.ok) {
        const arrBuf = await dlResponse.arrayBuffer()
        const blob = new Blob([arrBuf], { type: mimeType })
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = autoFilename
        anchor.style.display = 'none'
        document.body.appendChild(anchor)
        anchor.click()
        document.body.removeChild(anchor)
        URL.revokeObjectURL(url)
        downloadOk = true
      } else {
        let errMsg = 'Download failed'
        try {
          const errData = await dlResponse.json()
          errMsg = errData.message || errMsg
        } catch { /* ignore parse error */ }
        setError(`Download failed: ${errMsg}`)
      }
    } catch (dlErr: any) {
      setError(dlErr.message || 'Download failed — network error')
    }

    // 2. Save to Google Drive
    let driveLink: string | null = null
    try {
      const response = await fetch(`/api/urs/save/${generatedDoc.generated_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: autoFilename.replace(/\.[^.]+$/, '') }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || 'Save to Google Drive failed')
      }
      driveLink = data.drive_link || null
    } catch (err: any) {
      setError(err.message || 'Downloaded locally, but Save to Google Drive failed')
    } finally {
      setSaving(false)
    }

    // 3. Show success toast
    if (downloadOk) {
      showToast({ message: `Downloaded as ${autoFilename}`, driveLink })
    }
  }

  const handleDeleteTemplate = async (templateId: string) => {
    setError('')
    try {
      const response = await fetch(`/api/urs/templates/${templateId}`, { method: 'DELETE' })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || 'Delete failed')
      }
      setTemplates((prev) => prev.filter((t) => t.template_id !== templateId))
      if (selectedTemplate === templateId) {
        setSelectedTemplate('')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete template')
    } finally {
      setShowDeleteConfirm(false)
      setDeletingTemplateId(null)
    }
  }

  return (
    <Layout>
      <div className="container mt-4 mb-5" style={{ maxWidth: 980 }}>
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.back()}>
          Back
        </button>
        <h1 style={{ marginBottom: 8 }}>Generate URS / Requirement Document</h1>
        <p style={{ color: '#6b7280', marginBottom: 20 }}>
          Select a template, choose an active project, and generate a requirement draft from approved documents.
        </p>

        {error && <div className="alert alert-danger">{error}</div>}

        {loadingInitial ? (
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        ) : !allowed ? (
          <div className="alert alert-warning">Your role does not have access to Generate URS.</div>
        ) : (
          <>
            <div
              style={{
                background: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: 20, marginBottom: 12 }}>Step 1: Select Template</h3>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  style={{ flex: 1, padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                >
                  <option value="">-- Select Template --</option>
                  {templates.map((template) => (
                    <option key={template.template_id} value={template.template_id}>
                      {template.name} ({template.file_format})
                    </option>
                  ))}
                </select>

                {selectedTemplate && (
                  <button
                    onClick={() => {
                      setDeletingTemplateId(selectedTemplate)
                      setShowDeleteConfirm(true)
                    }}
                    title="Delete template"
                    style={{
                      background: 'none',
                      border: '1px solid #fca5a5',
                      borderRadius: '6px',
                      padding: '7px 10px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      color: '#dc2626',
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>

              {selectedTemplateData && (
                <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280' }}>
                  Detected placeholders:{' '}
                  {(selectedTemplateData.detected_placeholders || []).map((placeholder) => (
                    <span
                      key={placeholder}
                      style={{
                        display: 'inline-block',
                        background: '#f3f4f6',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        margin: '2px',
                        color: '#374151',
                      }}
                    >
                      {placeholder}
                    </span>
                  ))}
                </div>
              )}

              <div style={{ marginTop: '12px' }}>
                <button
                  onClick={() => setShowUploadTemplate(true)}
                  style={{
                    fontSize: '13px',
                    color: '#2563eb',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  + Upload New Template
                </button>
              </div>

              {showUploadTemplate && (
                <div
                  style={{
                    marginTop: '12px',
                    padding: '16px',
                    background: '#f9fafb',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                  }}
                >
                  <h4 style={{ fontSize: 16, marginBottom: 12 }}>Upload New Template</h4>
                  <input
                    type="text"
                    placeholder="Template Name"
                    value={newTemplateName}
                    onChange={(e) => setNewTemplateName(e.target.value)}
                    style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                  />
                  <textarea
                    placeholder="Description (optional)"
                    value={newTemplateDesc}
                    onChange={(e) => setNewTemplateDesc(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px',
                      marginTop: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      minHeight: 80,
                    }}
                  />
                  <input
                    type="file"
                    accept=".docx,.xlsx,.txt,.pdf"
                    onChange={(e) => setTemplateFile(e.target.files?.[0] || null)}
                    style={{ marginTop: '8px' }}
                  />
                  <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => void handleUploadTemplate()}
                      disabled={uploadingTemplate}
                      style={{
                        background: '#2563eb',
                        color: 'white',
                        padding: '6px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        cursor: uploadingTemplate ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {uploadingTemplate ? 'Uploading...' : 'Upload'}
                    </button>
                    <button
                      onClick={() => setShowUploadTemplate(false)}
                      style={{
                        padding: '6px 16px',
                        borderRadius: '6px',
                        border: '1px solid #d1d5db',
                        background: 'white',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div
              style={{
                background: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: 20, marginBottom: 12 }}>Step 2: Select Project</h3>
              <select
                value={selectedProject}
                onChange={(e) => {
                  const projectId = e.target.value
                  setSelectedProject(projectId)
                  setSelectedDocs([])
                  setGeneratedDoc(null)
                  void loadApprovedDocs(projectId)
                }}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
              >
                <option value="">-- Select Active Project --</option>
                {activeProjects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>

            <div
              style={{
                background: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: 20, marginBottom: 12 }}>Step 3: Select Approved Documents</h3>

              {approvedDocs.filter((doc) => doc.is_active !== false).length === 0 ? (
                <p style={{ color: '#9ca3af', marginBottom: 0 }}>
                  {selectedProject ? 'No approved documents found' : 'Please select a project first'}
                </p>
              ) : (
                <>
                  <div style={{ marginBottom: '8px', display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => setSelectedDocs(approvedDocs.filter((doc) => doc.is_active !== false).map((doc) => doc.doc_id))}
                      style={{ fontSize: '13px', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      Select All
                    </button>
                    <button
                      onClick={() => setSelectedDocs([])}
                      style={{ fontSize: '13px', color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      Clear All
                    </button>
                  </div>

                  {approvedDocs.filter((doc) => doc.is_active !== false).map((doc) => (
                    <div
                      key={doc.doc_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '8px',
                        borderBottom: '1px solid #f3f4f6',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocs.includes(doc.doc_id)}
                        onChange={(event) => {
                          if (event.target.checked) {
                            setSelectedDocs((prev) => (prev.includes(doc.doc_id) ? prev : [...prev, doc.doc_id]))
                          } else {
                            setSelectedDocs((prev) => prev.filter((id) => id !== doc.doc_id))
                          }
                        }}
                      />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div
                          title={doc.title}
                          style={{
                            fontWeight: 500,
                            lineHeight: 1.35,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            wordBreak: 'break-word',
                            overflowWrap: 'anywhere',
                          }}
                        >
                          {doc.title}
                        </div>
                        <div style={{ fontSize: '12px', color: '#6b7280', wordBreak: 'break-word' }}>
                          {doc.doc_type || 'document'} | Approved {formatHKTime(doc.updated_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>

            <div
              style={{
                background: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: 20, marginBottom: 12 }}>LLM Provider</h3>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
              >
                <optgroup label="Auto">
                  <option value="auto">Auto (DeepSeek → OpenRouter fallback)</option>
                </optgroup>
                <optgroup label="DeepSeek">
                  <option value="deepseek">DeepSeek</option>
                </optgroup>
                <optgroup label="OpenRouter">
                  <option value="openrouter">OpenRouter (GPT-4o-mini)</option>
                  <option value="gemini-2.5-pro">Gemini 2.5 Pro (OpenRouter)</option>
                  <option value="minimax-m2.5">MiniMax M2.5 (OpenRouter)</option>
                  <option value="claude-haiku-4-5">Claude Haiku 4.5 (OpenRouter)</option>
                </optgroup>
              </select>
            </div>

            <div
              style={{
                background: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: 20, marginBottom: 12 }}>Output Format</h3>
              <div style={{ display: 'flex', gap: '12px' }}>
                {(['docx', 'pdf'] as const).map((fmt) => (
                  <label
                    key={fmt}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 16px',
                      border: `2px solid ${outputFormat === fmt ? '#2563eb' : '#d1d5db'}`,
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: outputFormat === fmt ? 600 : 400,
                      color: outputFormat === fmt ? '#2563eb' : '#374151',
                      background: outputFormat === fmt ? '#eff6ff' : 'white',
                      userSelect: 'none',
                    }}
                  >
                    <input
                      type="radio"
                      name="outputFormat"
                      value={fmt}
                      checked={outputFormat === fmt}
                      onChange={() => setOutputFormat(fmt)}
                      style={{ accentColor: '#2563eb' }}
                    />
                    {fmt === 'docx' ? 'DOCX (Word)' : 'PDF'}
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={() => void handleGenerate()}
              disabled={!selectedTemplate || !selectedProject || selectedDocs.length === 0 || generating}
              style={{
                width: '100%',
                padding: '12px',
                background: !selectedTemplate || !selectedProject || selectedDocs.length === 0 ? '#9ca3af' : '#2563eb',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 600,
                cursor: !selectedTemplate || !selectedProject || selectedDocs.length === 0 ? 'not-allowed' : 'pointer',
                marginBottom: '16px',
              }}
            >
              {generating ? 'Generating...' : 'Proceed - Generate Document'}
            </button>

            <ProgressBar
              show={generating}
              progress={ursProgress}
              stage={ursProgressStage}
              title="Generating URS document..."
              startTime={ursStartTime ?? undefined}
            />

            {generatedDoc && (
              <div
                style={{
                  background: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  padding: '20px',
                }}
              >
                <h3 style={{ fontSize: 20, marginBottom: 16 }}>Preview — Generated Document</h3>

                <div
                  style={{
                    background: '#f0fdf4',
                    border: '1px solid #86efac',
                    borderRadius: '6px',
                    padding: '8px 16px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '8px',
                  }}
                >
                  <CheckCircle size={18} color="#16a34a" />
                  <strong style={{ minWidth: 0, wordBreak: 'break-word', overflowWrap: 'anywhere' }}>{generatedDoc.filename}</strong>
                </div>

                {/* Placeholder fill summary */}
                {generatedDoc.placeholder_summary && (
                  <div
                    style={{
                      marginBottom: '16px',
                      padding: '12px 16px',
                      background: '#f9fafb',
                      border: '1px solid #e5e7eb',
                      borderRadius: '6px',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 8, color: '#374151' }}>Placeholder Fill Summary</div>
                    {generatedDoc.placeholder_summary.filled.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        <span style={{ color: '#16a34a', fontWeight: 500 }}>Filled:</span>{' '}
                        {generatedDoc.placeholder_summary.filled.map((ph) => (
                          <span
                            key={ph}
                            style={{
                              display: 'inline-block',
                              background: '#dcfce7',
                              color: '#166534',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              margin: '2px',
                              fontSize: '12px',
                            }}
                          >
                            {ph}
                          </span>
                        ))}
                      </div>
                    )}
                    {generatedDoc.placeholder_summary.unfilled.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        <span style={{ color: '#dc2626', fontWeight: 500 }}>Not filled:</span>{' '}
                        {generatedDoc.placeholder_summary.unfilled.map((ph) => (
                          <span
                            key={ph}
                            style={{
                              display: 'inline-block',
                              background: '#fef2f2',
                              color: '#991b1b',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              margin: '2px',
                              fontSize: '12px',
                            }}
                          >
                            {ph}
                          </span>
                        ))}
                      </div>
                    )}
                    {generatedDoc.placeholder_summary.to_be_confirmed_count > 0 && (
                      <div style={{ color: '#92400e', fontSize: '12px' }}>
                        ⚠ {generatedDoc.placeholder_summary.to_be_confirmed_count} field(s) marked as [TO BE CONFIRMED]
                      </div>
                    )}
                  </div>
                )}

                {/* Word-style document preview */}
                <div
                  style={{
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    marginBottom: '16px',
                    maxHeight: '500px',
                    overflowY: 'auto',
                    background: '#fff',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                  }}
                >
                  <div
                    style={{
                      padding: '40px 48px',
                      fontFamily: "'Times New Roman', 'Georgia', serif",
                      fontSize: '13.5px',
                      lineHeight: 1.7,
                      color: '#1f2937',
                    }}
                    dangerouslySetInnerHTML={{
                      __html: generatedDoc.content
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(
                          /^(#{1,3})\s+(.+)$/gm,
                          (_match: string, hashes: string, text: string) => {
                            const level = hashes.length
                            if (level === 1)
                              return `<h2 style="text-align:center;font-size:20px;font-weight:700;margin:24px 0 12px;color:#1e3a5f;border-bottom:2px solid #2563eb;padding-bottom:8px;">${text}</h2>`
                            if (level === 2)
                              return `<h3 style="font-size:16px;font-weight:700;margin:20px 0 8px;color:#1e3a5f;">${text}</h3>`
                            return `<h4 style="font-size:14px;font-weight:600;margin:16px 0 6px;color:#374151;">${text}</h4>`
                          }
                        )
                        .replace(
                          /\*\*(.+?)\*\*/g,
                          '<strong>$1</strong>'
                        )
                        .replace(
                          /\[TO BE CONFIRMED\]/g,
                          '<span style="background:#fef3c7;padding:1px 6px;border-radius:3px;color:#92400e;font-weight:600;">[TO BE CONFIRMED]</span>'
                        )
                        .replace(
                          /\[([A-Z_][A-Z0-9_]*)\]/g,
                          '<span style="background:#fef3c7;padding:1px 6px;border-radius:3px;color:#92400e;font-weight:600;">[$1]</span>'
                        )
                        .replace(
                          /\{\{(.+?)\}\}/g,
                          '<span style="background:#fef3c7;padding:1px 6px;border-radius:3px;color:#92400e;font-weight:600;">{{$1}}</span>'
                        )
                        .replace(
                          /^(FR-\d+|NFR-\d+|GAP-\d+):/gm,
                          '<strong style="color:#2563eb;">$1:</strong>'
                        )
                        .replace(
                          /^\|(.+)\|$/gm,
                          (row: string) => {
                            const cells = row
                              .split('|')
                              .filter((c: string) => c.trim() !== '')
                              .map((c: string) => `<td style="border:1px solid #d1d5db;padding:6px 10px;">${c.trim()}</td>`)
                              .join('')
                            return `<tr>${cells}</tr>`
                          }
                        )
                        .replace(
                          /(<tr>[\s\S]*?<\/tr>(\s*<tr>[\s\S]*?<\/tr>)*)/g,
                          '<table style="border-collapse:collapse;width:100%;margin:12px 0;font-size:13px;">$1</table>'
                        )
                        .replace(
                          /^[-*]\s+(.+)$/gm,
                          '<li style="margin-left:20px;margin-bottom:2px;">$1</li>'
                        )
                        .replace(
                          /^---+$/gm,
                          '<hr style="border:none;border-top:1px solid #d1d5db;margin:16px 0;" />'
                        )
                        .replace(/\n/g, '<br />')
                    }}
                  />
                </div>

                <button
                  onClick={() => void handleDownloadAndSave()}
                  disabled={saving}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    width: '100%',
                    padding: '10px 20px',
                    background: saving ? '#93c5fd' : '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: saving ? 'not-allowed' : 'pointer',
                    fontWeight: 600,
                    fontSize: '15px',
                  }}
                >
                  <Download size={18} />
                  {saving ? 'Downloading & Saving...' : 'Download and Save to Google Drive'}
                </button>
              </div>
            )}

            {/* Delete confirmation modal */}
            {showDeleteConfirm && deletingTemplateId && (
              <div
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'rgba(0,0,0,0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 9999,
                }}
                onClick={() => {
                  setShowDeleteConfirm(false)
                  setDeletingTemplateId(null)
                }}
              >
                <div
                  style={{
                    background: 'white',
                    borderRadius: '10px',
                    padding: '24px',
                    maxWidth: 420,
                    width: '90%',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <h4 style={{ marginBottom: 12, fontSize: 18 }}>Delete Template?</h4>
                  <p style={{ color: '#4b5563', marginBottom: 20, fontSize: 14 }}>
                    Are you sure you want to delete this template? This will also remove the file from Google Drive. This action cannot be undone.
                  </p>
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => {
                        setShowDeleteConfirm(false)
                        setDeletingTemplateId(null)
                      }}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid #d1d5db',
                        background: 'white',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => void handleDeleteTemplate(deletingTemplateId)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        background: '#dc2626',
                        color: 'white',
                        cursor: 'pointer',
                        fontWeight: 600,
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Success toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: '#065f46',
            color: '#fff',
            padding: '14px 20px',
            borderRadius: '10px',
            boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            maxWidth: '440px',
            fontSize: '14px',
            animation: 'fadeInUp 0.3s ease-out',
          }}
        >
          <CheckCircle size={20} style={{ flexShrink: 0 }} />
          <span>{toast.message}</span>
          {toast.driveLink && (
            <a
              href={toast.driveLink}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#a7f3d0',
                marginLeft: '6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                textDecoration: 'underline',
                whiteSpace: 'nowrap',
              }}
            >
              Open in Drive <ExternalLink size={14} />
            </a>
          )}
          <button
            onClick={() => setToast(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#d1fae5',
              cursor: 'pointer',
              fontSize: '18px',
              marginLeft: '8px',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}

      <style jsx global>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </Layout>
  )
}
