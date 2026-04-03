import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { AUTH_SERVICE_URL, getAccessToken } from '../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const token = getAccessToken(req)

  try {
    if (token) {
      await axios.post(
        `${AUTH_SERVICE_URL}/auth/logout`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
    }
  } catch {
    // Always clear the cookie even if upstream logout fails.
  }

  res.setHeader(
    'Set-Cookie',
    'access_token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
  )

  res.status(200).json({ status: 'logged_out' })
}
