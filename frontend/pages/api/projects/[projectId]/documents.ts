import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  const { projectId, tab } = req.query
  if (!projectId || typeof projectId !== 'string') {
    res.status(400).json({ message: 'projectId is required' })
    return
  }

  try {
    const params: Record<string, string> = {}
    if (typeof tab === 'string' && tab.trim()) {
      params.tab = tab.trim()
    }

    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/projects/${projectId}/documents`, {
      params,
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Project documents API request failed'
    res.status(statusCode).json({ message })
  }
}
