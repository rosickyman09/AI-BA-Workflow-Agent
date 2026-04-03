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

  const { project_id: projectId, status = 'pending' } = req.query
  const statusValue = typeof status === 'string' ? status : 'pending'
  const params: Record<string, string | number> = { status: statusValue, page: 1, page_size: 200 }
  if (projectId && typeof projectId === 'string') {
    params.project_id = projectId
  }

  try {
    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/approvals`, {
      params,
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to fetch approvals'
    res.status(statusCode).json({ message })
  }
}
