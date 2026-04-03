import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import 'bootstrap/dist/css/bootstrap.min.css'

const ROLES = ['admin', 'ba', 'pm', 'business_owner', 'legal', 'finance', 'it', 'tech_lead', 'viewer'] as const
type Role = typeof ROLES[number]

const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  ba: 'Business Analyst',
  pm: 'Project Manager',
  business_owner: 'Business Owner',
  legal: 'Legal',
  finance: 'Finance',
  it: 'IT',
  tech_lead: 'Tech Lead',
  viewer: 'Viewer',
}

interface AppUser {
  user_id: string
  email: string
  role: Role
  full_name: string | null
  is_active: boolean
  created_at: string | null
}

interface CreateForm {
  email: string
  full_name: string
  password: string
  role: Role
}

interface EditForm {
  full_name: string
  role: Role
  password: string
}

const emptyCreate: CreateForm = { email: '', full_name: '', password: '', role: 'ba' }
const emptyEdit: EditForm = { full_name: '', role: 'ba', password: '' }

export default function SetupPage() {
  const router = useRouter()
  const [currentUser, setCurrentUser] = useState<{ role?: string } | null>(null)
  const [users, setUsers] = useState<AppUser[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Create modal
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreate)
  const [createError, setCreateError] = useState('')
  const [createLoading, setCreateLoading] = useState(false)

  // Edit modal
  const [editTarget, setEditTarget] = useState<AppUser | null>(null)
  const [editForm, setEditForm] = useState<EditForm>(emptyEdit)
  const [editError, setEditError] = useState('')
  const [editLoading, setEditLoading] = useState(false)

  // Status toggle loading
  const [statusLoadingId, setStatusLoadingId] = useState('')

  const flash = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(''), 3500)
  }

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/admin/users')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.message || 'Failed to load users')
      }
      const data: AppUser[] = await res.json()
      setUsers(data)
    } catch (e: any) {
      setError(e.message || 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      const user = await getCurrentUser()
      if (!user) {
        router.push('/login')
        return
      }
      const normalizedRole = (user.role || '').trim().toLowerCase()
      console.debug('[Setup] current user role:', user.role)
      if (normalizedRole !== 'admin') {
        router.push('/')
        return
      }
      setCurrentUser(user)
      await fetchUsers()
    }
    void init()
  }, [router, fetchUsers])

  // --- Create User ---
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError('')
    if (!createForm.email || !createForm.password) {
      setCreateError('Email and password are required.')
      return
    }
    if (createForm.password.length < 8) {
      setCreateError('Password must be at least 8 characters.')
      return
    }
    setCreateLoading(true)
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm),
      })
      const body = await res.json()
      if (!res.ok) throw new Error(body.message || 'Failed to create user')
      setShowCreate(false)
      setCreateForm(emptyCreate)
      flash(`User "${createForm.email}" created successfully.`)
      await fetchUsers()
    } catch (e: any) {
      setCreateError(e.message)
    } finally {
      setCreateLoading(false)
    }
  }

  // --- Edit User ---
  const openEdit = (user: AppUser) => {
    setEditTarget(user)
    setEditForm({ full_name: user.full_name || '', role: user.role, password: '' })
    setEditError('')
  }

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editTarget) return
    setEditError('')
    if (editForm.password && editForm.password.length < 8) {
      setEditError('Password must be at least 8 characters.')
      return
    }
    setEditLoading(true)
    const payload: Record<string, string> = {
      full_name: editForm.full_name,
      role: editForm.role,
    }
    if (editForm.password) payload.password = editForm.password
    try {
      const res = await fetch(`/api/admin/users/${editTarget.user_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const body = await res.json()
      if (!res.ok) throw new Error(body.message || 'Failed to update user')
      setEditTarget(null)
      flash(`User "${editTarget.email}" updated successfully.`)
      await fetchUsers()
    } catch (e: any) {
      setEditError(e.message)
    } finally {
      setEditLoading(false)
    }
  }

  // --- Toggle status ---
  const handleToggleStatus = async (user: AppUser) => {
    const action = user.is_active ? 'deactivate' : 'activate'
    setStatusLoadingId(user.user_id)
    try {
      const res = await fetch(`/api/admin/users/${user.user_id}/${action}`, { method: 'PATCH' })
      const body = await res.json()
      if (!res.ok) throw new Error(body.message || 'Failed to update status')
      flash(`User "${user.email}" ${action}d.`)
      await fetchUsers()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setStatusLoadingId('')
    }
  }

  if (!currentUser) return null

  return (
    <Layout>
      <div className="container-fluid py-4" style={{ maxWidth: 1100 }}>
        {/* Header */}
        <div className="d-flex align-items-center justify-content-between mb-4">
          <div>
            <h2 className="fw-bold mb-1" style={{ color: '#1a1a2e' }}>
              ⚙️ Setup
            </h2>
            <p className="text-muted mb-0">Manage user accounts and access roles</p>
          </div>
          <button
            className="btn btn-primary px-4"
            onClick={() => { setShowCreate(true); setCreateError('') }}
          >
            + Create User
          </button>
        </div>

        {/* Alerts */}
        {successMsg && (
          <div className="alert alert-success alert-dismissible" role="alert">
            {successMsg}
            <button className="btn-close" onClick={() => setSuccessMsg('')} />
          </div>
        )}
        {error && (
          <div className="alert alert-danger alert-dismissible" role="alert">
            {error}
            <button className="btn-close" onClick={() => setError('')} />
          </div>
        )}

        {/* Users Table */}
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white border-bottom d-flex align-items-center gap-2">
            <span className="fw-semibold">👥 User Accounts</span>
            <span className="badge bg-secondary ms-1">{users.length}</span>
            <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={fetchUsers}>
              🔄 Refresh
            </button>
          </div>
          <div className="card-body p-0">
            {loading ? (
              <div className="text-center py-5 text-muted">Loading users…</div>
            ) : (
              <div className="table-responsive">
                <table className="table table-hover mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Full Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th className="text-end">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center py-4 text-muted">No users found.</td>
                      </tr>
                    ) : (
                      users.map((u) => {
                        const normalizedRowRole = (u.role || '').trim().toLowerCase()
                        return (
                        <tr key={u.user_id}>
                          <td className="fw-semibold align-middle">
                            {u.full_name || <span className="text-muted fst-italic">—</span>}
                          </td>
                          <td className="align-middle text-muted" style={{ fontSize: 13 }}>{u.email}</td>
                          <td className="align-middle">
                            <span
                              className="badge"
                              style={{
                                background: normalizedRowRole === 'admin' ? '#1a1a2e' : '#e0e7ff',
                                color: normalizedRowRole === 'admin' ? '#fff' : '#3730a3',
                                fontSize: 11,
                              }}
                            >
                              {ROLE_LABELS[u.role] || u.role}
                            </span>
                          </td>
                          <td className="align-middle">
                            {u.is_active ? (
                              <span className="badge bg-success">Active</span>
                            ) : (
                              <span className="badge bg-secondary">Inactive</span>
                            )}
                          </td>
                          <td className="align-middle text-muted" style={{ fontSize: 12 }}>
                            {u.created_at
                              ? new Date(u.created_at).toLocaleDateString()
                              : '—'}
                          </td>
                          <td className="align-middle text-end">
                            <button
                              className="btn btn-sm btn-outline-primary me-1"
                              onClick={() => openEdit(u)}
                            >
                              ✏️ Edit
                            </button>
                            <button
                              className={`btn btn-sm ${u.is_active ? 'btn-outline-warning' : 'btn-outline-success'}`}
                              disabled={statusLoadingId === u.user_id}
                              onClick={() => handleToggleStatus(u)}
                            >
                              {statusLoadingId === u.user_id
                                ? '…'
                                : u.is_active
                                ? '🚫 Deactivate'
                                : '✅ Activate'}
                            </button>
                          </td>
                        </tr>
                      )})
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Role Reference Card */}
        <div className="card shadow-sm border-0 mt-4">
          <div className="card-header bg-white border-bottom">
            <span className="fw-semibold">🔑 Role Reference</span>
          </div>
          <div className="card-body">
            <div className="row g-2">
              {ROLES.map((r) => (
                <div key={r} className="col-md-4 col-lg-3">
                  <div className="p-2 rounded border" style={{ background: '#f8faff' }}>
                    <span
                      className="badge me-2"
                      style={{
                        background: r === 'admin' ? '#1a1a2e' : '#e0e7ff',
                        color: r === 'admin' ? '#fff' : '#3730a3',
                        fontSize: 10,
                      }}
                    >
                      {r}
                    </span>
                    <span style={{ fontSize: 13 }}>{ROLE_LABELS[r]}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ===== Create User Modal ===== */}
      {showCreate && (
        <div
          className="modal d-block"
          style={{ background: 'rgba(0,0,0,0.45)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowCreate(false) }}
        >
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title fw-bold">Create New User</h5>
                <button className="btn-close" onClick={() => setShowCreate(false)} />
              </div>
              <form onSubmit={handleCreateSubmit}>
                <div className="modal-body">
                  {createError && <div className="alert alert-danger py-2">{createError}</div>}
                  <div className="mb-3">
                    <label className="form-label fw-semibold">Full Name</label>
                    <input
                      className="form-control"
                      value={createForm.full_name}
                      onChange={(e) => setCreateForm((f) => ({ ...f, full_name: e.target.value }))}
                      placeholder="e.g. Jane Smith"
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label fw-semibold">
                      Email <span className="text-danger">*</span>
                    </label>
                    <input
                      className="form-control"
                      type="email"
                      value={createForm.email}
                      onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                      placeholder="user@example.com"
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label fw-semibold">
                      Password <span className="text-danger">*</span>
                    </label>
                    <input
                      className="form-control"
                      type="password"
                      value={createForm.password}
                      onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                      placeholder="Min. 8 characters"
                      required
                    />
                  </div>
                  <div className="mb-1">
                    <label className="form-label fw-semibold">Role</label>
                    <select
                      className="form-select"
                      value={createForm.role}
                      onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value as Role }))}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r]} ({r})</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setShowCreate(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={createLoading}>
                    {createLoading ? 'Creating…' : 'Create User'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ===== Edit User Modal ===== */}
      {editTarget && (
        <div
          className="modal d-block"
          style={{ background: 'rgba(0,0,0,0.45)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setEditTarget(null) }}
        >
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title fw-bold">Edit User</h5>
                <button className="btn-close" onClick={() => setEditTarget(null)} />
              </div>
              <form onSubmit={handleEditSubmit}>
                <div className="modal-body">
                  {editError && <div className="alert alert-danger py-2">{editError}</div>}
                  <p className="text-muted mb-3" style={{ fontSize: 13 }}>
                    Editing: <strong>{editTarget.email}</strong>
                  </p>
                  <div className="mb-3">
                    <label className="form-label fw-semibold">Full Name</label>
                    <input
                      className="form-control"
                      value={editForm.full_name}
                      onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                      placeholder="Full name"
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label fw-semibold">Role</label>
                    <select
                      className="form-select"
                      value={editForm.role}
                      onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value as Role }))}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r]} ({r})</option>
                      ))}
                    </select>
                  </div>
                  <div className="mb-1">
                    <label className="form-label fw-semibold">
                      Reset Password{' '}
                      <span className="text-muted fw-normal" style={{ fontSize: 12 }}>(leave blank to keep current)</span>
                    </label>
                    <input
                      className="form-control"
                      type="password"
                      value={editForm.password}
                      onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                      placeholder="New password (min. 8 chars)"
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setEditTarget(null)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={editLoading}>
                    {editLoading ? 'Saving…' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
