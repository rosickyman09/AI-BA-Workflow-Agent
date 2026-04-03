import axios from 'axios'

export interface AuthUser {
  user_id: string
  email: string
  role: string
  full_name?: string | null
  projects: Array<{ project_id: string; role: string }>
}

const authClient = axios.create({
  baseURL: '/api/auth',
  withCredentials: true,
})

export async function login(email: string, password: string): Promise<{ user: AuthUser }> {
  const response = await authClient.post('/login', { email, password })
  return response.data
}

export async function logout(): Promise<void> {
  await authClient.post('/logout')
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    const response = await authClient.get('/me')
    return response.data as AuthUser
  } catch {
    return null
  }
}

export async function isAuthenticated(): Promise<boolean> {
  const user = await getCurrentUser()
  return user !== null
}
