import axios from 'axios'
import { useAuthStore } from '../store/auth'

export const api = axios.create({ baseURL: '/' })

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(err)
  },
)

export function downloadFile(url: string, filename: string) {
  return api.get(url, { responseType: 'blob' }).then((r) => {
    const href = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    a.click()
    URL.revokeObjectURL(href)
  })
}
