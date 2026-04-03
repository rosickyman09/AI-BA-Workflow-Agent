import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../../_lib/config'

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
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
    const response = await axios.post(
      `${BACKEND_SERVICE_URL}/api/documents/${docId}/resubmit`,
      req.body || {},
      { headers: { Authorization: `Bearer ${token}` } }
    )
    res.status(200).json(response.data)
  } catch (error: any) {
    const statusCode = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to resubmit document'
    res.status(statusCode).json({ message, detail: message })
  }
}
