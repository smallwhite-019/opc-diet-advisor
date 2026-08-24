// API 基础地址：生产环境通过 VITE_API_BASE 配置后端公网地址
function authHeader() {
  const t = localStorage.getItem('opc_token')
  return t ? { 'Authorization': 'Bearer ' + t } : {}
}
const BASE = import.meta.env.VITE_API_BASE || ''

export async function chat(conv_id, message) {
  const r = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ conv_id: conv_id || '', message })
  })
  return r.json()
}

export const suggest = runSuggest

export async function runSuggest(crowd) {
  const r = await fetch(`${BASE}/api/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ crowd })
  })
  return r.json()
}

export async function loadSessions(user_id) {
  const r = await fetch(`${BASE}/api/sessions`, { headers: authHeader() })
  return r.json()
}

export async function loadHistory(conv_id, user_id = '') {
  const r = await fetch(`${BASE}/api/history?conv_id=${encodeURIComponent(conv_id)}`, { headers: authHeader() })
  return r.json()
}

export async function removeSession(conv_id) {
  await fetch(`${BASE}/api/sessions/${conv_id}`, { method: 'DELETE', headers: authHeader() })
}

export async function getGreeting() {
  const r = await fetch(`${BASE}/api/greeting`)
  return r.json()
}

export async function getKb() {
  const r = await fetch(`${BASE}/api/kb`)
  return r.json()
}

export async function getProfile(user_id) {
  const r = await fetch(`${BASE}/api/profile`, { headers: authHeader() })
  return r.json()
}

export async function getAccount(user_id) {
  const r = await fetch(`${BASE}/api/account`, { headers: authHeader() })
  return r.json()
}

export async function setNickname(user_id, nickname) {
  const r = await fetch(`${BASE}/api/account/nickname`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ nickname })
  })
  return r.json()
}

export async function clearAccount(user_id) {
  const r = await fetch(`${BASE}/api/account/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ })
  })
  return r.json()
}

export async function exportAccount(user_id) {
  const r = await fetch(`${BASE}/api/account/export`, { headers: authHeader() })
  return r.json()
}


export async function register(username, password, nickname) {
  const r = await fetch(`${BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, nickname })
  })
  return r.json()
}

export async function login(username, password) {
  const r = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  })
  return r.json()
}
