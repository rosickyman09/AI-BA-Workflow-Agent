/**
 * Main Layout Component
 */

import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from './NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [currentUser, setCurrentUser] = useState<{ email: string; full_name?: string | null; role?: string } | null>(null)
  const normalizedRole = (currentUser?.role || '').trim().toLowerCase()

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      if (user) {
        console.debug('[Layout] current user role:', user.role)
      }
      setCurrentUser(user)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {currentUser && (
        <nav
          className={`${styles.navbar} navbar navbar-expand-lg navbar-dark`}
          style={{
            background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}
        >
          <div className="container-fluid">
            <Link href="/" className="navbar-brand fw-bold" style={{ letterSpacing: '0.5px' }}>
              🤖 AI BA Workflow Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                {!['it', 'viewer'].includes(normalizedRole) && (
                  <li className="nav-item">
                    <Link href="/my-documents" className="nav-link">
                      My Documents
                    </Link>
                  </li>
                )}
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                {['admin', 'ba', 'pm', 'business_owner'].includes(normalizedRole) && (
                  <li className="nav-item">
                    <Link href="/generate-urs" className="nav-link">
                      Generate URS
                    </Link>
                  </li>
                )}
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                {normalizedRole === 'admin' && (
                  <li className="nav-item">
                    <Link href="/setup" className="nav-link">
                      ⚙️ Setup
                    </Link>
                  </li>
                )}
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>

                {/* User avatar + name + role badge */}
                <li className="nav-item d-flex align-items-center ms-3 gap-2">
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #e44d7b, #6b48ff)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontWeight: 700,
                      fontSize: 14,
                      flexShrink: 0,
                      boxShadow: '0 0 0 2px rgba(255,255,255,0.2)',
                    }}
                    title={currentUser.full_name || currentUser.email}
                  >
                    {(currentUser.full_name || currentUser.email || '?')[0].toUpperCase()}
                  </div>
                  <div className="d-flex flex-column" style={{ lineHeight: 1.2 }}>
                    <span className="text-white" style={{ fontSize: 13 }}>
                      {currentUser.full_name || currentUser.email}
                    </span>
                    {currentUser.role && (
                      <span
                        className="badge"
                        style={{
                          fontSize: 10,
                          background: 'rgba(255,255,255,0.15)',
                          color: '#a8d8ff',
                          alignSelf: 'flex-start',
                          marginTop: 2,
                        }}
                      >
                        {currentUser.role}
                      </span>
                    )}
                  </div>
                </li>

                <li className="nav-item d-flex align-items-center ms-2">
                  <NotificationBell />
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      <main className={styles.main}>
        {children}
      </main>

      <footer className={`${styles.footer} text-center py-3 bg-light`}>
        <p>&copy; 2026 AI BA Workflow Agent. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default Layout
