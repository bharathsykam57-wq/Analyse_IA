import api from './api'
import { AuthTokens, LoginRequest, RegisterRequest, User } from '@/types'

export async function login(data: LoginRequest): Promise<AuthTokens> {
  const res = await api.post('/auth/login', {
    email: data.email,
    password: data.password,
  })
  const tokens: AuthTokens = res.data.tokens
  if (typeof window !== 'undefined') {
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
  }
  return tokens
}

export async function register(data: RegisterRequest): Promise<User> {
  const res = await api.post('/auth/register', data)
  const tokens: AuthTokens = res.data.tokens
  if (tokens && typeof window !== 'undefined') {
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
  }
  return res.data.user
}

export async function logout(): Promise<void> {
  try {
    const refresh_token = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null
    await api.post('/auth/logout', { refresh_token })
  } catch {
    // Logout endpoint may not exist or fail, but we still clear tokens
  } finally {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const res = await api.get<User>('/auth/me')
    return res.data
  } catch {
    return null
  }
}

export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false
  return !!localStorage.getItem('access_token')
}
