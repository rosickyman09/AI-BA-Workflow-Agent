import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { AUTH_SERVICE_URL, getAccessToken } from '../../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  const { userId } = req.query as { userId: string }
  const headers = { Authorization: `Bearer ${token}` }

  try {
    if (req.method === 'GET') {
      const response = await axios.get(`${AUTH_SERVICE_URL}/auth/admin/users/${userId}`, { headers })
      res.status(200).json(response.data)
    } else if (req.method === 'PUT') {
      const response = await axios.put(`${AUTH_SERVICE_URL}/auth/admin/users/${userId}`, req.body, { headers })
      res.status(200).json(response.data)
    } else {
      res.setHeader('Allow', ['GET', 'PUT'])
      res.status(405).json({ message: 'Method not allowed' })
    }
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Request failed'
    res.status(status).json({ message })
  }
}
