import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import { getDocumentStatus, listDocuments, type DocumentListItem, uploadDocument } from '@/services/documents'
import { listProjects, type ProjectItem } from '@/services/projects'
import 'bootstrap/dist/css/bootstrap.min.css'

interface UploadItemState {
  fileName: string
  progress: number
  status: 'pending' | 'uploading' | 'completed' | 'failed'
  error?: string
  documentId?: string
}

export default function DocumentsPage() {
  const router = useRouter()
  const [projectId, setProjectId] = useState('')
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadItems, setUploadItems] = useState<UploadItemState[]>([])
  const [uploading, setUploading] = useState(false)
  const [overallStatus, setOverallStatus] = useState('')
  const [error, setError] = useState('')
  const [currentRole, setCurrentRole] = useState('')
  const [showSuccess, setShowSuccess] = useState(false)
  const [lastUploadedCount, setLastUploadedCount] = useState(0)
  const [submissionNotes, setSubmissionNotes] = useState('')
  const [registryItems, setRegistryItems] = useState<DocumentListItem[]>([])
  const [registryLoading, setRegistryLoading] = useState(false)
  const [registryError, setRegistryError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [docTypeFilter, setDocTypeFilter] = useState('all')
  const [submitterFilter, setSubmitterFilter] = useState('all')

  const loadRegistry = async (targetProjectId: string) => {
    setRegistryLoading(true)
    setRegistryError('')
    try {
      const items = await listDocuments(targetProjectId)
      setRegistryItems(items)
    } catch (err: any) {
      setRegistryError(err.response?.data?.message || 'Unable to load documents table')
      setRegistryItems([])
    } finally {
      setRegistryLoading(false)
    }
  }

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
      setCurrentRole((user.role || '').trim().toLowerCase())
      const items = await listProjects()
      const activeProjects = items.filter((project) => {
        const normalizedStatus = (project.status || '').trim().toLowerCase()
        return normalizedStatus === 'active' && !project.is_frozen
      })
      setProjects(activeProjects)
      const requestedProjectId =
        typeof router.query.project_id === 'string' ? router.query.project_id.trim() : ''
      const preselectedProjectId =
        requestedProjectId && activeProjects.some((project) => project.project_id === requestedProjectId)
          ? requestedProjectId
          : ''

      if (preselectedProjectId) {
        setProjectId(preselectedProjectId)
        await loadRegistry(preselectedProjectId)
      } else {
        // Initial behavior: no default project selected, table remains empty
        // until user explicitly chooses a project.
        setProjectId('')
        setRegistryItems([])
        setRegistryError('')
      }
    }
    if (!router.isReady) {
      return
    }
    void bootstrap()
  }, [router.isReady, router.query.project, router.query.project_id])

  const handleProjectChange = (nextProjectId: string) => {
    const normalizedProjectId = nextProjectId.trim()
    setProjectId(normalizedProjectId)
    if (!normalizedProjectId) {
      setRegistryItems([])
      setRegistryError('')
      setRegistryLoading(false)
      return
    }
    void loadRegistry(normalizedProjectId)
  }

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!projectId) {
      setError('Please select a project first')
      return
    }
    if (selectedFiles.length === 0) {
      setError('Please select at least one file')
      return
    }

    setUploading(true)
    setError('')
    setOverallStatus('Uploading files...')

    const initialState: UploadItemState[] = selectedFiles.map((file) => ({
      fileName: file.name,
      progress: 0,
      status: 'pending',
    }))
    setUploadItems(initialState)

    let successCount = 0
    let failCount = 0

    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index]

      setUploadItems((previous) =>
        previous.map((item, itemIndex) =>
          itemIndex === index
            ? {
                ...item,
                status: 'uploading',
              }
            : item
        )
      )

      try {
        const response = await uploadDocument(file, projectId, (progress) => {
          setUploadItems((previous) =>
            previous.map((item, itemIndex) =>
              itemIndex === index
                ? {
                    ...item,
                    progress,
                  }
                : item
            )
          )
        }, submissionNotes || undefined)

        setUploadItems((previous) =>
          previous.map((item, itemIndex) =>
            itemIndex === index
              ? {
                  ...item,
                  progress: 100,
                  status: 'completed',
                  documentId: response.document_id,
                }
              : item
          )
        )

        void getDocumentStatus(response.document_id)
        successCount += 1
      } catch (err: any) {
        failCount += 1
        setUploadItems((previous) =>
          previous.map((item, itemIndex) =>
            itemIndex === index
              ? {
                  ...item,
                  status: 'failed',
                  error: err.response?.data?.message || 'Upload failed',
                }
              : item
          )
        )
      }
    }

    setOverallStatus(`Upload complete: ${successCount} succeeded, ${failCount} failed.`)
    setUploading(false)
    if (successCount > 0) {
      setLastUploadedCount(successCount)
      setShowSuccess(true)
      if (projectId) {
        await loadRegistry(projectId)
      }
    }
  }

  const handleFileSelection = (files: FileList | null) => {
    if (!files) {
      setSelectedFiles([])
      setUploadItems([])
      return
    }

    const chosen = Array.from(files)
    if (chosen.length > 5) {
      setError('You can upload up to 5 files at once')
      setSelectedFiles([])
      setUploadItems([])
      return
    }

    setError('')
    setSelectedFiles(chosen)
    setUploadItems(
      chosen.map((file) => ({
        fileName: file.name,
        progress: 0,
        status: 'pending',
      }))
    )
  }

  const normalizedRole = (currentRole || '').trim().toLowerCase()
  const canUpload = ['admin', 'ba', 'pm', 'business_owner', 'tech_lead'].includes(normalizedRole)
  const selectedProject = projects.find((project) => project.project_id === projectId)
  const statusOptions = useMemo(
    () => ['all', ...Array.from(new Set(registryItems.map((doc) => (doc.status || '').trim()).filter(Boolean)))],
    [registryItems]
  )
  const docTypeOptions = useMemo(
    () => ['all', ...Array.from(new Set(registryItems.map((doc) => (doc.doc_type || '').trim()).filter(Boolean)))],
    [registryItems]
  )
  const submitterOptions = useMemo(
    () => ['all', ...Array.from(new Set(registryItems.map((doc) => (doc.submitter_name || '').trim()).filter(Boolean)))],
    [registryItems]
  )
  const filteredRegistryItems = useMemo(
    () => registryItems.filter((doc) => {
      if (statusFilter !== 'all' && doc.status !== statusFilter) return false
      if (docTypeFilter !== 'all' && (doc.doc_type || '') !== docTypeFilter) return false
      if (submitterFilter !== 'all' && (doc.submitter_name || '') !== submitterFilter) return false
      return true
    }),
    [registryItems, statusFilter, docTypeFilter, submitterFilter]
  )

  const handleUploadAnother = () => {
    setShowSuccess(false)
    setSelectedFiles([])
    setUploadItems([])
    setOverallStatus('')
    setSubmissionNotes('')
  }

  return (
    <Layout>
      <div className="container mt-4">
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.push('/projects')}>
          ← Back
        </button>
        <h1>Documents Upload</h1>

        {error && <div className="alert alert-danger">{error}</div>}

        {showSuccess ? (
          <div className="card border-success">
            <div className="card-body text-center py-5">
              <div style={{ fontSize: '3rem' }}>✅</div>
              <h4 className="mt-3 text-success">Document submitted successfully!</h4>
              <p className="text-muted mt-2">
                {lastUploadedCount === 1 ? '1 document' : `${lastUploadedCount} documents`} submitted.
                Step 1 reviewer has been notified.
              </p>
              <p className="text-muted">Track progress in My Documents.</p>
              <div className="d-flex gap-3 justify-content-center mt-4">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void router.push('/my-documents')}
                >
                  Go to My Documents
                </button>
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={handleUploadAnother}
                >
                  Upload Another
                </button>
              </div>
            </div>
          </div>
        ) : !canUpload ? (
          <div className="alert alert-warning">Your role does not allow document uploads.</div>
        ) : (
          <div className="card">
            <div className="card-body">
              <form onSubmit={handleUpload}>
                <div className="mb-3">
                  <label className="form-label">Project</label>
                  <select
                    className="form-control"
                    value={projectId}
                    onChange={(e) => handleProjectChange(e.target.value)}
                    required
                    disabled={projects.length === 0}
                  >
                    <option value="">-- Select a project --</option>
                    {projects.length === 0 ? (
                      <option value="">No projects available</option>
                    ) : (
                      projects.map((project) => (
                        <option key={project.project_id} value={project.project_id}>
                          {project.name}
                        </option>
                      ))
                    )}
                  </select>
                  {selectedProject && (
                    <div className="mt-2 d-flex gap-2 align-items-center">
                      <span className={`badge bg-${selectedProject.status === 'active' ? 'success' : 'secondary'}`}>
                        {selectedProject.status}
                      </span>
                      {selectedProject.is_frozen && <span className="badge bg-dark">Frozen</span>}
                    </div>
                  )}
                </div>

                <div className="mb-3">
                  <label className="form-label">Document File</label>
                  <input
                    type="file"
                    multiple
                    className="form-control"
                    onChange={(e) => handleFileSelection(e.target.files)}
                    required
                  />
                  <small className="text-muted">Maximum 5 files per upload.</small>
                </div>

                <div className="mb-3">
                  <label className="form-label">Submission Notes <span className="text-muted small">(optional)</span></label>
                  <textarea
                    className="form-control"
                    rows={3}
                    maxLength={500}
                    placeholder="Add notes for reviewers (optional)"
                    value={submissionNotes}
                    onChange={(e) => setSubmissionNotes(e.target.value)}
                  />
                  <div className="text-muted small text-end">{submissionNotes.length}/500</div>
                </div>

                <button className="btn btn-primary" disabled={uploading || !projectId} type="submit">
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </form>

              {uploadItems.length > 0 && (
                <div className="mt-4">
                  <h5 className="mb-3">Files</h5>
                  <ul className="list-group">
                    {uploadItems.map((item, index) => (
                      <li key={`${item.fileName}-${index}`} className="list-group-item">
                        <div className="d-flex justify-content-between mb-2">
                          <span>{item.fileName}</span>
                          <span className="small text-muted text-uppercase">{item.status}</span>
                        </div>
                        <div className="progress mb-2">
                          <div className="progress-bar" style={{ width: `${item.progress}%` }}>
                            {item.progress}%
                          </div>
                        </div>
                        {item.documentId && <div className="small text-muted">Document ID: {item.documentId}</div>}
                        {item.error && <div className="small text-danger">{item.error}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {overallStatus && (
                <div className="mt-4">
                  <div className="alert alert-info mb-0">
                    {overallStatus}
                  </div>
                </div>
              )}

              {uploadItems.some((item) => item.status === 'uploading') && (
                <div className="mt-3">
                  <small className="text-muted">Uploading sequentially, one file at a time...</small>
                </div>
              )}

              {uploadItems.length > 0 && uploadItems.every((item) => item.status !== 'pending' && item.status !== 'uploading') && (
                <div className="mt-3">
                  <small className="text-muted">All selected files have finished uploading.</small>
                </div>
              )}

              {uploadItems.length > 0 && uploading && (
                <div className="mt-3">
                  <div className="progress">
                    <div
                      className="progress-bar progress-bar-striped progress-bar-animated"
                      style={{
                        width: `${Math.round(uploadItems.reduce((acc, item) => acc + item.progress, 0) / uploadItems.length)}%`,
                      }}
                    >
                      {Math.round(uploadItems.reduce((acc, item) => acc + item.progress, 0) / uploadItems.length)}%
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="card mt-4">
          <div className="card-header d-flex justify-content-between align-items-center">
            <span className="fw-semibold">Documents Table</span>
            <button
              type="button"
              className="btn btn-outline-secondary btn-sm"
              onClick={() => {
                if (projectId) {
                  void loadRegistry(projectId)
                }
              }}
            >
              Refresh
            </button>
          </div>
          <div className="card-body">
            <div className="row g-2 mb-3">
              <div className="col-12 col-md-3">
                <label className="form-label form-label-sm mb-1">Status</label>
                <select className="form-select form-select-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  {statusOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt === 'all' ? 'All' : opt}</option>
                  ))}
                </select>
              </div>
              <div className="col-12 col-md-3">
                <label className="form-label form-label-sm mb-1">Document Type</label>
                <select className="form-select form-select-sm" value={docTypeFilter} onChange={(e) => setDocTypeFilter(e.target.value)}>
                  {docTypeOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt === 'all' ? 'All' : opt}</option>
                  ))}
                </select>
              </div>
              <div className="col-12 col-md-6">
                <label className="form-label form-label-sm mb-1">Submitter</label>
                <select className="form-select form-select-sm" value={submitterFilter} onChange={(e) => setSubmitterFilter(e.target.value)}>
                  {submitterOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt === 'all' ? 'All' : opt}</option>
                  ))}
                </select>
              </div>
              <div className="col-12">
                <button
                  type="button"
                  className="btn btn-outline-secondary btn-sm"
                  onClick={() => {
                    setStatusFilter('all')
                    setDocTypeFilter('all')
                    setSubmitterFilter('all')
                  }}
                >
                  Reset
                </button>
              </div>
            </div>

            {registryError && <div className="alert alert-danger">{registryError}</div>}
            {registryLoading ? (
              <div className="spinner-border" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            ) : !projectId ? (
              <p className="text-muted mb-0">Please select a project to view documents.</p>
            ) : filteredRegistryItems.length === 0 ? (
              <p className="text-muted mb-0">No documents match the selected filters.</p>
            ) : (
              <div className="table-responsive">
                <table className="table table-bordered align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Document</th>
                      <th>Project</th>
                      <th>Status</th>
                      <th>Document Type</th>
                      <th>Submitter</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRegistryItems.map((doc) => (
                      <tr key={doc.doc_id}>
                        <td>
                          <a href={`/documents/${doc.doc_id}/detail`} style={{ color: '#2563eb', fontWeight: 500 }}>
                            {doc.title}
                          </a>
                        </td>
                        <td>{doc.project_name || '—'}</td>
                        <td>{doc.status || '—'}</td>
                        <td>{doc.doc_type || '—'}</td>
                        <td>{doc.submitter_name || '—'}</td>
                        <td>{doc.updated_at ? new Date(doc.updated_at).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
