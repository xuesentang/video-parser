/**
 * 博主追踪系统 API 封装
 */
import axios from 'axios'

const TOKEN_KEY = 'saveany_token'

function getAuthHeaders() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const api = axios.create({
  baseURL: '/api/tracker',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const headers = getAuthHeaders()
  Object.assign(config.headers, headers)
  return config
})

// ============ 博主/订阅管理 ============

export async function addCreator(url) {
  const { data } = await api.post('/creators', { url })
  return data
}

export async function listCreators() {
  const { data } = await api.get('/creators')
  return data
}

export async function updateSubscription(subId, { alias, groupTag }) {
  const { data } = await api.patch(`/creators/${subId}`, {
    alias: alias || null,
    group_tag: groupTag || null,
  })
  return data
}

export async function removeCreator(subId) {
  const { data } = await api.delete(`/creators/${subId}`)
  return data
}

// ============ 报告管理 ============

export async function listReports({ limit = 20, offset = 0 } = {}) {
  const { data } = await api.get('/reports', { params: { limit, offset } })
  return data
}

export async function getReport(reportId) {
  const { data } = await api.get(`/reports/${reportId}`)
  return data
}

export async function deleteReport(reportId) {
  const { data } = await api.delete(`/reports/${reportId}`)
  return data
}

export async function generateReport(timeRangeHours = 24) {
  const { data } = await api.post('/reports/generate', {
    time_range_hours: timeRangeHours,
  })
  return data
}

export async function getReportProgress(reportId) {
  const { data } = await api.get(`/reports/${reportId}/progress`)
  return data
}
