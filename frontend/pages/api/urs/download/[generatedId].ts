import type { NextApiRequest, NextApiResponse } from 'next'
import { BACKEND_SERVICE_URL, getAccessToken } from '../../_lib/config'

function resolveAuthorizationHeader(req: NextApiRequest): string | null {
  const incoming = req.headers.authorization
  if (typeof incoming === 'string' && incoming.trim()) return incoming
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

  const { generatedId } = req.query
  if (!generatedId || typeof generatedId !== 'string') {
    res.status(400).json({ message: 'generatedId is required' })
    return
  }

  try {
    const response = await fetch(`${BACKEND_SERVICE_URL}/api/urs/download/${generatedId}`, {
      headers: { Authorization: authorization },
    })

    if (!response.ok) {
      const text = await response.text()
      res.status(response.status).json({ message: text })
      return
    }

    const contentType = response.headers.get('content-type') || 'application/octet-stream'
    const contentDisposition = response.headers.get('content-disposition') || ''

    res.setHeader('Content-Type', contentType)
    if (contentDisposition) {
      res.setHeader('Content-Disposition', contentDisposition)
    }

    const arrayBuffer = await response.arrayBuffer()
    res.send(Buffer.from(arrayBuffer))
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Download failed'
    res.status(500).json({ message })
  }
}
