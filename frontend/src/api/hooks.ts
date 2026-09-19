import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  Elder, Dish, Ingredient, Plan, TaskInfo, RuleVersion, RuleItem, AuditLog,
} from '../lib/types'

// ── 认证 ──
export function useLogin() {
  return useMutation({
    mutationFn: (b: { username: string; password: string }) =>
      api.post('/api/auth/login-json', b).then((r) => r.data),
  })
}

// ── 老人 ──
export const eldersKey = ['elders']
export function useElders() {
  return useQuery({ queryKey: eldersKey, queryFn: () =>
    api.get<Elder[]>('/api/elders').then((r) => r.data) })
}
export function useElder(id: number | null | undefined) {
  return useQuery({
    queryKey: ['elder', id], enabled: !!id,
    queryFn: () => api.get<Elder>(`/api/elders/${id}`).then((r) => r.data),
  })
}
export function useSaveElder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: Elder) =>
      b.id
        ? api.put(`/api/elders/${b.id}`, b).then((r) => r.data)
        : api.post('/api/elders', b).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: eldersKey }),
  })
}
export function usePreviewTargets() {
  return useMutation({
    mutationFn: (b: unknown) =>
      api.post('/api/elders/preview-targets', b).then((r) => r.data),
  })
}

// ── 菜品库 ──
export function useIngredients() {
  return useQuery({ queryKey: ['ingredients'], queryFn: () =>
    api.get<Ingredient[]>('/api/food/ingredients').then((r) => r.data) })
}
export function useDishes(params?: { iddsi_max?: number }) {
  return useQuery({
    queryKey: ['dishes', params?.iddsi_max],
    queryFn: () => api.get<Dish[]>('/api/food/dishes', { params }).then((r) => r.data),
  })
}
export function useSaveDish() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: Dish) =>
      b.id
        ? api.put(`/api/food/dishes/${b.id}`, b).then((r) => r.data)
        : api.post('/api/food/dishes', b).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dishes'] }),
  })
}
export function useSaveIngredient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: Ingredient) =>
      b.id
        ? api.put(`/api/food/ingredients/${b.id}`, b).then((r) => r.data)
        : api.post('/api/food/ingredients', b).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ingredients'] }),
  })
}

// ── 规则 ──
export function useRuleVersions() {
  return useQuery({ queryKey: ['rule-versions'], queryFn: () =>
    api.get<RuleVersion[]>('/api/rules/versions').then((r) => r.data) })
}
export function useRules(versionId: number | null) {
  return useQuery({
    queryKey: ['rules', versionId], enabled: versionId != null,
    queryFn: () => api.get<RuleItem[]>(
      `/api/rules/versions/${versionId}/rules`).then((r) => r.data),
  })
}
export function useCheckDishes() {
  return useMutation({
    mutationFn: (b: { elder_id: number; dish_ids: number[] }) =>
      api.post('/api/rules/check-dishes', b).then((r) => r.data),
  })
}

// ── 方案 ──
export function usePlans(elderId?: number) {
  return useQuery({
    queryKey: ['plans', elderId],
    queryFn: () => api.get<Plan[]>('/api/plans', { params: { elder_id: elderId } })
      .then((r) => r.data),
  })
}
export function usePlan(id: number | null | undefined) {
  return useQuery({
    queryKey: ['plan', id], enabled: !!id,
    queryFn: () => api.get<Plan>(`/api/plans/${id}`).then((r) => r.data),
  })
}
export function useSolve() {
  return useMutation({
    mutationFn: (b: unknown) =>
      api.post('/api/plans/solve', b).then((r) => r.data as { task_id: number }),
  })
}
export function useResolve() {
  return useMutation({
    mutationFn: (planId: number) =>
      api.post(`/api/plans/${planId}/resolve`).then((r) => r.data),
  })
}
export function useUpdatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: unknown }) =>
      api.put(`/api/plans/${id}`, body).then((r) => r.data as Plan),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['plan', v.id] }),
  })
}
export function usePlanAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action, lockVersion }:
      { id: number; action: 'publish' | 'archive'; lockVersion: number }) =>
      api.post(`/api/plans/${id}/${action}`, null, {
        params: action === 'publish' ? { lock_version: lockVersion } : undefined,
      }).then((r) => r.data),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ['plan', v.id] })
      qc.invalidateQueries({ queryKey: ['plans'] })
    },
  })
}
export function usePlanVersions(id: number | null) {
  return useQuery({
    queryKey: ['plan-versions', id], enabled: !!id,
    queryFn: () => api.get(`/api/plans/${id}/versions`).then((r) => r.data),
  })
}
export function useRollback() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, v }: { id: number; v: number }) =>
      api.post(`/api/plans/${id}/rollback/${v}`).then((r) => r.data),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['plan', v.id] }),
  })
}

export function useTask(id: number | null, opts?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: ['task', id], enabled: !!id,
    queryFn: () => api.get<TaskInfo>(`/api/tasks/${id}`).then((r) => r.data),
    refetchInterval: opts?.refetchInterval === undefined ? 1500 : opts.refetchInterval,
  })
}

// ── 日志 ──
export function useAuditLogs(limit = 100) {
  return useQuery({
    queryKey: ['audit-logs', limit],
    queryFn: () => api.get<AuditLog[]>('/api/audit-logs', { params: { limit } })
      .then((r) => r.data),
  })
}

export function usePurchase(planId: number | null) {
  return useQuery({
    queryKey: ['purchase', planId], enabled: !!planId,
    queryFn: () => api.get(`/api/reports/plans/${planId}/purchase`).then((r) => r.data),
  })
}
