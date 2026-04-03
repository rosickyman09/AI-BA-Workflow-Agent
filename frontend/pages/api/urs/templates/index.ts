import axios from 'axios'
import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../../_lib/config'

function resolveAuthorizationHeader(req: NextApiRequest): string | null {
  const incoming = req.headers.authorization
  if (typeof incoming === 'string' && incoming.trim()) {
    return incoming
  }
  const token = getAccessToken(req)
  return token ? `Bearer ${token}` : null
}

export default async function handler(req: NextApiRequest, res: NextApiResponse): Promise<void> {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET')
    res.status(405).json({ message: 'Method not allowed' })
    return
  }

  const authorization = resolveAuthorizationHeader(req)
  if (!authorization) {
    res.status(401).json({ message: 'Unauthorized' })
    return
  }

  try {
    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/urs/templates`, {
      headers: { Authorization: authorization },
    })
    res.status(200).json(response.data)
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || error.response?.data?.message || 'Unable to load templates'
    res.status(status).json({ message })
  }
}
