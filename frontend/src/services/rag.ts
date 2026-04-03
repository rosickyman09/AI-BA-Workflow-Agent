import axios from 'axios'

export interface RAGResult {
  text: string
  doc_id: string
  section: string
  citation: string
  score?: number
}

export interface RAGResponse {
  query: string
  results: RAGResult[]
  citations: string[]
  total_found: number
  search_time_ms: number
  confidence: number
}

export interface RagDocumentItem {
  doc_id: string
  status: 'indexed' | 'pending'
}

export interface RagDocumentListResponse {
  project_id: string
  doc_ids: string[]
  items: RagDocumentItem[]
  count: number
}

export interface AddRagDocumentsResponse {
  added_count: number
  doc_ids: string[]
  message: string
}

const ragClient = axios.create({
  baseURL: '/api/rag',
  withCredentials: true,
})

export async function searchKnowledgeBase(query: string, projectId: string): Promise<RAGResponse> {
  const response = await ragClient.post('/search', {
    query,
    project_id: projectId,
    top_k: 5,
    user_id: 'frontend-user',
  })

  const data = response.data as RAGResponse
  return {
    ...data,
    results: (data.results || []).map((result: any) => ({
      text: result.text || result.content || '',
      doc_id: result.doc_id || result.metadata?.doc_id || 'unknown',
      section: String(result.section || result.metadata?.section || '1'),
      citation: result.citation || `[${result.doc_id || 'unknown'}#${result.section || '1'}]`,
      score: result.score,
    })),
  }
}

export async function getRagDocuments(projectId: string): Promise<RagDocumentListResponse> {
  const response = await axios.get('/api/knowledge-base/rag', {
    params: { project_id: projectId },
    withCredentials: true,
  })
  return response.data as RagDocumentListResponse
}

export async function addDocumentsToRag(docIds: string[]): Promise<AddRagDocumentsResponse> {
  const response = await axios.post(
    '/api/knowledge-base/rag',
    { doc_ids: docIds },
    { withCredentials: true },
  )
  return response.data as AddRagDocumentsResponse
}
