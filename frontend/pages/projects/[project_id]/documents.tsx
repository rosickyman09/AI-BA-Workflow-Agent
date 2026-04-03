import React, { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import {
  getProject,
  getProjectDocuments,
  updateProjectStatusByProjectPage,
  type ProjectDocumentItem,
  type ProjectItem,
} from '@/services/projects'
import 'bootstrap/dist/css/bootstrap.min.css'

type TabKey = 'all' | 'in_progress' | 'approved' | 'rejected'
type ProjectStatus = 'active' | 'inactive' | 'completed' | 'frozen'

function normalizeUTC(iso: string): string {
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(normalizeUTC(iso)).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Hong_Kong',
  })
}

function projectStatusStyle(status: string): React.CSSProperties {
  const normalized = (status || '').trim().toLowerCase()
  if (normalized === 'active') {
    return { color: '#16a34a', background: '#f0fdf4' }
  }
  if (normalized === 'inactive') {
    return { color: '#ca8a04', background: '#fefce8' }
  }
  if (normalized === 'completed') {
    return { color: '#2563eb', background: '#eff6ff' }
  }
  if (normalized === 'frozen') {
    return { color: '#4b5563', background: '#f3f4f6' }
  }
  return { color: '#4b5563', background: '#f3f4f6' }
}

function documentWorkflowBadge(doc: ProjectDocumentItem) {
  const wfStatus = (doc.workflow_status || '').trim().toLowerCase()
  const currentStep = doc.current_step || 1
  const resubmitted = (doc.resubmit_count || 0) > 0

  if (wfStatus === 'rejected') {
    return <span className="badge bg-danger">❌ Rejected</span>
  }
  if (wfStatus === 'approved' && (doc.status || '').trim().toLowerCase() === 'approved') {
    return <span className="badge bg-success">✅ Approved</span>
  }
  if (wfStatus === 'returned_to_submitter' || wfStatus === 'returned_to_step1') {
    return <span className="badge" style={{ background: '#f97316', color: 'white' }}>🟠 Returned - Action Required</span>
  }
  if (wfStatus === 'in_progress') {
    if (resubmitted && currentStep === 2) {
      return <span className="badge" style={{ background: '#7c3aed', color: 'white' }}>🔄 Resubmitted - Awaiting Step 2</span>
    }
    if (resubmitted && currentStep === 1) {
      return <span className="badge" style={{ background: '#7c3aed', color: 'white' }}>🔄 Resubmitted - Awaiting Step 1</span>
    }
    if (currentStep === 2) {
      return <span className="badge bg-primary">🔵 Awaiting Step 2</span>
    }
    return <span className="badge bg-primary">🔵 Awaiting Step 1</span>
  }

  const fallback = (doc.status || '').trim().toLowerCase()
  if (fallback === 'approved') return <span className="badge bg-success">✅ Approved</span>
  if (fallback === 'rejected') return <span className="badge bg-danger">❌ Rejected</span>
  return <span className="badge bg-secondary">{fallback || 'unknown'}</span>
}

function canChangeStatus(role: string): boolean {
  return ['admin', 'business_owner'].includes(role)
}

function getAvailableStatuses(currentStatus: ProjectStatus, role: string) {
  if (currentStatus === 'completed') {
    return [] as Array<{ value: ProjectStatus; label: string; color: string }>
  }

  const options: Array<{ value: ProjectStatus; label: string; color: string }> = []

  if (currentStatus !== 'active') {
    options.push({ value: 'active', label: '✅ Set Active', color: '#16a34a' })
  }

  if (currentStatus !== 'inactive') {
    options.push({ value: 'inactive', label: '⏸️ Set Inactive', color: '#ca8a04' })
  }

  options.push({ value: 'completed', label: '🏁 Set Completed', color: '#2563eb' })

  if (role === 'admin' && currentStatus !== 'frozen') {
    options.push({ value: 'frozen', label: '🔒 Freeze Project', color: '#4b5563' })
  }

  return options
}

export default function ProjectDocumentsPage() {
  const router = useRouter()
  const { project_id } = router.query

  const [project, setProject] = useState<ProjectItem | null>(null)
  const [docs, setDocs] = useState<ProjectDocumentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('all')
  const [currentRole, setCurrentRole] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [statusSaving, setStatusSaving] = useState(false)

  const projectId = typeof project_id === 'string' ? project_id : ''

  const availableStatusOptions = useMemo(() => {
    const status = ((project?.status || 'active').trim().toLowerCase() as ProjectStatus)
    return getAvailableStatuses(status, currentRole)
  }, [project?.status, currentRole])

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
      setCurrentRole((user.role || '').trim().toLowerCase())
    }
    void bootstrap()
  }, [])

  useEffect(() => {
    if (!router.isReady || !projectId) {
      return
    }

    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const [projectInfo, documentItems] = await Promise.all([
          getProject(projectId),
          getProjectDocuments(projectId, activeTab),
        ])
        setProject(projectInfo)
        setDocs(documentItems)
      } catch (err: any) {
        setError(err.response?.data?.message || 'Unable to load project documents')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [router.isReady, projectId, activeTab])

  const handleToggleVisibility = async (docId: string, newIsActive: boolean) => {
    try {
      const res = await fetch(`/api/documents/${docId}/visibility`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ is_active: newIsActive }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as any).detail || 'Failed to update visibility')
      }
      setDocs((prev) =>
        prev.map((doc) => (doc.doc_id === docId ? { ...doc, is_active: newIsActive } : doc))
      )
      setSuccessMessage(
        newIsActive
          ? '✓ Document set to Active — now visible in Generate URS and Knowledge Base'
          : '○ Document set to Inactive — hidden from Generate URS and Knowledge Base',
      )
    } catch (err: any) {
      setError(err.message || 'Failed to update document visibility')
    }
  }

  const handleStatusChange = async (nextStatus: ProjectStatus) => {
    if (!project || !projectId || statusSaving) {
      return
    }

    const currentStatus = ((project.status || 'active').trim().toLowerCase() as ProjectStatus)
    if (currentStatus === nextStatus) {
      return
    }

    const confirmed = window.confirm(`Change project status to ${nextStatus.toUpperCase()}?\n\nThis action will be logged.`)
    if (!confirmed) {
      return
    }

    const previousProject = project
    setProject({ ...project, status: nextStatus })
    setStatusSaving(true)
    setError('')
    setSuccessMessage('')

    try {
      const updated = await updateProjectStatusByProjectPage(projectId, nextStatus)
      setProject((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          status: updated.status,
          updated_at: updated.updated_at || prev.updated_at,
        }
      })
      setSuccessMessage(`Project status updated to ${updated.status}.`)
    } catch (err: any) {
      setProject(previousProject)
      setError(err.response?.data?.message || 'Unable to update project status')
    } finally {
      setStatusSaving(false)
    }
  }

  return (
    <Layout>
      <div className="container mt-4">
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.push('/projects')}>
          ← Back
        </button>

        {error && (
          <div className="alert alert-danger alert-dismissible">
            {error}
            <button type="button" className="btn-close" onClick={() => setError('')} />
          </div>
        )}

        {successMessage && (
          <div className="alert alert-success alert-dismissible">
            {successMessage}
            <button type="button" className="btn-close" onClick={() => setSuccessMessage('')} />
          </div>
        )}

        <div className="card mb-4">
          <div className="card-body">
            <div className="d-flex flex-wrap justify-content-between align-items-start gap-3">
              <div>
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <h2 className="mb-0">{project?.name || 'Project'}</h2>
                  <span
                    className="badge"
                    style={{
                      ...projectStatusStyle(project?.status || 'active'),
                      padding: '6px 10px',
                      fontSize: '0.8rem',
                    }}
                  >
                    {(project?.status || 'active').trim().toLowerCase()}
                  </span>
                </div>
                <p className="text-muted mb-0 mt-2">{project?.description || 'No description provided.'}</p>
              </div>

              <div className="d-flex align-items-center gap-2 flex-wrap">
                {canChangeStatus(currentRole) && availableStatusOptions.length > 0 && (
                  <div>
                    <select
                      className="form-select"
                      disabled={statusSaving}
                      defaultValue=""
                      onChange={(event) => {
                        const value = event.target.value as ProjectStatus
                        if (value) {
                          void handleStatusChange(value)
                          event.target.value = ''
                        }
                      }}
                    >
                      <option value="">Change Status ▼</option>
                      {availableStatusOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void router.push(`/documents?project_id=${projectId}`)}
                >
                  + Upload Document
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h4 className="mb-0">Documents</h4>
            </div>

            <div className="btn-group mb-3" role="group">
              <button
                type="button"
                className={`btn ${activeTab === 'all' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setActiveTab('all')}
              >
                All
              </button>
              <button
                type="button"
                className={`btn ${activeTab === 'in_progress' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setActiveTab('in_progress')}
              >
                In Progress
              </button>
              <button
                type="button"
                className={`btn ${activeTab === 'approved' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setActiveTab('approved')}
              >
                Approved
              </button>
              <button
                type="button"
                className={`btn ${activeTab === 'rejected' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setActiveTab('rejected')}
              >
                Rejected
              </button>
            </div>

            {loading ? (
              <div className="spinner-border" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            ) : docs.length === 0 ? (
              <p className="text-muted mb-0">No documents found for this project.</p>
            ) : (
              <div className="table-responsive">
                <table className="table table-bordered align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Document</th>
                      <th>Submitter</th>
                      <th>Status</th>
                      <th>Visibility</th>
                      <th>Step</th>
                      <th>Submitted</th>
                      <th>Last Updated</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.map((doc) => (
                      <tr key={doc.doc_id}>
                        <td>
                          <a href={`/documents/${doc.doc_id}/detail`} style={{ color: '#2563eb', fontWeight: 500 }}>
                            {doc.title}
                          </a>
                        </td>
                        <td>{doc.submitter_name || '—'}</td>
                        <td>{documentWorkflowBadge(doc)}</td>
                        <td>
                          {(currentRole === 'business_owner' || currentRole === 'project_owner' || currentRole === 'admin')
                            && (doc.status || '').toLowerCase() === 'approved' ? (
                            <button
                              type="button"
                              className={`vis-badge-toggle ${doc.is_active !== false ? 'active' : 'inactive'}`}
                              title={doc.is_active !== false ? 'Click to deactivate' : 'Click to activate'}
                              onClick={() => void handleToggleVisibility(doc.doc_id, doc.is_active === false)}
                            >
                              {doc.is_active !== false ? '\u25cf Active' : '\u25cb Inactive'}
                            </button>
                          ) : (
                            <span className={`vis-badge-readonly ${doc.is_active !== false ? 'active' : 'inactive'}`}>
                              {doc.is_active !== false ? '\u25cf Active' : '\u25cb Inactive'}
                            </span>
                          )}
                        </td>
                        <td>
                          {doc.current_step && doc.total_steps
                            ? `${doc.current_step} / ${doc.total_steps}`
                            : '—'}
                        </td>
                        <td>{formatDateTime(doc.created_at)}</td>
                        <td>{formatDateTime(doc.updated_at)}</td>
                        <td>
                          <a href={`/documents/${doc.doc_id}/detail`} className="btn btn-sm btn-outline-primary">
                            Open
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`
        .vis-badge-toggle, .vis-badge-readonly {
          padding: 3px 10px;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
          white-space: nowrap;
          border: 1px solid;
          display: inline-block;
        }
        .vis-badge-toggle.active, .vis-badge-readonly.active {
          background-color: #d1fae5;
          color: #065f46;
          border-color: #6ee7b7;
        }
        .vis-badge-toggle.inactive, .vis-badge-readonly.inactive {
          background-color: #f3f4f6;
          color: #6b7280;
          border-color: #d1d5db;
        }
        .vis-badge-toggle {
          cursor: pointer;
          background: none;
        }
        .vis-badge-toggle:hover { opacity: 0.8; }
        .vis-badge-readonly { cursor: default; }
      `}</style>
    </Layout>
  )
}
