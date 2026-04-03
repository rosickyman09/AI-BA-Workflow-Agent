import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'GET' && req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const token = getAccessToken(req)
  if (!token) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  try {
    if (req.method === 'GET') {
      const { project_id } = req.query
      if (!project_id || typeof project_id !== 'string') {
        res.status(400).json({ message: 'project_id is required' })
        return
      }

      const response = await axios.get(`${BACKEND_SERVICE_URL}/api/knowledge-base/rag`, {
        params: { project_id },
        headers: { Authorization: `Bearer ${token}` },
      })
      res.status(200).json(response.data)
      return
    }

    const response = await axios.post(`${BACKEND_SERVICE_URL}/api/knowledge-base/rag`, req.body, {
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || error.response?.data?.message || 'Knowledge base RAG request failed'
    res.status(status).json({ message })
  }
}
