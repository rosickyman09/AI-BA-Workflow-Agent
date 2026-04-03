/**
 * Home Page / Dashboard
 */

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import Layout from '@/components/Layout'
import { getCurrentUser, isAuthenticated } from '@/services/auth'
import { listDocuments } from '@/services/documents'
import { listProjects, type ProjectItem } from '@/services/projects'

interface DashboardProject extends ProjectItem {
  documentCount?: number
}

export default function Home() {
  const router = useRouter()
  const [recentProjects, setRecentProjects] = useState<DashboardProject[]>([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [canGenerateUrs, setCanGenerateUrs] = useState(false)

  useEffect(() => {
    const check = async () => {
      const authenticated = await isAuthenticated()
      if (!authenticated) {
        router.push('/login')
        return
      }
      const user = await getCurrentUser()
      const normalizedRole = (user?.role || '').trim().toLowerCase()
      setCanGenerateUrs(['admin', 'ba', 'pm', 'business_owner'].includes(normalizedRole))

      setProjectsLoading(true)
      try {
        const projects = await listProjects()
        const activeProjects = projects.filter((project) => {
          const normalizedStatus = (project.status || '').trim().toLowerCase()
          return normalizedStatus === 'active' && !project.is_frozen
        })
        // Sort by updated_at descending, take top 4
        const sorted = [...activeProjects].sort((a, b) => {
          const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0
          const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0
          return tb - ta
        })
        const recent = sorted.slice(0, 4)
        const withCounts = await Promise.all(
          recent.map(async (project) => {
            try {
              const docs = await listDocuments(project.project_id)
              return { ...project, documentCount: docs.length }
            } catch {
              return { ...project, documentCount: undefined }
            }
          })
        )
        setRecentProjects(withCounts)
      } catch {
        setRecentProjects([])
      } finally {
        setProjectsLoading(false)
      }
    }
    void check()
  }, [router])

  return (
    <Layout>
      <div className="container mt-5">
        <h1>Welcome to AI BA Workflow Agent</h1>
        <p className="lead">Intelligent document analysis and generation powered by AI</p>

        <div className="mt-4">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h3 className="mb-0">Recent Projects</h3>
          </div>

          {projectsLoading ? (
            <div className="spinner-border" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          ) : recentProjects.length === 0 ? (
            <div className="alert alert-light border">
              No projects yet. <Link href="/projects">Create your first project â†’</Link>
            </div>
          ) : (
            <div className="row g-3">
              {recentProjects.map((project) => (
                <div key={project.project_id} className="col-12 col-md-6 col-lg-3">
                  <div
                    className="card h-100"
                    style={{ cursor: 'pointer', transition: 'box-shadow 0.15s' }}
                    onClick={() => router.push(`/projects/${project.project_id}/documents`)}
                    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.15)')}
                    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '')}
                  >
                    <div className="card-body d-flex flex-column">
                      <h6 className="card-title mb-2">{project.name}</h6>
                      <div className="mb-2">
                        <span className={`badge bg-${project.status === 'active' ? 'success' : 'secondary'} me-2`}>
                          {project.status}
                        </span>
                        {project.is_frozen && <span className="badge bg-dark">Frozen</span>}
                      </div>
                      <small className="text-muted">
                        Documents: {typeof project.documentCount === 'number' ? project.documentCount : 'N/A'}
                      </small>
                      {project.updated_at && (
                        <small className="text-muted mt-1">
                          Updated: {new Date((project.updated_at.endsWith('Z') || project.updated_at.includes('+') ? project.updated_at : project.updated_at + 'Z')).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Hong_Kong' })}
                        </small>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="row mt-5">
          <div className="col-md-6 mb-4">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">📁 Projects</h5>
                <p className="card-text">Manage your projects</p>
                <Link href="/projects" className="btn btn-primary">
                  Go to Projects
                </Link>
              </div>
            </div>
          </div>

          <div className="col-md-6 mb-4">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">📄 My Documents</h5>
                <p className="card-text">View and manage your submitted documents</p>
                <Link href="/my-documents" className="btn btn-primary">
                  Go to My Documents
                </Link>
              </div>
            </div>
          </div>

          <div className="col-md-6 mb-4">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">📋 Documents</h5>
                <p className="card-text">Upload and manage your documents</p>
                <Link href="/documents" className="btn btn-primary">
                  Go to Documents
                </Link>
              </div>
            </div>
          </div>

          <div className="col-md-6 mb-4">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">✅ Approvals</h5>
                <p className="card-text">Review pending document approvals</p>
                <Link href="/approvals" className="btn btn-primary">
                  Go to Approvals
                </Link>
              </div>
            </div>
          </div>

          {canGenerateUrs && (
            <div className="col-md-6 mb-4">
              <div className="card">
                <div className="card-body">
                  <h5 className="card-title">📝 Generate URS</h5>
                  <p className="card-text">Generate URS and requirement documents with AI</p>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => router.push('/generate-urs')}
                  >
                    Go to Generate URS
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="col-md-6 mb-4">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">🔍 Knowledge Base</h5>
                <p className="card-text">Search and explore your knowledge base</p>
                <Link href="/knowledge-base" className="btn btn-primary">
                  Go to Knowledge Base
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
