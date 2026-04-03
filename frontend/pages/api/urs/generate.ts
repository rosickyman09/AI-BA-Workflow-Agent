import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../_lib/config'

export const config = {
  api: {
    responseLimit: false,
    bodyParser: { sizeLimit: '10mb' },
  },
}

function resolveAuthorizationHeader(req: NextApiRequest): string | null {
  const incoming = req.headers.authorization
  if (typeof incoming === 'string' && incoming.trim()) {
    return incoming
  }
  const token = getAccessToken(req)
  return token ? `Bearer ${token}` : null
}

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const authorization = resolveAuthorizationHeader(req)
  if (!authorization) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  try {
    const response = await axios.post(`${BACKEND_SERVICE_URL}/api/urs/generate`, req.body, {
      headers: { Authorization: authorization },
      timeout: 1140000, // 1140s — just under nginx 1200s limit
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message =
      error.code === 'ECONNABORTED'
        ? 'URS generation timed out. The document may be large — please try again.'
        : error.response?.data?.detail || error.response?.data?.message || 'Generate request failed'
    res.status(status).json({ message })
  }
}
