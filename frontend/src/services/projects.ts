import axios from 'axios'

export interface ProjectItem {
  project_id: string
  name: string
  description: string
  status: string
  is_frozen: boolean
  created_at?: string | null
  updated_at?: string | null
  doc_count?: number
}

export interface ProjectDocumentItem {
  doc_id: string
  title: string
  status: string
  doc_type?: string | null
  created_at?: string | null
  updated_at?: string | null
  google_drive_link?: string | null
  submission_notes?: string | null
  google_drive_folder?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  workflow_status?: string | null
  current_step?: number | null
  total_steps?: number | null
  resubmit_count?: number | null
  step_1_role?: string | null
  step_2_role?: string | null
  is_active?: boolean | null
}

const projectsClient = axios.create({
  baseURL: '/api/projects',
  withCredentials: true,
})

export async function listProjects(): Promise<ProjectItem[]> {
  const response = await projectsClient.get('')
  return (response.data.items || []) as ProjectItem[]
}

export async function createProject(name: string, description: string): Promise<ProjectItem> {
  const response = await projectsClient.post('', { name, description })
  return response.data as ProjectItem
}

export async function getProject(projectId: string): Promise<ProjectItem> {
  const response = await projectsClient.get(`/${projectId}`)
  return response.data as ProjectItem
}

export async function updateProject(projectId: string, name: string, description: string): Promise<ProjectItem> {
  const response = await projectsClient.put(`/${projectId}`, { name, description })
  return response.data as ProjectItem
}

export async function updateProjectStatus(projectId: string, status: 'active' | 'inactive' | 'completed'): Promise<ProjectItem> {
  const response = await projectsClient.put(`/${projectId}`, { status })
  return response.data as ProjectItem
}

export async function updateProjectStatusByProjectPage(
  projectId: string,
  status: 'active' | 'inactive' | 'completed' | 'frozen',
): Promise<Pick<ProjectItem, 'project_id' | 'name' | 'status' | 'updated_at'>> {
  const response = await projectsClient.put(`/${projectId}/status`, { status })
  return response.data as Pick<ProjectItem, 'project_id' | 'name' | 'status' | 'updated_at'>
}

export async function getProjectDocuments(
  projectId: string,
  tab: 'all' | 'in_progress' | 'approved' | 'rejected' = 'all',
): Promise<ProjectDocumentItem[]> {
  const response = await projectsClient.get(`/${projectId}/documents`, {
    params: { tab },
  })
  return (response.data.documents || []) as ProjectDocumentItem[]
}

export async function freezeProject(projectId: string): Promise<{ project_id: string; name: string; is_frozen: boolean }> {
  const response = await projectsClient.post(`/${projectId}/freeze`)
  return response.data as { project_id: string; name: string; is_frozen: boolean }
}
