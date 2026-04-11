import axios from 'axios'

const TOKEN_KEY = 'saveany_token'

function getAuthHeaders() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export async function parseVideo(url) {
  const { data } = await api.post('/parse', { url }, { headers: getAuthHeaders() })
  return data
}

export async function getDirectUrl(url, formatId) {
  const { data } = await api.post('/direct-url', { url, format_id: formatId })
  return data
}

export function getDownloadUrl() {
  return '/api/download'
}

export async function downloadViaServer(url, formatId) {
  const response = await api.post(
    '/download',
    { url, format_id: formatId },
    { responseType: 'blob', timeout: 600000, headers: getAuthHeaders() }
  )
  return response
}
