import type { NextApiRequest } from 'next'

export const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || 'http://localhost:5001'
export const BACKEND_SERVICE_URL = process.env.BACKEND_SERVICE_URL || 'http://localhost:5000'
export const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:5002'

export function getAccessToken(req: NextApiRequest): string | null {
  const rawCookie = req.headers.cookie || ''
  const cookieMap = rawCookie.split(';').map((item) => item.trim())
  const found = cookieMap.find((item) => item.startsWith('access_token='))
  if (!found) {
    const cookieNames = cookieMap.map((c) => c.split('=')[0]).filter(Boolean)
    console.error(
      `[getAccessToken] access_token cookie NOT found. Path: ${req.url} | ` +
        `Available cookies: [${cookieNames.join(', ') || 'none'}]`
    )
    return null
  }
  const value = found.split('=').slice(1).join('=')
  return decodeURIComponent(value)
}
