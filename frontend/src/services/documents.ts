import axios from 'axios'

export interface UploadResponse {
  document_id: string
  workflow_id: string
  status: string
  step_1_role?: string | null
}

export interface DocumentStatus {
  document_id: string
  title: string
  status: string
  progress: number
  updated_at?: string | null
}

export interface DocumentListItem {
  doc_id: string
  title: string
  doc_type?: string | null
  status: string
  project_name?: string | null
  submitter_name?: string | null
  version_count: number
  google_drive_link?: string | null
  updated_at?: string | null
}

export interface DocumentVersion {
  version_id: string
  version_number: number
  approval_status: string
  created_at?: string | null
}

export interface PendingApprovalItem {
  workflow_id: string
  doc_id: string
  doc_title?: string
  doc_type?: string | null
  current_step: number
  total_steps: number
  status: string
  updated_at?: string | null
  submitted_at?: string | null
  google_drive_link?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
  project_name?: string | null
  submission_notes?: string | null
  resubmit_count?: number | null
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  edit_url?: string | null
}

export type ApprovalListStatus = 'pending' | 'completed' | 'all'

export interface MyDocumentItem {
  doc_id: string
  title: string
  doc_type?: string | null
  doc_status: string
  project_id: string
  project_name: string
  created_at?: string | null
  updated_at?: string | null
  workflow_id?: string | null
  workflow_status?: string | null
  current_step?: number | null
  total_steps?: number | null
  step_1_role?: string | null
  step_2_role?: string | null
  submission_notes?: string | null
  resubmit_count?: number | null
}

export type MyDocumentStatus = 'in_progress' | 'completed' | 'all'

export interface WorkflowInfo {
  workflow_id: string
  status: string
  current_step: number
  total_steps: number
  step_1_role?: string | null
  step_2_role?: string | null
  submitter_id?: string | null
}

export interface HistoryEntry {
  action: string
  actor_name?: string | null
  actor_role?: string | null
  step?: number | null
  comment?: string | null
  created_at?: string | null
}

export interface DocumentDetail {
  doc_id: string
  title: string
  doc_type?: string | null
  status: string
  project_id: string
  project_name: string
  submitter_id?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  google_drive_link?: string | null
  edit_url?: string | null
  file_mime_type?: string | null
  created_at?: string | null
  updated_at?: string | null
  submission_notes?: string | null
  workflow?: WorkflowInfo | null
  history: HistoryEntry[]
}

const docsClient = axios.create({
  baseURL: '/api/documents',
  withCredentials: true,
})

const approvalsClient = axios.create({
  baseURL: '/api/approvals',
  withCredentials: true,
})

export async function uploadDocument(
  file: File,
  projectId: string,
  onProgress?: (progress: number) => void,
  submissionNotes?: string,
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_id', projectId)
  formData.append('title', file.name)
  if (submissionNotes) {
    formData.append('submission_notes', submissionNotes)
  }

  const response = await docsClient.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) {
        return
      }
      const progress = Math.round((event.loaded / event.total) * 100)
      onProgress(progress)
    },
  })

  return response.data as UploadResponse
}

export async function getDocumentStatus(docId: string): Promise<DocumentStatus> {
  const response = await docsClient.get(`/${docId}/status`)
  return response.data as DocumentStatus
}

export async function listDocuments(projectId?: string, status?: string): Promise<DocumentListItem[]> {
  const params: Record<string, string> = {}
  if (projectId && projectId.trim()) {
    params.project_id = projectId.trim()
  }
  if (status) params.status = status
  const response = await docsClient.get('', { params })
  return (response.data.documents || []) as DocumentListItem[]
}

export async function getDocumentVersions(docId: string): Promise<DocumentVersion[]> {
  const response = await docsClient.get(`/${docId}/versions`)
  return (response.data.versions || []) as DocumentVersion[]
}

export async function getPendingApprovals(projectId: string): Promise<PendingApprovalItem[]> {
  const response = await approvalsClient.get('/pending', { params: { project_id: projectId } })
  return (response.data.items || []) as PendingApprovalItem[]
}

export async function getApprovals(
  projectId: string | null,
  status: ApprovalListStatus,
): Promise<PendingApprovalItem[]> {
  const params: Record<string, string> = { status }
  if (projectId) params.project_id = projectId
  const response = await approvalsClient.get('', { params })
  return (response.data.items || []) as PendingApprovalItem[]
}

export async function approveWorkflow(workflowId: string, comment = ''): Promise<void> {
  await approvalsClient.post(`/${workflowId}/approve`, { comment })
}

export async function rejectWorkflow(workflowId: string, reason: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/reject`, { reason })
}

export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string, resubmitNotes?: string): Promise<void> {
  const response = await docsClient.post(`/${docId}/resubmit`, resubmitNotes ? { resubmit_notes: resubmitNotes } : {})
  return response.data
}

export async function getMySubmissions(status: MyDocumentStatus = 'in_progress'): Promise<MyDocumentItem[]> {
  const response = await docsClient.get('/my-submissions', { params: { status } })
  return (response.data.documents || []) as MyDocumentItem[]
}

export async function getDocumentDetail(docId: string): Promise<DocumentDetail> {
  const response = await docsClient.get(`/${docId}/detail`)
  return response.data as DocumentDetail
}

