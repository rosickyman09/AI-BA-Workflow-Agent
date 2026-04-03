import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  try {
    if (req.method === 'GET') {
      const params: Record<string, string> = {}
      if (typeof req.query.status === 'string' && req.query.status.trim()) {
        params.status = req.query.status.trim()
      }
      const response = await axios.get(`${BACKEND_SERVICE_URL}/api/projects`, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      })
      res.status(200).json(response.data)
      return
    }

    if (req.method === 'POST') {
      const response = await axios.post(`${BACKEND_SERVICE_URL}/api/projects`, req.body, {
        headers: { Authorization: `Bearer ${token}` },
      })
      res.status(200).json(response.data)
      return
    }

    res.setHeader('Allow', 'GET, POST')
    res.status(405).json({ message: 'Method not allowed' })
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Projects API request failed'
    res.status(statusCode).json({ message })
  }
}
