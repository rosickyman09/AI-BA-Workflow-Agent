import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser, type AuthUser } from '@/services/auth'
import {
  approveWorkflow,
  getDocumentDetail,
  rejectWorkflow,
  returnWorkflow,
  resubmitDocument,
  type DocumentDetail,
} from '@/services/documents'
import 'bootstrap/dist/css/bootstrap.min.css'

// ─── helpers ─────────────────────────────────────────────────────────────────

function statusBadge(status: string) {
  const map: Record<string, string> = {
    approved: 'bg-success',
    rejected: 'bg-danger',
    returned: 'bg-warning text-dark',
    returned_to_submitter: 'bg-warning text-dark',
    returned_to_step1: 'bg-warning text-dark',
    in_progress: 'bg-primary',
    human_review_required: 'bg-secondary',
    pending_approval: 'bg-info text-dark',
  }
  const cls = map[status] || 'bg-light text-dark'
  return <span className={`badge ${cls}`}>{status.replace(/_/g, ' ')}</span>
}

function actionDot(action: string) {
  const colors: Record<string, string> = {
    submitted: '#0d6efd',
    resubmitted: '#0d6efd',
    approved: '#198754',
    rejected: '#dc3545',
    returned: '#fd7e14',
  }
  return (
    <span
      style={{
        display: 'inline-block',
        width: 12,
        height: 12,
        borderRadius: '50%',
        backgroundColor: colors[action] || '#6c757d',
        marginRight: 8,
        flexShrink: 0,
      }}
    />
  )
}

function normalizeUTC(iso: string): string {
  if (!iso.endsWith('Z') && !iso.includes('+')) return iso + 'Z'
  return iso
}

function formatDateTime(iso?: string | null) {
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

function isEditable(mimeType?: string | null) {
  const mt = (mimeType || '').toLowerCase()
  return (
    mt.includes('document') ||
    mt.includes('spreadsheet') ||
    mt.includes('presentation') ||
    mt.includes('word') ||
    mt.includes('excel') ||
    mt.includes('powerpoint')
  )
}

// ─────────────────────────────────────────────────────────────────────────────

export default function DocumentDetailPage() {
  const router = useRouter()
  const { doc_id } = router.query as { doc_id?: string }

  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [comment, setComment] = useState('')
  const [resubmitNotes, setResubmitNotes] = useState('')
  const [actionMode, setActionMode] = useState<'reject' | 'return' | null>(null)
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
      setCurrentUser(user)
    }
    void bootstrap()
  }, [])

  useEffect(() => {
    if (!doc_id) return
    void loadDetail(doc_id)
  }, [doc_id])

  const loadDetail = async (id: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await getDocumentDetail(id)
      setDetail(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  // ── action handlers ────────────────────────────────────────────────────────

  const handleApprove = async () => {
    if (!detail?.workflow?.workflow_id) return
    setActionLoading(true)
    setError('')
    try {
      await approveWorkflow(detail.workflow.workflow_id, comment)
      setSuccessMsg('Document approved successfully.')
      setComment('')
      setActionMode(null)
      await loadDetail(doc_id!)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Approve failed')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!detail?.workflow?.workflow_id) return
    const reason = comment.trim()
    if (!reason) { setError('Rejection reason is required'); return }
    setActionLoading(true)
    setError('')
    try {
      await rejectWorkflow(detail.workflow.workflow_id, reason)
      setSuccessMsg('Document rejected.')
      setComment('')
      setActionMode(null)
      await loadDetail(doc_id!)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Reject failed')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReturn = async () => {
    if (!detail?.workflow?.workflow_id) return
    const msg = comment.trim()
    if (!msg) { setError('Comment is required when returning a document'); return }
    setActionLoading(true)
    setError('')
    try {
      await returnWorkflow(detail.workflow.workflow_id, msg)
      setSuccessMsg('Document returned.')
      setComment('')
      setActionMode(null)
      await loadDetail(doc_id!)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Return failed')
    } finally {
      setActionLoading(false)
    }
  }

  const handleResubmit = async () => {
    if (!doc_id) return
    setActionLoading(true)
    setError('')
    try {
      await resubmitDocument(doc_id, resubmitNotes.trim() || undefined)
      setSuccessMsg('Document resubmitted for review.')
      setResubmitNotes('')
      await loadDetail(doc_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Resubmit failed')
    } finally {
      setActionLoading(false)
    }
  }

  // ── role/status checks ─────────────────────────────────────────────────────

  const wf = detail?.workflow
  const normalizedRole = (currentUser?.role || '').trim().toLowerCase()
  const normalizedStep1Role = (wf?.step_1_role || '').trim().toLowerCase()
  const userId = currentUser?.user_id || ''

  const isApproverStep1 = wf?.current_step === 1 && normalizedStep1Role === normalizedRole && wf?.status === 'in_progress'
  const isAdminApprover = normalizedRole === 'admin' && normalizedStep1Role === 'admin' && wf?.current_step === 1 && wf?.status === 'in_progress'
  const isCurrentApprover = isApproverStep1 || isAdminApprover

  const isSubmitter = String(wf?.submitter_id) === String(userId) || String(detail?.submitter_id) === String(userId)
  const isReturnedToSubmitter = wf?.status === 'returned_to_submitter'
  // Also show for admins reviewing a returned doc, or if user is the document creator
  const showSubmitterReturnPanel = (isSubmitter || normalizedRole === 'admin') && isReturnedToSubmitter

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <Layout>
      <div className="container mt-4" style={{ maxWidth: 900 }}>

        {/* Back */}
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.back()}>
          ← Back
        </button>

        {loading && (
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading…</span>
          </div>
        )}

        {error && (
          <div className="alert alert-danger alert-dismissible">
            {error}
            <button type="button" className="btn-close" onClick={() => setError('')} />
          </div>
        )}

        {successMsg && (
          <div className="alert alert-success alert-dismissible">
            {successMsg}
            <button type="button" className="btn-close" onClick={() => setSuccessMsg('')} />
          </div>
        )}

        {!loading && detail && (
          <>
            {/* ── Section 1: Header ─────────────────────────────────── */}
            <div className="mb-4">
              <div className="d-flex align-items-center gap-3 flex-wrap">
                <h2 className="mb-0">{detail.title}</h2>
                {statusBadge(wf?.status || detail.status)}
              </div>
              <div className="text-muted mt-2 small">
                <span className="me-3">
                  <strong>Project:</strong> {detail.project_name || '—'}
                </span>
                <span className="me-3">
                  <strong>Submitted by:</strong> {detail.submitter_name || '—'}
                  {detail.submitter_role && (
                    <span className="badge bg-secondary ms-1">{detail.submitter_role}</span>
                  )}
                </span>
                <span>
                  <strong>Date:</strong> {formatDateTime(detail.created_at)}
                </span>
              </div>
              {wf && (
                <div className="text-muted mt-1 small">
                  {wf.step_1_role && <span>Required approver: <em>{wf.step_1_role}</em></span>}
                </div>
              )}
            </div>

            {/* ── Section 2: File Access ────────────────────────────── */}
            {(detail.google_drive_link || detail.edit_url) && (
              <div className="card mb-4">
                <div className="card-body">
                  <h5 className="card-title">File Access</h5>
                  {isEditable(detail.file_mime_type) && detail.edit_url ? (
                    <a
                      href={detail.edit_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-outline-primary me-2"
                    >
                      ✏️ Edit in Google Drive
                    </a>
                  ) : (
                    detail.google_drive_link && (
                      <a
                        href={detail.google_drive_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline-secondary me-2"
                      >
                        📄 View File
                      </a>
                    )
                  )}
                  {!isEditable(detail.file_mime_type) && detail.google_drive_link && (
                    <div className="alert alert-warning mt-3 mb-0 small">
                      ⚠️ This file cannot be edited directly. Please add comments below.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Section 2b: Submission Notes ─────────────────────── */}
            {detail.submission_notes && (
              <div className="card mb-4">
                <div className="card-body">
                  <h5 className="card-title">Submission Notes</h5>
                  <p className="mb-0" style={{ color: '#374151' }}>{detail.submission_notes}</p>
                </div>
              </div>
            )}

            {/* ── Section 3: Action Panel ───────────────────────────── */}

            {/* A: Approver Panel */}
            {isCurrentApprover && !showSubmitterReturnPanel && (
              <div className="card mb-4 border-primary">
                <div className="card-body">
                  <h5 className="card-title text-primary">
                    Your Action Required – Step {wf!.current_step}
                  </h5>
                  <textarea
                    className="form-control mb-3"
                    rows={3}
                    placeholder="Comment (required for Reject / Return, optional for Approve)"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    disabled={actionLoading}
                  />
                  <div className="d-flex gap-2 flex-wrap">
                    <button
                      className="btn btn-success"
                      disabled={actionLoading}
                      onClick={() => void handleApprove()}
                    >
                      ✅ Approve
                    </button>
                    <button
                      className={`btn ${actionMode === 'reject' ? 'btn-danger' : 'btn-outline-danger'}`}
                      disabled={actionLoading}
                      onClick={() => setActionMode(actionMode === 'reject' ? null : 'reject')}
                    >
                      ❌ Reject
                    </button>
                    <button
                      className={`btn ${actionMode === 'return' ? 'btn-warning' : 'btn-outline-warning'}`}
                      disabled={actionLoading}
                      onClick={() => setActionMode(actionMode === 'return' ? null : 'return')}
                    >
                      ↩️ Return
                    </button>
                  </div>

                  {actionMode === 'reject' && (
                    <div className="mt-3">
                      <button
                        className="btn btn-danger"
                        disabled={actionLoading || !comment.trim()}
                        onClick={() => void handleReject()}
                      >
                        Confirm Reject
                      </button>
                    </div>
                  )}
                  {actionMode === 'return' && (
                    <div className="mt-3">
                      <button
                        className="btn btn-warning"
                        disabled={actionLoading || !comment.trim()}
                        onClick={() => void handleReturn()}
                      >
                        Confirm Return
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* B: Submitter Returned Panel */}
            {showSubmitterReturnPanel && (
              <div className="card mb-4 border-warning">
                <div className="card-body">
                  <h5 className="card-title text-warning">⚠️ This document was returned</h5>
                  {(() => {
                    const latestReturn = detail.history.find((h) => h.action === 'returned')
                    const returnComment = latestReturn?.comment
                    return returnComment ? (
                      <div className="alert alert-warning mb-3">
                        <strong>Return reason:</strong> {returnComment}
                      </div>
                    ) : (
                      <div className="alert alert-warning mb-3 text-muted fst-italic">
                        (No return reason was provided)
                      </div>
                    )
                  })()}
                  <p className="text-muted small mb-3">Steps to resubmit:</p>
                  <ol className="small">
                    <li>Click <strong>Edit in Google Drive</strong> to modify the document</li>
                    <li>Save your changes in Google Drive</li>
                    <li>Click <strong>Resubmit for Review</strong> when ready</li>
                  </ol>
                  <div className="mb-3">
                    <label className="form-label small fw-semibold">
                      Response / Review Notes <span className="text-muted fw-normal">(optional)</span>
                    </label>
                    <textarea
                      className="form-control form-control-sm"
                      rows={3}
                      placeholder="Describe what changes you made or respond to the reviewer's comments…"
                      value={resubmitNotes}
                      onChange={(e) => setResubmitNotes(e.target.value)}
                      disabled={actionLoading}
                    />
                  </div>
                  <div className="d-flex gap-2 flex-wrap">
                    {detail.edit_url && (
                      <a
                        href={detail.edit_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline-primary"
                      >
                        ✏️ Edit in Google Drive
                      </a>
                    )}
                    <button
                      className="btn btn-primary"
                      disabled={actionLoading}
                      onClick={() => void handleResubmit()}
                    >
                      🔄 Resubmit for Review
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* C: Read-only info */}
            {!isCurrentApprover && !showSubmitterReturnPanel && wf && (
              <div className="card mb-4">
                <div className="card-body">
                  <h5 className="card-title">Workflow Status</h5>
                  <p className="text-muted mb-0">
                    {wf.status === 'approved' && '✅ This document has been fully approved.'}
                    {wf.status === 'rejected' && '❌ This document was rejected.'}
                    {wf.status === 'in_progress' && `⏳ Awaiting Step ${wf.current_step} review (${wf.current_step === 1 ? wf.step_1_role : wf.step_2_role}).`}
                    {wf.status === 'human_review_required' && '🔍 This document requires manual human review.'}
                    {wf.status === 'returned_to_step1' && '↩️ Returned to Step 1 reviewer for re-review.'}
                    {!['approved', 'rejected', 'in_progress', 'human_review_required', 'returned_to_step1', 'returned_to_submitter'].includes(wf.status) && wf.status.replace(/_/g, ' ')}
                  </p>
                </div>
              </div>
            )}

            {/* ── Section 4: History Timeline ───────────────────────── */}
            <div className="card mb-4">
              <div className="card-body">
                <h5 className="card-title">Approval History</h5>
                {detail.history.length === 0 ? (
                  <p className="text-muted mb-0">No history yet.</p>
                ) : (
                  <ul className="list-unstyled mb-0">
                    {detail.history.map((entry, idx) => (
                      <li key={idx} className="d-flex align-items-start mb-3">
                        <span style={{ marginTop: 4 }}>{actionDot(entry.action)}</span>
                        <div>
                          <div className="small text-muted">{formatDateTime(entry.created_at)}</div>
                          <div>
                            <strong>{entry.actor_name || 'System'}</strong>
                            {entry.actor_role && (
                              <span className="badge bg-secondary ms-1 small">{entry.actor_role}</span>
                            )}
                            {' – '}
                            <span className="text-capitalize">{entry.action}</span>
                            {entry.step != null && <span className="text-muted"> (Step {entry.step})</span>}
                          </div>
                          {entry.comment && (
                            <div className="text-muted small mt-1" style={{ fontStyle: 'italic' }}>
                              &ldquo;{entry.comment}&rdquo;
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
