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

  const { docId } = req.query
  if (!docId || typeof docId !== 'string') {
    res.status(400).json({ message: 'docId is required' })
    return
  }

  try {
    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/documents/${docId}/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to fetch document status'
    res.status(status).json({ message })
  }
}
