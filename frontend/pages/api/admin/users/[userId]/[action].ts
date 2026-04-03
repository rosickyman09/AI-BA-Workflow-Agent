import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { AUTH_SERVICE_URL, getAccessToken } from '../../../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'PATCH') {
    res.setHeader('Allow', 'PATCH')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  const { userId, action } = req.query as { userId: string; action: string }
  if (action !== 'activate' && action !== 'deactivate') {
    res.status(400).json({ message: 'action must be activate or deactivate' })
    return
  }

  const headers = { Authorization: `Bearer ${token}` }

  try {
    const response = await axios.patch(
      `${AUTH_SERVICE_URL}/auth/admin/users/${userId}/${action}`,
      {},
      { headers }
    )
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Request failed'
    res.status(status).json({ message })
  }
}
