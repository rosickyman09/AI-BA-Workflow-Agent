import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import {
  approveWorkflow,
  getApprovals,
  rejectWorkflow,
  returnWorkflow,
  type ApprovalListStatus,
  type PendingApprovalItem,
} from '@/services/documents'
import 'bootstrap/dist/css/bootstrap.min.css'

const REVIEWER_ROLES = new Set(['admin', 'business_owner', 'ba', 'pm', 'legal'])

function normalizeUTC(iso: string): string {
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

type ActionMode = 'reject' | 'return' | 'approve' | null

function statusBadge(a: PendingApprovalItem) {
  const wfStatus = a.status
  const resubmitted = (a.resubmit_count ?? 0) > 0

  if (wfStatus === 'returned_to_submitter' || wfStatus === 'returned') {
    return <span className="badge bg-warning text-dark">↩️ Returned to Submitter</span>
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
  return <span className="badge bg-light text-dark">{wfStatus.replace(/_/g, ' ')}</span>
}

export default function ApprovalsPage() {
  const router = useRouter()
  const [approvals, setApprovals] = useState<PendingApprovalItem[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState('')
  const [error, setError] = useState('')
  const [role, setRole] = useState('')
  const [activeStatus, setActiveStatus] = useState<ApprovalListStatus>('pending')
  const [statusFilter, setStatusFilter] = useState('all')
  const [docTypeFilter, setDocTypeFilter] = useState('all')
  const [projectFilter, setProjectFilter] = useState('all')

  // Per-row comment / reason state
  const [comments, setComments] = useState<Record<string, string>>({})
  // Which action mode is open per row
  const [actionMode, setActionMode] = useState<Record<string, ActionMode>>({})

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
      setRole((user.role || '').trim().toLowerCase())
    }
    void bootstrap()
  }, [])

  useEffect(() => {
    void loadApprovals(activeStatus)
  }, [activeStatus])

  const loadApprovals = async (status: ApprovalListStatus) => {
    setLoading(true)
    setError('')
    try {
      const items = await getApprovals(null, status)
      setApprovals(items)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Unable to load approvals')
    } finally {
      setLoading(false)
    }
  }

  const normalizedRole = (role || '').trim().toLowerCase()
  const canDecide = REVIEWER_ROLES.has(normalizedRole)
  const statusOptions = useMemo(
    () => ['all', ...Array.from(new Set(approvals.map((a) => a.status).filter(Boolean)))],
    [approvals]
  )
  const docTypeOptions = useMemo(
    () => ['all', ...Array.from(new Set(approvals.map((a) => (a.doc_type || '').trim()).filter(Boolean)))],
    [approvals]
  )
  const projectOptions = useMemo(
    () => ['all', ...Array.from(new Set(approvals.map((a) => (a.project_name || '').trim()).filter(Boolean)))],
    [approvals]
  )
  const filteredApprovals = useMemo(() => {
    return approvals.filter((item) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false
      if (docTypeFilter !== 'all' && (item.doc_type || '') !== docTypeFilter) return false
      if (projectFilter !== 'all' && (item.project_name || '') !== projectFilter) return false
      return true
    })
  }, [approvals, statusFilter, docTypeFilter, projectFilter])

  const setComment = (wid: string, val: string) =>
    setComments((prev) => ({ ...prev, [wid]: val }))

  const openAction = (wid: string, mode: ActionMode) =>
    setActionMode((prev) => ({ ...prev, [wid]: prev[wid] === mode ? null : mode }))

  const handleApprove = async (workflowId: string) => {
    setActionLoadingId(workflowId)
    setError('')
    try {
      await approveWorkflow(workflowId, comments[workflowId] || '')
      await loadApprovals(activeStatus)
      setComments((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
      setActionMode((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Approve failed')
    } finally {
      setActionLoadingId('')
    }
  }

  const handleReject = async (workflowId: string) => {
    const reason = (comments[workflowId] || '').trim()
    if (!reason) { setError('Rejection reason is required'); return }
    setActionLoadingId(workflowId)
    setError('')
    try {
      await rejectWorkflow(workflowId, reason)
      await loadApprovals(activeStatus)
      setComments((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
      setActionMode((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Reject failed')
    } finally {
      setActionLoadingId('')
    }
  }

  const handleReturn = async (workflowId: string) => {
    const comment = (comments[workflowId] || '').trim()
    if (!comment) { setError('Comment is required when returning a document'); return }
    setActionLoadingId(workflowId)
    setError('')
    try {
      await returnWorkflow(workflowId, comment)
      await loadApprovals(activeStatus)
      setComments((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
      setActionMode((prev) => { const n = { ...prev }; delete n[workflowId]; return n })
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Return failed')
    } finally {
      setActionLoadingId('')
    }
  }

  return (
    <Layout>
      <div className="container mt-4">
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.back()}>
          ← Back
        </button>
        <h1>Approvals</h1>

        <div className="mb-3">
          <div className="btn-group" role="group">
            {(['pending', 'completed', 'all'] as ApprovalListStatus[]).map((s) => (
              <button
                key={s}
                type="button"
                className={`btn ${activeStatus === s ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setActiveStatus(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
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

        {error && <div className="alert alert-danger alert-dismissible">
          {error}
          <button type="button" className="btn-close" onClick={() => setError('')} />
        </div>}

        {loading ? (
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading…</span>
          </div>
        ) : filteredApprovals.length === 0 ? (
          <p className="text-muted">
            No approvals match the selected filters.
          </p>
        ) : (
          <div className="table-responsive">
            <table className="table table-bordered align-middle">
              <thead className="table-light">
                <tr>
                  <th>Project</th>
                  <th>Document</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Required Role</th>
                  {canDecide && activeStatus !== 'completed' && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredApprovals.map((a) => {
                  const isBusy = actionLoadingId === a.workflow_id || actionLoadingId === a.doc_id
                  const mode = actionMode[a.workflow_id] ?? null

                  return (
                    <tr
                      key={a.workflow_id}
                      className={isBusy ? 'opacity-50' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => router.push(`/documents/${a.doc_id}/detail`)}
                    >                      {/* Project column */}
                      <td className="small">{a.project_name || '—'}</td>

                      {/* Document column */}
                      <td onClick={(e) => e.stopPropagation()}>
                        <a href={`/documents/${a.doc_id}/detail`} style={{ color: '#2563eb', fontWeight: 500 }}>
                          {a.doc_title || a.doc_id.slice(0, 8)}
                        </a>
                        {a.google_drive_link && (
                          <a
                            href={a.google_drive_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ms-2 small text-muted"
                          >
                            [Drive]
                          </a>
                        )}
                        {a.submission_notes && (
                          <div className="small text-muted fst-italic mt-1">
                            Note: {a.submission_notes}
                          </div>
                        )}
                      </td>

                      {/* Status badge */}
                      <td>{statusBadge(a)}</td>

                      {/* Submitted */}
                      <td className="small text-nowrap">
                        {a.submitted_at ? new Date(normalizeUTC(a.submitted_at)).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Hong_Kong' }) : '—'}
                      </td>

                      {/* Required role */}
                      <td>
                        {a.step_1_role && <div className="small text-muted">{a.step_1_role}</div>}
                      </td>

                      {/* Actions */}
                      {canDecide && activeStatus !== 'completed' && (
                        <td style={{ minWidth: 260 }} onClick={(e) => e.stopPropagation()}>
                          <>
                              {/* Primary action row */}
                              <div className="d-flex gap-1 flex-wrap mb-1">
                                <button
                                  className={`btn btn-sm ${mode === 'approve' ? 'btn-success' : 'btn-outline-success'}`}
                                  disabled={isBusy}
                                  onClick={() => openAction(a.workflow_id, 'approve')}
                                >
                                  Approve
                                </button>
                                <button
                                  className={`btn btn-sm ${mode === 'reject' ? 'btn-danger' : 'btn-outline-danger'}`}
                                  disabled={isBusy}
                                  onClick={() => openAction(a.workflow_id, 'reject')}
                                >
                                  Reject
                                </button>
                                <button
                                  className={`btn btn-sm ${mode === 'return' ? 'btn-warning' : 'btn-outline-warning'}`}
                                  disabled={isBusy}
                                  onClick={() => openAction(a.workflow_id, 'return')}
                                >
                                  Return
                                </button>
                              </div>

                              {/* Inline comment box for approve / reject / return */}
                              {mode && (
                                <div className="mt-1">
                                  <textarea
                                    className="form-control form-control-sm mb-1"
                                    rows={2}
                                    placeholder={
                                      mode === 'approve'
                                        ? 'Approval comment (optional)'
                                        : mode === 'reject'
                                        ? 'Rejection reason (required)'
                                        : 'Return comment (required)'
                                    }
                                    value={comments[a.workflow_id] || ''}
                                    onChange={(e) => setComment(a.workflow_id, e.target.value)}
                                  />
                                  <div className="d-flex gap-1">
                                    <button
                                      className={`btn btn-sm ${mode === 'approve' ? 'btn-success' : mode === 'reject' ? 'btn-danger' : 'btn-warning'}`}
                                      disabled={
                                        isBusy ||
                                        (mode !== 'approve' && !(comments[a.workflow_id] || '').trim())
                                      }
                                      onClick={() =>
                                        void (mode === 'approve'
                                          ? handleApprove(a.workflow_id)
                                          : mode === 'reject'
                                          ? handleReject(a.workflow_id)
                                          : handleReturn(a.workflow_id))
                                      }
                                    >
                                      Confirm {mode}
                                    </button>
                                    <button
                                      className="btn btn-sm btn-outline-secondary"
                                      onClick={() => openAction(a.workflow_id, mode)}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                </div>
                              )}
                          </>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  )
}
