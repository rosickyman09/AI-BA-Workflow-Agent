import axios from 'axios'

export interface InAppNotification {
  notification_id: string
  title: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
  is_read: boolean
  related_doc_id?: string | null
  related_workflow_id?: string | null
  project_name?: string | null
  doc_name?: string | null
  created_at: string
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getInAppNotifications(unreadOnly = false, limit = 50): Promise<InAppNotification[]> {
  const response = await client.get('/in-app', { params: { unread_only: unreadOnly, limit } })
  return (response.data.items || []) as InAppNotification[]
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/in-app/unread-count')
  return (response.data.unread_count as number) ?? 0
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/in-app/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/in-app/read-all')
}
