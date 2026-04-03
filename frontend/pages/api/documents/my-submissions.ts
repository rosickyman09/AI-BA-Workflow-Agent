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

  const { status = 'in_progress', page = '1', page_size = '20' } = req.query

  try {
    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/documents/my-submissions`, {
      params: {
        status: typeof status === 'string' ? status : 'in_progress',
        page: typeof page === 'string' ? page : '1',
        page_size: typeof page_size === 'string' ? page_size : '20',
      },
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to fetch submissions'
    res.status(statusCode).json({ message, detail: message })
  }
}
