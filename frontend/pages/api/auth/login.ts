import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { AUTH_SERVICE_URL } from '../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  try {
    const response = await axios.post(`${AUTH_SERVICE_URL}/auth/login`, req.body)
    const accessToken = response.data.access_token as string

    res.setHeader(
      'Set-Cookie',
      `access_token=${encodeURIComponent(accessToken)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600`
    )

    res.status(200).json({
      user: response.data.user,
      expires_in: response.data.expires_in,
    })
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Login failed'
    res.status(status).json({ message })
  }
}
