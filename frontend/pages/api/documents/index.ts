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

  const { project_id: projectId, status } = req.query

  try {
    const backendParams: Record<string, string> = { limit: '100', offset: '0' }
    if (typeof projectId === 'string' && projectId.trim()) {
      backendParams.project_id = projectId.trim()
    }
    if (status && typeof status === 'string') {
      backendParams.status = status
    }

    const response = await axios.get(`${BACKEND_SERVICE_URL}/api/documents`, {
      params: backendParams,
      headers: { Authorization: `Bearer ${token}` },
    })

    const documentItems = response.data.documents || []

    // Fetch versions in batches of 3 to avoid exhausting the backend DB pool
    const BATCH_SIZE = 3
    const documents: any[] = []
    for (let i = 0; i < documentItems.length; i += BATCH_SIZE) {
      const batch = documentItems.slice(i, i + BATCH_SIZE)
      const results = await Promise.all(
        batch.map(async (doc: any) => {
          const docId = String(doc.doc_id)
          let versionCount = 0
          try {
            const versions = await axios.get(`${BACKEND_SERVICE_URL}/api/documents/${docId}/versions`, {
              headers: { Authorization: `Bearer ${token}` },
              timeout: 5000,
            })
            versionCount = versions.data.total || 0
          } catch {
            versionCount = 0
          }
          return {
            doc_id: docId,
            title: doc.title || `Document ${docId.slice(0, 8)}`,
            doc_type: doc.doc_type || null,
            status: doc.status || 'unknown',
            project_name: doc.project_name || null,
            submitter_name: doc.submitter_name || null,
            version_count: versionCount,
            google_drive_link: doc.google_drive_link || null,
            updated_at: doc.updated_at || null,
          }
        })
      )
      documents.push(...results)
    }

    res.status(200).json({ documents })
  } catch (error: any) {
    const status = error.response?.status || 500
    const message = error.response?.data?.detail || 'Unable to list documents'
    res.status(status).json({ message })
  }
}
