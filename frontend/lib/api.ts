import axios from 'axios'

let isRefreshing = false

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry && !isRefreshing) {
      original._retry = true
      isRefreshing = true
      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const refreshRes = await axios.post(`${baseURL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          const newAccessToken = refreshRes.data.access_token
          if (newAccessToken) {
            localStorage.setItem('access_token', newAccessToken)
            original.headers.Authorization = `Bearer ${newAccessToken}`
            return api(original)
          }
        }
        throw new Error('No refresh token')
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(err)
  }
)

export default api
