import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import { getMySubmissions, resubmitDocument, type MyDocumentItem, type MyDocumentStatus } from '@/services/documents'
import 'bootstrap/dist/css/bootstrap.min.css'

function workflowStatusBadge(item: MyDocumentItem) {
  const wfStatus = item.workflow_status
  const resubmitted = (item.resubmit_count ?? 0) > 0

  if (wfStatus === 'returned_to_submitter') {
    return <span className="badge" style={{ background: '#f97316', color: 'white' }}>↩️ Returned – Action Required</span>
  }
  if (wfStatus === 'approved') {
    return <span className="badge bg-success">✅ Approved</span>
  }
  if (wfStatus === 'rejected') {
    return <span className="badge bg-danger">❌ Rejected</span>
  }
  if (wfStatus === 'in_progress') {
    return resubmitted
      ? <span className="badge" style={{ background: '#7c3aed', color: 'white' }}>🔄 Resubmitted – Awaiting Approval</span>
      : <span className="badge bg-primary">🔵 Awaiting Approval</span>
  }
  if (wfStatus === 'human_review_required') {
    return <span className="badge bg-secondary">Human Review Required</span>
  }
  // Fallback to doc_status
  const docStatus = item.doc_status || ''
  const map: Record<string, string> = {
    pending_approval: 'bg-info text-dark',
    approved: 'bg-success',
    rejected: 'bg-danger',
    returned: 'bg-warning text-dark',
    draft: 'bg-light text-dark',
  }
  return <span className={`badge ${map[docStatus] || 'bg-light text-dark'}`}>{docStatus.replace(/_/g, ' ')}</span>
}

function normalizeUTC(iso: string): string {
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

function formatDate(iso?: string | null) {
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

export default function MyDocumentsPage() {
  const router = useRouter()
  const [docs, setDocs] = useState<MyDocumentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<MyDocumentStatus>('in_progress')
  const [resubmitLoadingId, setResubmitLoadingId] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [docTypeFilter, setDocTypeFilter] = useState('all')
  const [projectFilter, setProjectFilter] = useState('all')

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
    }
    void bootstrap()
  }, [])

  useEffect(() => {
    void loadDocs(activeTab)
  }, [activeTab])

  const loadDocs = async (status: MyDocumentStatus) => {
    setLoading(true)
    setError('')
    try {
      const items = await getMySubmissions(status)
      setDocs(items)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Unable to load documents')
    } finally {
      setLoading(false)
    }
  }

  const handleResubmit = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation()
    setResubmitLoadingId(docId)
    setError('')
    try {
      await resubmitDocument(docId)
      await loadDocs(activeTab)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Resubmit failed')
    } finally {
      setResubmitLoadingId('')
    }
  }

  const tabLabels: Record<MyDocumentStatus, string> = {
    in_progress: 'In Progress',
    completed: 'Completed',
    all: 'All',
  }
  const statusOptions = useMemo(
    () => ['all', ...Array.from(new Set(docs.map((d) => d.workflow_status || d.doc_status).filter(Boolean) as string[]))],
    [docs]
  )
  const docTypeOptions = useMemo(
    () => ['all', ...Array.from(new Set(docs.map((d) => (d.doc_type || '').trim()).filter(Boolean)))],
    [docs]
  )
  const projectOptions = useMemo(
    () => ['all', ...Array.from(new Set(docs.map((d) => (d.project_name || '').trim()).filter(Boolean)))],
    [docs]
  )
  const filteredDocs = useMemo(
    () => docs.filter((doc) => {
      const effectiveStatus = doc.workflow_status || doc.doc_status
      if (statusFilter !== 'all' && effectiveStatus !== statusFilter) return false
      if (docTypeFilter !== 'all' && (doc.doc_type || '') !== docTypeFilter) return false
      if (projectFilter !== 'all' && (doc.project_name || '') !== projectFilter) return false
      return true
    }),
    [docs, statusFilter, docTypeFilter, projectFilter]
  )

  return (
    <Layout>
      <div className="container mt-4">
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.back()}>
          ← Back
        </button>
        <h1>My Documents</h1>

        {/* Tab bar */}
        <div className="btn-group mb-3" role="group">
          {(['in_progress', 'completed', 'all'] as MyDocumentStatus[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-outline-primary'}`}
              onClick={() => setActiveTab(tab)}
            >
              {tabLabels[tab]}
            </button>
          ))}
        </div>

        <div className="card mb-3">
          <div className="card-body py-2">
            <div className="row g-2 align-items-end">
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
              <div className="col-12 col-md-3">
                <label className="form-label form-label-sm mb-1">Project</label>
                <select className="form-select form-select-sm" value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
                  {projectOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt === 'all' ? 'All' : opt}</option>
                  ))}
                </select>
              </div>
              <div className="col-12 col-md-3">
                <button
                  type="button"
                  className="btn btn-outline-secondary btn-sm w-100"
                  onClick={() => {
                    setStatusFilter('all')
                    setDocTypeFilter('all')
                    setProjectFilter('all')
                  }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="alert alert-danger alert-dismissible">
            {error}
            <button type="button" className="btn-close" onClick={() => setError('')} />
          </div>
        )}

        {loading ? (
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading…</span>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="text-center py-5 text-muted">
            <p className="fs-5">No documents match the selected filters</p>
            <button
              type="button"
              className="btn btn-primary mt-2"
              onClick={() => void router.push('/documents')}
            >
              Upload a Document
            </button>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="table table-bordered align-middle">
              <thead className="table-light">
                <tr>
                  <th>Document Name</th>
                  <th>Project</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Last Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => (
                  <tr
                    key={doc.doc_id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => void router.push(`/documents/${doc.doc_id}/detail`)}
                  >
                    <td>
                      <span className="text-primary text-decoration-underline">
                        {doc.title || doc.doc_id.slice(0, 8)}
                      </span>
                    </td>
                    <td>{doc.project_name || '—'}</td>
                    <td>{workflowStatusBadge(doc)}</td>
                    <td>{formatDate(doc.created_at)}</td>
                    <td>{formatDate(doc.updated_at)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {(doc.workflow_status === 'returned_to_submitter' || doc.doc_status === 'returned') && (
                        <button
                          className="btn btn-sm btn-warning"
                          disabled={resubmitLoadingId === doc.doc_id}
                          onClick={(e) => void handleResubmit(e, doc.doc_id)}
                        >
                          {resubmitLoadingId === doc.doc_id ? 'Resubmitting…' : '🔄 Resubmit'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  )
}
