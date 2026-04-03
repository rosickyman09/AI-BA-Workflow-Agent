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

  const { project_id, limit = '100', offset = '0' } = req.query

  try {
    const params: Record<string, string> = {
      limit: typeof limit === 'string' ? limit : '100',
      offset: typeof offset === 'string' ? offset : '0',
    }
    if (project_id && typeof project_id === 'string') {
      params.project_id = project_id
    }

    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/documents/in-review`, {
      params,
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to fetch in-review documents'
    res.status(statusCode).json({ message, detail: message })
  }
}
