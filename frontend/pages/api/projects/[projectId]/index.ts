import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  const { projectId } = req.query
  if (!projectId || typeof projectId !== 'string') {
    res.status(400).json({ message: 'projectId is required' })
    return
  }

  try {
    if (req.method === 'GET') {
      const response = await axios.get(`${BACKEND_SERVICE_URL}/api/projects/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      res.status(200).json(response.data)
      return
    }

    if (req.method === 'PUT') {
      const response = await axios.put(`${BACKEND_SERVICE_URL}/api/projects/${projectId}`, req.body, {
        headers: { Authorization: `Bearer ${token}` },
      })
      res.status(200).json(response.data)
      return
    }

    res.setHeader('Allow', 'GET, PUT')
    res.status(405).json({ message: 'Method not allowed' })
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Project API request failed'
    res.status(statusCode).json({ message })
  }
}
