import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AuthUser {
  id: number
  username: string
  name: string
  role: 'admin' | 'nutritionist' | 'viewer'
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  setAuth: (token: string, user: AuthUser) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'mealplan-auth' },
  ),
)

export const ROLE_LABELS: Record<string, string> = {
  admin: '系统管理员',
  nutritionist: '营养师',
  viewer: '只读查看员',
}

export const canWrite = (role?: string) =>
  role === 'admin' || role === 'nutritionist'
