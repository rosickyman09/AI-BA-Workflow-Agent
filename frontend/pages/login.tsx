/**
 * Login Page
 */

import React, { useState } from 'react'
import { useRouter } from 'next/router'
import { Eye, EyeOff, Upload } from 'lucide-react'
import { getCurrentUser, login } from '@/services/auth'
import styles from '@/styles/login.module.css'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const result = await login(email, password)
      const user = result?.user ?? (await getCurrentUser())
      if (!user) {
        throw new Error('Session not established')
      }
      router.push('/')
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('Invalid email or password')
      } else {
        setError(err.response?.data?.message || err.message || 'Login failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.loginContainer}>
      <div className={styles.docClusterLeft} aria-hidden="true">
        <svg width="170" height="140" viewBox="0 0 170 140" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Decorative dashes to the left */}
          <line x1="2" y1="50" x2="16" y2="50" stroke="#a5c2d2" strokeWidth="1.4" strokeLinecap="round"/>
          <line x1="2" y1="63" x2="14" y2="63" stroke="#a5c2d2" strokeWidth="1.4" strokeLinecap="round"/>
          <line x1="2" y1="76" x2="13" y2="76" stroke="#a5c2d2" strokeWidth="1.4" strokeLinecap="round"/>
          {/* Back document */}
          <rect x="50" y="18" width="80" height="104" rx="10" fill="white" fillOpacity="0.5" stroke="#97bec9" strokeWidth="1.6"/>
          <line x1="64" y1="42" x2="118" y2="42" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="64" y1="55" x2="118" y2="55" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="64" y1="68" x2="100" y2="68" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="64" y1="81" x2="110" y2="81" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          {/* Front document */}
          <rect x="20" y="4" width="80" height="104" rx="10" fill="white" fillOpacity="0.68" stroke="#8ab6c4" strokeWidth="1.6"/>
          <line x1="34" y1="28" x2="88" y2="28" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="34" y1="41" x2="88" y2="41" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="34" y1="54" x2="74" y2="54" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="34" y1="67" x2="80" y2="67" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="34" y1="80" x2="77" y2="80" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </div>
      <div className={styles.docClusterRight} aria-hidden="true">
        <svg width="230" height="158" viewBox="0 0 230 158" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Back small doc */}
          <rect x="78" y="22" width="66" height="90" rx="8" fill="white" fillOpacity="0.38" stroke="#97bec9" strokeWidth="1.5"/>
          <line x1="90" y1="42" x2="134" y2="42" stroke="#b0cdd8" strokeWidth="1.6" strokeLinecap="round"/>
          <line x1="90" y1="54" x2="134" y2="54" stroke="#b0cdd8" strokeWidth="1.6" strokeLinecap="round"/>
          <line x1="90" y1="66" x2="120" y2="66" stroke="#b0cdd8" strokeWidth="1.6" strokeLinecap="round"/>
          {/* Decorative curved arcs extending right from back doc */}
          <path d="M 145 36 C 183 34 216 52 214 78 C 212 98 198 110 184 114" stroke="#93bece" strokeWidth="1.45" fill="none" strokeLinecap="round"/>
          <path d="M 145 50 C 192 48 226 70 224 98 C 222 120 206 132 190 136" stroke="#93bece" strokeWidth="1.3" fill="none" strokeLinecap="round"/>
          <path d="M 145 64 C 196 62 228 88 226 114 C 224 136 210 148 194 152" stroke="#93bece" strokeWidth="1.15" fill="none" strokeLinecap="round"/>
          {/* Front main document */}
          <rect x="8" y="6" width="92" height="124" rx="10" fill="white" fillOpacity="0.64" stroke="#8ab6c4" strokeWidth="1.6"/>
          {/* Image placeholder block */}
          <rect x="22" y="18" width="64" height="44" rx="5" fill="#b8d8e4" fillOpacity="0.72"/>
          {/* Text lines below image */}
          <line x1="22" y1="74" x2="86" y2="74" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="22" y1="87" x2="86" y2="87" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="22" y1="100" x2="70" y2="100" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
          <line x1="22" y1="113" x2="76" y2="113" stroke="#b0cdd8" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </div>

      <div className={`card shadow-lg ${styles.loginCard}`}>
        <div className={`card-body p-4 p-md-5 ${styles.loginCardBody}`}>
          <h1 className={`mb-4 text-center ${styles.loginTitle}`}>AI BA Workflow Agent</h1>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label className={`form-label ${styles.fieldLabel}`}>Email</label>
              <input
                type="email"
                className={`form-control w-100 ${styles.loginInput}`}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="mb-3">
              <div className={styles.passwordRow}>
                <label className={`form-label mb-0 ${styles.fieldLabel}`}>Password</label>
                <div className={styles.toggleLinkWrapper}>
                  <span className={styles.toggleLinkText}>View/Hide</span>
                </div>
              </div>
              <div className={styles.passwordInputWrap}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  className={`form-control w-100 ${styles.loginInput} ${styles.passwordInput}`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder=".........."
                  required
                />
                <button
                  type="button"
                  className={styles.eyeButton}
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <Eye size={18} /> : <EyeOff size={18} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className={`btn w-100 ${styles.loginButton}`}
              disabled={loading}
            >
              <Upload size={18} className={styles.btnIcon} /> {loading ? 'LOGGING IN...' : 'LOG IN'}
            </button>
          </form>

          <div className={styles.demoPanel}>
            <div className={styles.demoHeader}>DEMO ACCESS</div>
            <div className={styles.demoList}>
              <div className={styles.demoCell}>admin@ai-ba.local</div>
              <div className={styles.demoCell}>ba1@ai-ba.local</div>
              <div className={styles.demoCell}>ba2@ai-ba.local</div>
              <div className={styles.demoCell}>owner@ai-ba.local</div>
            </div>
            <div className={styles.demoPassword}><strong>Password:</strong> password123</div>
          </div>
        </div>
      </div>
    </div>
  )
}
