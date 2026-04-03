import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../_lib/config'

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

  const { project_id: projectId } = req.query
  if (!projectId || typeof projectId !== 'string') {
    res.status(400).json({ message: 'project_id is required' })
    return
  }

  try {
    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/approvals/pending`, {
      params: { project_id: projectId, page: 1, page_size: 100 },
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to fetch pending approvals'
    res.status(status).json({ message })
  }
}
