import React, { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/router'
import Layout from '@/components/Layout'
import { getCurrentUser } from '@/services/auth'
import { createProject, listProjects, type ProjectItem } from '@/services/projects'
import 'bootstrap/dist/css/bootstrap.min.css'

export default function ProjectsPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [currentRole, setCurrentRole] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive' | 'frozen' | 'completed'>('active')
  const normalizedRole = (currentRole || '').trim().toLowerCase()

  const canCreateProject = useMemo(
    () => ['admin', 'ba', 'business_owner'].includes(normalizedRole),
    [normalizedRole]
  )
  const filteredProjects = useMemo(() => {
    if (statusFilter === 'all') {
      return projects
    }
    return projects.filter((project) => {
      const normalizedStatus = (project.status || 'active').trim().toLowerCase()
      return normalizedStatus === statusFilter
    })
  }, [projects, statusFilter])

  const statusBadgeClass = (status: string) => {
    const normalizedStatus = (status || 'active').trim().toLowerCase()
    if (normalizedStatus === 'active') {
      return 'success'
    }
    if (normalizedStatus === 'completed') {
      return 'primary'
    }
    if (normalizedStatus === 'inactive') {
      return 'secondary'
    }
    if (normalizedStatus === 'frozen') {
      return 'dark'
    }
    return 'secondary'
  }

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (!user) {
        window.location.href = '/login'
        return
      }
      setCurrentRole((user.role || '').trim().toLowerCase())
      await loadProjects()
    }
    void bootstrap()
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    setError('')
    try {
      const items = await listProjects()
      setProjects(items)
    } catch (err: any) {
      setError(err.response?.data?.message || 'Unable to load projects')
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!newName.trim()) {
      setError('Project name is required')
      return
    }

    setSubmitting(true)
    setError('')
    try {
      await createProject(newName.trim(), newDescription.trim())
      setShowCreateModal(false)
      setNewName('')
      setNewDescription('')
      await loadProjects()
    } catch (err: any) {
      setError(err.response?.data?.message || 'Create project failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="container mt-4">
        <button type="button" className="btn btn-outline-secondary mb-3" onClick={() => router.back()}>
          ← Back
        </button>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1 className="mb-0">Projects</h1>
          {canCreateProject && (
            <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
              Create Project
            </button>
          )}
        </div>

        <div className="card mb-3">
          <div className="card-body py-2">
            <div className="d-flex flex-wrap gap-2 align-items-center">
              <span className="fw-semibold">Filter:</span>
              <select
                className="form-select form-select-sm"
                style={{ width: 180 }}
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as 'all' | 'active' | 'inactive' | 'frozen' | 'completed')
                }
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="frozen">Frozen</option>
                <option value="completed">Completed</option>
              </select>
              <button
                type="button"
                className="btn btn-outline-secondary btn-sm"
                onClick={() => setStatusFilter('active')}
              >
                Reset
              </button>
            </div>
          </div>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {loading ? (
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        ) : filteredProjects.length === 0 ? (
          <p className="text-muted">No projects found.</p>
        ) : (
          <div className="row g-3">
            {filteredProjects.map((project) => (
              <div key={project.project_id} className="col-12 col-md-6 col-lg-4">
                <div
                  className="card h-100"
                  style={{ cursor: 'pointer' }}
                  onClick={() => router.push(`/projects/${project.project_id}/documents`)}
                >
                  <div className="card-body d-flex flex-column">
                    <div className="d-flex justify-content-between align-items-start gap-2 mb-2">
                      <h5 className="card-title mb-0">{project.name}</h5>
                    </div>

                    <p className="card-text text-muted flex-grow-1">
                      {project.description || 'No description provided.'}
                    </p>

                    <div className="d-flex align-items-center gap-2 mb-2">
                      <span className={`badge bg-${statusBadgeClass(project.status)}`}>
                        {(project.status || 'active').trim().toLowerCase()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="modal d-block" tabIndex={-1} role="dialog" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog" role="document">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">Create Project</h5>
                <button
                  type="button"
                  className="btn-close"
                  aria-label="Close"
                  onClick={() => setShowCreateModal(false)}
                />
              </div>
              <form onSubmit={handleCreateProject}>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Name</label>
                    <input
                      className="form-control"
                      value={newName}
                      onChange={(event) => setNewName(event.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-control"
                      rows={4}
                      value={newDescription}
                      onChange={(event) => setNewDescription(event.target.value)}
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? 'Creating...' : 'Submit'}
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
